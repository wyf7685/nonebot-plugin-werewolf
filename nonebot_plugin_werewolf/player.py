import asyncio
import asyncio.timeouts
import contextlib
from enum import Enum, auto
from typing import TYPE_CHECKING, ClassVar
from typing_extensions import override

from nonebot.adapters import Bot
from nonebot_plugin_alconna.uniseg import Receipt, Target, UniMessage

from .input_store import store
from .utils import check_index

if TYPE_CHECKING:
    from .game import Game


class Role(Enum):
    # 狼人
    狼人 = auto()

    # 神职
    预言家 = auto()
    女巫 = auto()
    猎人 = auto()
    守卫 = auto()

    # 平民
    平民 = auto()


class Player:
    bot: Bot
    user: Target
    name: str
    role: ClassVar[Role]
    alive: bool
    selected: "Player | None"

    def __init__(self, bot: Bot, user: Target, name: str) -> None:
        assert self.__class__ is not Player
        self.bot = bot
        self.user = user
        self.name = name
        self.alive = True
        self.selected = None

    @classmethod
    def new(cls, bot: Bot, user: Target, name: str, role: Role) -> "Player":
        for c in cls.__subclasses__():
            if c.role == role:
                return c(bot, user, name)
        else:
            raise ValueError(f"Unexpected role: {role!r}")

    def __repr__(self) -> str:
        return f"<{self.role.name}: {self.user}>"

    async def send(self, message: str | UniMessage) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        return await message.send(target=self.user, bot=self.bot)

    async def receive(self, prompt: str | UniMessage | None = None) -> UniMessage:
        if prompt:
            await self.send(prompt)
        return await store.fetch(self.user.id)

    async def notify_role(self):
        await self.send(f"你的身份: {self.role.name}")

    async def interact(self, game: "Game") -> None:
        raise NotImplementedError

    async def vote(self, players: "PlayerSet") -> "Player | None":
        players = players.exclude(self)
        await self.send(
            f"请选择需要投票的玩家:\n{players.show()}"
            "\n\n发送编号选择玩家\n发送 “/stop” 弃票"
        )

        while True:
            text = (await self.receive()).extract_plain_text()
            if text == "/stop":
                return None
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("输入错误，请发送编号选择玩家")

        player = players[selected]
        await self.send(f"投票的玩家: {player.name}")
        return player

    def kill(self) -> None:
        self.alive = False

    @property
    def user_id(self) -> str:
        return self.user.id


class 狼人(Player):
    role: ClassVar[Role] = Role.狼人

    @override
    async def interact(self, game: "Game") -> None:
        players = game.players.alive()
        partners = players.select(Role.狼人).exclude(self)

        # 避免阻塞
        def broadcast(msg: str | UniMessage):
            return asyncio.create_task(partners.broadcast(msg))

        await self.send(
            "你的队友:\n"
            + "\n".join(p.name for p in partners)
            + "\n所有私聊消息将被转发至队友"
            + "\n\n请选择需要杀死的玩家:\n"
            + players.show()
            + "\n\n发送 “/kill <编号>” 选择玩家"
            + "\n发送 “/stop” 结束回合"
        )

        selected: int | None = None
        finished: bool = False
        while selected is None or not finished:
            input = await self.receive()
            text = input.extract_plain_text()
            index = check_index(text.removeprefix("/kill").strip(), len(players))
            if index is not None:
                selected = index - 1
                msg = f"当前选择玩家: {players[selected].name}"
                await self.send(msg)
                broadcast(f"队友 {self.name} {msg}")
            if text == "/stop":
                if selected is None:
                    finished = True
                    await self.send("你已结束当前回合")
                    broadcast(f"队友 {self.name} 结束当前回合")
                else:
                    await self.send("当前未选择玩家，无法结束回合")
            msg = UniMessage.text(f"队友 {self.name}:\n") + input
            broadcast(msg)

        self.selected = players[selected]


class 预言家(Player):
    role: ClassVar[Role] = Role.预言家

    @override
    async def interact(self, game: "Game") -> None:
        players = game.players.alive().exclude(self)
        await self.send(
            f"请选择需要查验身份的玩家:\n{players.show()}\n\n发送编号选择玩家"
        )

        while True:
            text = (await self.receive()).extract_plain_text()
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("输入错误，请发送编号选择玩家")

        player = players[selected]
        result = "狼人" if player.role == Role.狼人 else "好人"
        await self.send(f"玩家 {player.name} 的阵营是『{result}』")


class 女巫(Player):
    role: ClassVar[Role] = Role.女巫
    antidote: int = 1
    poison: int = 1

    @staticmethod
    def potion_str(potion: int) -> str:
        return "解药" if potion == 1 else "毒药"

    async def select_potion(self, players: "PlayerSet") -> int:
        await self.send(
            f"你当前拥有以下药水:\n1.解药x{self.antidote} | 2.毒药x{self.poison}"
            + "\n发送编号选择药水"
            + "\n发送 “/list” 查看玩家列表"
            + "\n发送 “/stop” 结束回合(不使用药水)"
        )

        while True:
            text = (await self.receive()).extract_plain_text()
            if text == "/list":
                await self.send(players.show())
                continue
            elif text == "/stop":
                await self.send("你选择了取消，回合结束")
                return 0
            selected = check_index(text, 2)
            match (selected, self.antidote, self.poison):
                case (None, _, _):
                    await self.send("输入错误，请发送编号选择药水")
                case (1, 0, _):
                    await self.send("选择错误: 你已经用过解药了")
                case (2, _, 0):
                    await self.send("选择错误: 你已经用过解药了")
                case _:
                    return selected

    async def select_player(self, potion: int, players: "PlayerSet") -> Player | None:
        await self.send(
            f"当前选择药水: {self.potion_str(potion)}\n\n"
            f"{players.show()}\n\n发送编号选择玩家\n发送 “/back” 回退到选择药水"
        )

        while True:
            text = (await self.receive()).extract_plain_text()
            if text == "/back":
                return None
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("输入错误，请发送编号选择玩家")

        return players[selected]

    @override
    async def interact(self, game: "Game") -> None:
        if game.state.killed is not None:
            await self.send(f"今晚 {game.state.killed.name} 被刀了")
        else:
            await self.send("今晚没有人被刀")

        if not self.antidote and not self.poison:
            await self.send("你没有可以使用的药水，回合结束")
            game.state.potion = (None, (False, False))
            return

        players = game.players.alive()
        potion = await self.select_potion(players)
        if potion == 0:
            return

        while (player := await self.select_player(potion, players)) is None:
            potion = await self.select_potion(players)
            if potion == 0:
                return

        self.selected = player
        game.state.potion = (player, (potion == 1, potion == 2))
        await self.send(
            f"当前回合选择对玩家 {player.name} 使用 {self.potion_str(potion)}"
            "\n回合结束"
        )

        if potion == 1:
            self.antidote = 0
        else:
            self.poison = 0


class 猎人(Player):
    role: ClassVar[Role] = Role.猎人

    @override
    async def interact(self, game: "Game") -> None:
        players = game.players.alive().exclude(self)
        await self.send(
            "请选择需要射杀的玩家:\n"
            + players.show()
            + "\n\n发送编号选择玩家"
            + "\n发送 “/stop” 取消技能"  # 真的会有人选这个吗
        )

        while True:
            text = (await self.receive()).extract_plain_text()
            if text == "/stop":
                await self.send("已取消技能")  # 不是哥们
                return
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("输入错误，请发送编号选择玩家")

        self.selected = players[selected]
        game.state.shoot = players[selected]
        await self.send(f"选择射杀的玩家: {self.selected.name}")


class 守卫(Player):
    role: ClassVar[Role] = Role.守卫

    @override
    async def interact(self, game: "Game") -> None:
        players = game.players.alive().exclude(self)
        await self.send(
            f"请选择需要保护的玩家:\n{players.show()}"
            "\n\n发送编号选择玩家\n发送 “/stop” 结束回合"
        )

        while True:
            text = (await self.receive()).extract_plain_text()
            if text == "/stop":
                await self.send("你选择了取消，回合结束")
                return
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                if players[selected] is self.selected:
                    await self.send("守卫不能连续两晚保护同一目标")
                    continue
                break
            await self.send("输入错误，请发送编号选择玩家")

        game.state.protected = self.selected = players[selected]
        await self.send(f"本回合保护的玩家: {self.selected.name}")


class 平民(Player):
    role: ClassVar[Role] = Role.平民

    @override
    async def interact(self, game: "Game") -> None:
        return


class PlayerSet(set[Player]):
    @property
    def size(self) -> int:
        return len(self)

    def alive(self) -> "PlayerSet":
        return PlayerSet(p for p in self if p.alive)

    def dead(self) -> "PlayerSet":
        return PlayerSet(p for p in self if not p.alive)

    def include(self, *types: Role | Player) -> "PlayerSet":
        return PlayerSet(p for p in self if p in types or p.role in types)

    def select(self, *types: Role | Player) -> "PlayerSet":
        return self.include(*types)

    def exclude(self, *types: Role | Player) -> "PlayerSet":
        return PlayerSet(p for p in self if p not in types and p.role not in types)

    def sorted(self) -> list[Player]:
        return sorted(self, key=lambda p: p.user_id)

    async def interact(self, game: "Game") -> None:
        await asyncio.gather(*[p.interact(game) for p in self.alive()])

    def player_selected(self) -> "PlayerSet":
        return PlayerSet(p.selected for p in self.alive() if p.selected is not None)

    async def broadcast(self, message: str | UniMessage) -> None:
        await asyncio.gather(*[p.send(message) for p in self])

    async def wait_group_stop(self, group_id: str, timeout: float):  # noqa: ASYNC109
        async def wait(p: Player):
            while True:
                msg = await store.fetch(p.user_id, group_id)
                if msg.extract_plain_text() == "/stop":
                    break

        with contextlib.suppress(TimeoutError):
            async with asyncio.timeouts.timeout(timeout):
                await asyncio.gather(*[wait(p) for p in self])

    def show(self):
        return "\n".join(f"{i}. {p.name}" for i, p in enumerate(self.sorted(), 1))

    def __getitem__(self, __index: int) -> Player:
        return self.sorted()[__index]
