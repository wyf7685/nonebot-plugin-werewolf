import asyncio
import asyncio.timeouts
import contextlib
from typing import TYPE_CHECKING, ClassVar, Literal
from typing_extensions import override

from nonebot.adapters import Bot
from nonebot_plugin_alconna.uniseg import Receipt, Target, UniMessage

from .constant import KillReason, Role, RoleGroup
from .utils import InputStore, check_index

if TYPE_CHECKING:
    from .game import Game

PlayerClass: dict[Role, type["Player"]] = {}


def register_role(cls: type["Player"]) -> type["Player"]:
    PlayerClass[cls.role] = cls
    return cls


class Player:
    role: ClassVar[Role]
    role_group: ClassVar[RoleGroup]

    bot: Bot
    game: "Game"
    user: Target
    name: str
    alive: bool = True
    killed: bool = False
    kill_reason: KillReason | None = None
    selected: "Player | None" = None

    @classmethod
    def new(
        cls,
        role: Role,
        bot: Bot,
        game: "Game",
        user: Target,
        name: str,
    ) -> "Player":
        if role not in PlayerClass:
            raise ValueError(f"Unexpected role: {role!r}")

        player = PlayerClass[role]()
        player.bot = bot
        player.game = game
        player.user = user
        player.name = name
        player.game = game
        return player

    def __repr__(self) -> str:
        return f"<{self.role.name}: user={self.user} alive={self.alive}>"

    async def send(self, message: str | UniMessage) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        return await message.send(target=self.user, bot=self.bot)

    async def receive(self, prompt: str | UniMessage | None = None) -> UniMessage:
        if prompt:
            await self.send(prompt)
        return await InputStore.fetch(self.user.id)

    async def interact(self) -> None:
        return

    async def notify_role(self) -> None:
        await self.send(f"你的身份: {self.role.name}")

    async def kill(self, reason: KillReason) -> bool:
        self.alive = False
        self.kill_reason = reason
        return True

    async def post_kill(self) -> None:
        self.killed = True

    async def vote(self, players: "PlayerSet") -> "Player | None":
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


@register_role
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
            .text("\n\n发送编号选择玩家")
            .text("\n发送 “/stop” 结束回合")
            .text("\n\n意见未统一将空刀")
        )

        selected = None
        finished = False
        while selected is None or not finished:
            input = await self.receive()
            text = input.extract_plain_text()
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                msg = f"当前选择玩家: {players[selected].name}"
                await self.send(msg)
                broadcast(f"队友 {self.name} {msg}")
            if text == "/stop":
                if selected is not None:
                    finished = True
                    await self.send("你已结束当前回合")
                    broadcast(f"队友 {self.name} 结束当前回合")
                else:
                    await self.send("当前未选择玩家，无法结束回合")
            broadcast(UniMessage.text(f"队友 {self.name}:\n") + input)

        self.selected = players[selected]


@register_role
class 狼王(CanShoot, 狼人):
    role: ClassVar[Role] = Role.狼王
    role_group: ClassVar[RoleGroup] = RoleGroup.狼人


@register_role
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


@register_role
class 女巫(Player):
    role: ClassVar[Role] = Role.女巫
    role_group: ClassVar[RoleGroup] = RoleGroup.好人
    antidote: int = 1
    poison: int = 1

    def set_state(
        self, *, antidote: Player | None = None, posion: Player | None = None
    ):
        if antidote is not None:
            self.antidote = 0
            self.selected = antidote
            self.game.state.potion = (antidote, (True, False))
        elif posion is not None:
            self.poison = 0
            self.selected = posion
            self.game.state.potion = (posion, (False, True))
        else:
            self.game.state.potion = (None, (False, False))

    @staticmethod
    def potion_str(potion: Literal[1, 2]) -> str:
        return "解药" if potion == 1 else "毒药"

    async def handle_killed(self) -> bool:
        if self.game.state.killed is not None:
            await self.send(f"今晚 {self.game.state.killed.name} 被刀了")
        else:
            await self.send("今晚没有人被刀")
            return False

        if not self.antidote:
            await self.send("你已经用过解药了")
            return False

        await self.send("使用解药请发送 “1”\n不使用解药请发送 “/stop”")

        while True:
            text = (await self.receive()).extract_plain_text()
            if text == "1":
                self.antidote = 0
                self.set_state(antidote=self.game.state.killed)
                await self.send(
                    f"你对 {self.game.state.killed.name} 使用了解药，回合结束"
                )
                return True
            elif text == "/stop":
                return False
            else:
                await self.send("输入错误: 请输入 “1” 或 “/stop”")

    @override
    async def interact(self) -> None:
        if await self.handle_killed():
            return

        if not self.poison:
            await self.send("你没有可以使用的药水，回合结束")
            self.set_state()
            return

        players = self.game.players.alive()
        await self.send(
            UniMessage.text("你有一瓶毒药\n")
            .text("玩家列表:\n")
            .text(players.show())
            .text("\n\n发送玩家编号使用毒药")
            .text("\n发送 “/stop” 结束回合(不使用药水)")
        )

        while True:
            text = (await self.receive()).extract_plain_text().strip()
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            elif text == "/stop":
                await self.send("你选择不使用毒药，回合结束")
                self.set_state()
                return
            else:
                await self.send("输入错误: 请发送玩家编号或 “/stop”")

        self.poison = 0
        self.selected = player = players[selected]
        self.set_state(posion=player)
        await self.send(f"当前回合选择对玩家 {player.name} 使用毒药\n回合结束")


@register_role
class 猎人(CanShoot, Player):
    role: ClassVar[Role] = Role.猎人
    role_group: ClassVar[RoleGroup] = RoleGroup.好人


@register_role
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


@register_role
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


@register_role
class 平民(Player):
    role: ClassVar[Role] = Role.平民
    role_group: ClassVar[RoleGroup] = RoleGroup.好人


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

    async def interact(self, timeout_secs: float = 60) -> None:
        async with asyncio.timeouts.timeout(timeout_secs):
            await asyncio.gather(*[p.interact() for p in self.alive()])

    async def vote(self, timeout_secs: float = 60) -> list[Player]:
        async def vote(player: Player) -> "Player | None":
            try:
                async with asyncio.timeouts.timeout(timeout_secs):
                    return await player.vote(self)
            except TimeoutError:
                await player.send("投票超时，将自动弃票")

        return [
            p
            for p in await asyncio.gather(*[vote(p) for p in self.alive()])
            if p is not None
        ]

    async def post_kill(self) -> None:
        await asyncio.gather(*[p.post_kill() for p in self])

    async def broadcast(self, message: str | UniMessage) -> None:
        await asyncio.gather(*[p.send(message) for p in self])

    async def wait_group_stop(self, group_id: str, timeout_secs: float) -> None:
        async def wait(p: Player):
            while True:
                msg = await InputStore.fetch(p.user_id, group_id)
                if msg.extract_plain_text() == "/stop":
                    break

        with contextlib.suppress(TimeoutError):
            async with asyncio.timeouts.timeout(timeout_secs):
                await asyncio.gather(*[wait(p) for p in self])

    def show(self) -> str:
        return "\n".join(f"{i}. {p.name}" for i, p in enumerate(self.sorted(), 1))

    def __getitem__(self, __index: int) -> Player:
        return self.sorted()[__index]
