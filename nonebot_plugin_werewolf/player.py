import asyncio
import asyncio.timeouts
import contextlib
from typing import TYPE_CHECKING, ClassVar, Literal
from typing_extensions import final, override

from nonebot.adapters import Bot
from nonebot_plugin_alconna.uniseg import Receipt, Target, UniMessage

from .constant import KillReason, Role, RoleGroup
from .input_store import store
from .utils import check_index

if TYPE_CHECKING:
    from .game import Game


class Player:
    bot: Bot
    user: Target
    name: str
    role: ClassVar[Role]
    role_group: ClassVar[RoleGroup]
    game: "Game"
    alive: bool = True
    kill_reason: KillReason | None = None
    selected: "Player | None" = None

    def __init__(self, bot: Bot, game: "Game", user: Target, name: str) -> None:
        assert self.__class__ is not Player
        self.bot = bot
        self.user = user
        self.name = name
        self.game = game

    @classmethod
    def new(
        cls,
        bot: Bot,
        game: "Game",
        user: Target,
        name: str,
        role: Role,
    ) -> "Player":
        for c in cls.__subclasses__():
            if c.role == role:
                return c(bot, game, user, name)
        else:
            raise ValueError(f"Unexpected role: {role!r}")

    def __repr__(self) -> str:
        return f"<{self.role.name}: user={self.user} alive={self.alive}>"

    async def send(self, message: str | UniMessage) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        return await message.send(target=self.user, bot=self.bot)

    async def receive(self, prompt: str | UniMessage | None = None) -> UniMessage:
        if prompt:
            await self.send(prompt)
        return await store.fetch(self.user.id)

    async def interact(self) -> None:
        raise NotImplementedError

    async def notify_role(self) -> None:
        await self.send(f"你的身份: {self.role.name}")

    async def kill(self, reason: KillReason) -> bool:
        self.alive = False
        self.kill_reason = reason
        return True

    async def post_kill(self) -> None:
        return

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

    @property
    def user_id(self) -> str:
        return self.user.id


class CanShoot(Player):
    @override
    async def post_kill(self) -> None:
        if self.kill_reason == KillReason.Poison:
            await self.send("你昨晚被女巫毒杀，无法使用技能")
            return await super().post_kill()

        await self.game.send(
            UniMessage.text(f"{self.role.name} ")
            .at(self.user_id)
            .text(f" 死了\n请{self.role.name}决定击杀目标...")
        )

        self.game.state.shoot = (None, None)
        shoot = await self.shoot()
        if shoot is not None:
            self.game.state.shoot = (self, shoot)

        if shoot is not None:
            await self.send(
                UniMessage.text(f"{self.role.name} ")
                .at(self.user_id)
                .text(" 射杀了玩家 ")
                .at(shoot.user_id)
            )
            await shoot.kill(KillReason.Shoot)
            await shoot.post_kill()
        else:
            await self.send(f"{self.role.name}选择了取消技能")
        return await super().post_kill()

    async def shoot(self) -> Player | None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            "请选择需要射杀的玩家:\n"
            + players.show()
            + "\n\n发送编号选择玩家"
            + "\n发送 “/stop” 取消技能"
        )

        while True:
            text = (await self.receive()).extract_plain_text()
            if text == "/stop":
                await self.send("已取消技能")
                return
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("输入错误，请发送编号选择玩家")

        await self.send(f"选择射杀的玩家: {players[selected].name}")
        return players[selected]


class 狼人(Player):
    role: ClassVar[Role] = Role.狼人
    role_group: ClassVar[RoleGroup] = RoleGroup.狼人

    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        partners = self.game.players.alive().select(RoleGroup.狼人).exclude(self)
        msg = "你的队友:\n" + "\n".join(f"  {p.role.name}: {p.name}" for p in partners)
        await self.send(msg)

    @override
    async def interact(self) -> None:
        players = self.game.players.alive()
        partners = players.select(RoleGroup.狼人).exclude(self)

        # 避免阻塞
        def broadcast(msg: str | UniMessage):
            return asyncio.create_task(partners.broadcast(msg))

        msg = UniMessage()
        if partners:
            msg = (
                msg.text("你的队友:\n")
                .text("\n".join(f"  {p.role.name}: {p.name}" for p in partners))
                .text("\n所有私聊消息将被转发至队友\n\n")
            )
        await self.send(
            msg.text("请选择今晚的目标:\n")
            .text(players.show())
            .text("\n\n发送 “/kill <编号>” 选择玩家")
            .text("\n发送 “/stop” 结束回合")
            .text("\n\n限时2分钟，意见未统一将空刀")
        )

        selected = None
        finished = False
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
            broadcast(UniMessage.text(f"队友 {self.name}:\n") + input)

        self.selected = players[selected]


class 狼王(CanShoot, 狼人):
    role: ClassVar[Role] = Role.狼王
    role_group: ClassVar[RoleGroup] = RoleGroup.狼人


@final
class 预言家(Player):
    role: ClassVar[Role] = Role.预言家
    role_group: ClassVar[RoleGroup] = RoleGroup.好人

    @override
    async def interact(self) -> None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            UniMessage.text("请选择需要查验身份的玩家:\n")
            .text(players.show())
            .text("\n\n发送编号选择玩家")
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


@final
class 女巫(Player):
    role: ClassVar[Role] = Role.女巫
    role_group: ClassVar[RoleGroup] = RoleGroup.好人
    antidote: int = 1
    poison: int = 1

    @staticmethod
    def potion_str(potion: Literal[1, 2]) -> str:
        return "解药" if potion == 1 else "毒药"

    async def select_potion(self, players: "PlayerSet") -> Literal[1, 2] | None:
        await self.send(
            UniMessage.text("你当前拥有以下药水:")
            .text(f"\n1.解药x{self.antidote} | 2.毒药x{self.poison}")
            .text("\n发送编号选择药水")
            .text("\n发送 “/list” 查看玩家列表")
            .text("\n发送 “/stop” 结束回合(不使用药水)")
        )

        while True:
            text = (await self.receive()).extract_plain_text()
            if text == "/list":
                await self.send(players.show())
                continue
            elif text == "/stop":
                await self.send("你选择了取消，回合结束")
                return
            selected = check_index(text, 2)
            match (selected, self.antidote, self.poison):
                case (None, _, _):
                    await self.send("输入错误: 请发送编号选择药水")
                case (1, 0, _):
                    await self.send("选择错误: 你已经用过解药了")
                case (2, _, 0):
                    await self.send("选择错误: 你已经用过毒药了")
                case (1, 1, _) | (2, _, 1):
                    return selected
                case x:
                    await self.send(f"未知错误: {x}")

    async def select_player(
        self,
        potion: Literal[1, 2],
        players: "PlayerSet",
    ) -> Player | None:
        await self.send(
            UniMessage.text(f"当前选择药水: {self.potion_str(potion)}\n\n")
            .text(players.show())
            .text("\n\n发送编号选择玩家")
            .text("\n发送 “/back” 回退到选择药水")
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
    async def interact(self) -> None:
        if self.game.state.killed is not None:
            await self.send(f"今晚 {self.game.state.killed.name} 被刀了")
        else:
            await self.send("今晚没有人被刀")

        if not self.antidote and not self.poison:
            await self.send("你没有可以使用的药水，回合结束")
            self.game.state.potion = (None, (False, False))
            return

        players = self.game.players.alive()
        potion = await self.select_potion(players)
        if potion is None:
            return

        while (player := await self.select_player(potion, players)) is None:
            potion = await self.select_potion(players)
            if potion is None:
                return

        self.selected = player
        self.game.state.potion = (player, (potion == 1, potion == 2))
        await self.send(
            UniMessage.text(f"当前回合选择对玩家 {player.name}")
            .text(f" 使用 {self.potion_str(potion)}")
            .text("\n回合结束")
        )

        if potion == 1:
            self.antidote = 0
        else:
            self.poison = 0


@final
class 猎人(CanShoot, Player):
    role: ClassVar[Role] = Role.猎人
    role_group: ClassVar[RoleGroup] = RoleGroup.好人

    @override
    async def interact(self) -> None:
        return


@final
class 守卫(Player):
    role: ClassVar[Role] = Role.守卫
    role_group: ClassVar[RoleGroup] = RoleGroup.好人

    @override
    async def interact(self) -> None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            UniMessage.text(f"请选择需要保护的玩家:\n{players.show()}")
            .text("\n\n发送编号选择玩家")
            .text("\n发送 “/stop” 结束回合")
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

        self.game.state.protected = self.selected = players[selected]
        await self.send(f"本回合保护的玩家: {self.selected.name}")


@final
class 白痴(Player):
    role: ClassVar[Role] = Role.白痴
    role_group: ClassVar[RoleGroup] = RoleGroup.好人
    voted: bool = False

    @override
    async def kill(self, reason: KillReason) -> bool:
        if reason == KillReason.Vote and not self.voted:
            self.voted = True
            await self.game.send(
                UniMessage.at(self.user_id)
                .text(" 的身份是白痴\n")
                .text("免疫本次投票放逐，且接下来无法参与投票")
            )
            return False
        return await super().kill(reason)

    @override
    async def vote(self, players: "PlayerSet") -> "Player | None":
        if self.voted:
            await self.send("你已经发动过白痴身份的技能，无法参与本次投票")
            return None
        return await super().vote(players)

    @override
    async def interact(self) -> None:
        return


@final
class 平民(Player):
    role: ClassVar[Role] = Role.平民
    role_group: ClassVar[RoleGroup] = RoleGroup.好人

    @override
    async def interact(self) -> None:
        return


class PlayerSet(set[Player]):
    @property
    def size(self) -> int:
        return len(self)

    def alive(self) -> "PlayerSet":
        return PlayerSet(p for p in self if p.alive)

    def dead(self) -> "PlayerSet":
        return PlayerSet(p for p in self if not p.alive)

    def include(self, *types: Player | Role | RoleGroup) -> "PlayerSet":
        return PlayerSet(
            player
            for player in self
            if (player in types or player.role in types or player.role_group in types)
        )

    def select(self, *types: Player | Role | RoleGroup) -> "PlayerSet":
        return self.include(*types)

    def exclude(self, *types: Player | Role | RoleGroup) -> "PlayerSet":
        return PlayerSet(
            player
            for player in self
            if (
                player not in types
                and player.role not in types
                and player.role_group not in types
            )
        )

    def player_selected(self) -> "PlayerSet":
        return PlayerSet(p.selected for p in self.alive() if p.selected is not None)

    def sorted(self) -> list[Player]:
        return sorted(self, key=lambda p: p.user_id)

    async def interact(self, timeout: float = 60) -> None:  # noqa: ASYNC109
        async with asyncio.timeouts.timeout(timeout):
            await asyncio.gather(*[p.interact() for p in self.alive()])

    async def post_kill(self) -> None:
        await asyncio.gather(*[p.post_kill() for p in self])

    async def broadcast(self, message: str | UniMessage) -> None:
        await asyncio.gather(*[p.send(message) for p in self])

    async def wait_group_stop(self, group_id: str, timeout: float) -> None:  # noqa: ASYNC109
        async def wait(p: Player):
            while True:
                msg = await store.fetch(p.user_id, group_id)
                if msg.extract_plain_text() == "/stop":
                    break

        with contextlib.suppress(TimeoutError):
            async with asyncio.timeouts.timeout(timeout):
                await asyncio.gather(*[wait(p) for p in self])

    def show(self) -> str:
        return "\n".join(f"{i}. {p.name}" for i, p in enumerate(self.sorted(), 1))

    def __getitem__(self, __index: int) -> Player:
        return self.sorted()[__index]
