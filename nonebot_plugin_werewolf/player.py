from __future__ import annotations

import asyncio
import asyncio.timeouts
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, TypeVar, final
from typing_extensions import override

from nonebot.adapters import Bot
from nonebot_plugin_alconna.uniseg import Receipt, Target, UniMessage

from .constant import KillReason, Role, RoleGroup, role_name_conv
from .utils import InputStore, check_index

if TYPE_CHECKING:
    from .game import Game
    from .player_set import PlayerSet


P = TypeVar("P", bound=type["Player"])
PLAYER_CLASS: dict[Role, type[Player]] = {}


def register_role(role: Role, role_group: RoleGroup, /):
    def decorator(cls: P, /) -> P:
        cls.role = role
        cls.role_group = role_group
        PLAYER_CLASS[role] = cls
        return cls

    return decorator


@dataclass
class KillInfo:
    reason: KillReason
    killers: PlayerSet


class Player:
    role: ClassVar[Role]
    role_group: ClassVar[RoleGroup]

    bot: Bot
    game: Game
    user: Target
    name: str
    alive: bool = True
    killed: bool = False
    kill_info: KillInfo | None = None
    selected: Player | None = None

    @final
    def __init__(self, bot: Bot, game: Game, user: Target, name: str) -> None:
        self.bot = bot
        self.game = game
        self.user = user
        self.name = name

    @final
    @classmethod
    def new(
        cls,
        role: Role,
        bot: Bot,
        game: Game,
        user: Target,
        name: str,
    ) -> Player:
        if role not in PLAYER_CLASS:
            raise ValueError(f"Unexpected role: {role!r}")

        return PLAYER_CLASS[role](bot, game, user, name)

    def __repr__(self) -> str:
        return f"<{self.role_name}: user={self.user} alive={self.alive}>"

    @property
    def user_id(self) -> str:
        return self.user.id

    @property
    def role_name(self) -> str:
        return role_name_conv[self.role]

    @final
    async def send(self, message: str | UniMessage) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        return await message.send(target=self.user, bot=self.bot)

    @final
    async def receive(self, prompt: str | UniMessage | None = None) -> UniMessage:
        if prompt:
            await self.send(prompt)
        return await InputStore.fetch(self.user.id)

    @final
    async def receive_text(self) -> str:
        return (await self.receive()).extract_plain_text()

    async def interact(self) -> None:
        return

    async def notify_role(self) -> None:
        await self.send(f"你的身份: {self.role_name}")

    async def kill(
        self,
        reason: KillReason,
        *killers: Player,
    ) -> bool:
        from .player_set import PlayerSet

        self.alive = False
        self.kill_info = KillInfo(reason, PlayerSet(killers))
        return True

    async def post_kill(self) -> None:
        self.killed = True

    async def vote(self, players: PlayerSet) -> tuple[Player, Player] | None:
        await self.send(
            f"请选择需要投票的玩家:\n{players.show()}"
            "\n\n发送编号选择玩家\n发送 “/stop” 弃票"
        )

        while True:
            text = await self.receive_text()
            if text == "/stop":
                await self.send("你选择了弃票")
                return None
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("输入错误，请发送编号选择玩家")

        player = players[selected]
        await self.send(f"投票的玩家: {player.name}")
        return self, player


class CanShoot(Player):
    @override
    async def post_kill(self) -> None:
        if self.kill_info and self.kill_info.reason == KillReason.Poison:
            await self.send("你昨晚被女巫毒杀，无法使用技能")
            return await super().post_kill()

        await self.game.send(
            UniMessage.text(f"{self.role_name} ")
            .at(self.user_id)
            .text(f" 死了\n请{self.role_name}决定击杀目标...")
        )

        self.game.state.shoot = (None, None)
        shoot = await self.shoot()

        if shoot is not None:
            self.game.state.shoot = (self, shoot)
            await self.send(
                UniMessage.text(f"{self.role_name} ")
                .at(self.user_id)
                .text(" 射杀了玩家 ")
                .at(shoot.user_id)
            )
            await shoot.kill(KillReason.Shoot, self)
        else:
            await self.send(f"{self.role_name}选择了取消技能")
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
            text = await self.receive_text()
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


@register_role(Role.Werewolf, RoleGroup.Werewolf)
class Werewolf(Player):
    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        partners = self.game.players.alive().select(RoleGroup.Werewolf).exclude(self)
        if partners:
            await self.send(
                "你的队友:\n"
                + "\n".join(f"  {p.role_name}: {p.name}" for p in partners)
            )

    @override
    async def interact(self) -> None:
        players = self.game.players.alive()
        partners = players.select(RoleGroup.Werewolf).exclude(self)

        # 避免阻塞
        def broadcast(msg: str | UniMessage):
            return asyncio.create_task(partners.broadcast(msg))

        msg = UniMessage()
        if partners:
            msg = (
                msg.text("你的队友:\n")
                .text("\n".join(f"  {p.role_name}: {p.name}" for p in partners))
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
                await self.send(f"{msg}\n发送 “/stop” 结束回合")
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


@register_role(Role.WolfKing, RoleGroup.Werewolf)
class WolfKing(CanShoot, Werewolf):
    pass


@register_role(Role.Prophet, RoleGroup.GoodGuy)
class Prophet(Player):
    @override
    async def interact(self) -> None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            UniMessage.text("请选择需要查验身份的玩家:\n")
            .text(players.show())
            .text("\n\n发送编号选择玩家")
        )

        while True:
            text = await self.receive_text()
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("输入错误，请发送编号选择玩家")

        player = players[selected]
        result = role_name_conv[player.role_group]
        await self.send(f"玩家 {player.name} 的阵营是『{result}』")


@register_role(Role.Witch, RoleGroup.GoodGuy)
class Witch(Player):
    antidote: int = 1
    poison: int = 1

    def set_state(
        self,
        *,
        antidote: Player | None = None,
        posion: Player | None = None,
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
            self.selected = None
            self.game.state.potion = (None, (False, False))

    async def handle_killed(self) -> bool:
        msg = UniMessage()
        if (killed := self.game.state.killed) is not None:
            msg.text(f"今晚 {killed.name} 被刀了\n\n")
        else:
            await self.send("今晚没有人被刀")
            return False

        if not self.antidote:
            await self.send(msg.text("你已经用过解药了"))
            return False

        await self.send(msg.text("使用解药请发送 “1”\n不使用解药请发送 “/stop”"))

        while True:
            text = await self.receive_text()
            if text == "1":
                self.antidote = 0
                self.set_state(antidote=killed)
                await self.send(f"你对 {killed.name} 使用了解药，回合结束")
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
            text = await self.receive_text()
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


@register_role(Role.Hunter, RoleGroup.GoodGuy)
class Hunter(CanShoot, Player):
    pass


@register_role(Role.Guard, RoleGroup.GoodGuy)
class Guard(Player):
    @override
    async def interact(self) -> None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            UniMessage.text(f"请选择需要保护的玩家:\n{players.show()}")
            .text("\n\n发送编号选择玩家")
            .text("\n发送 “/stop” 结束回合")
        )

        while True:
            text = await self.receive_text()
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


@register_role(Role.Idiot, RoleGroup.GoodGuy)
class Idiot(Player):
    voted: bool = False

    @override
    async def kill(
        self,
        reason: KillReason,
        *killers: Player,
    ) -> bool:
        if reason == KillReason.Vote and not self.voted:
            self.voted = True
            await self.game.send(
                UniMessage.at(self.user_id)
                .text(" 的身份是白痴\n")
                .text("免疫本次投票放逐，且接下来无法参与投票")
            )
            return False
        return await super().kill(reason, *killers)

    @override
    async def vote(self, players: PlayerSet) -> tuple[Player, Player] | None:
        if self.voted:
            await self.send("你已经发动过白痴身份的技能，无法参与本次投票")
            return None
        return await super().vote(players)


@register_role(Role.Civilian, RoleGroup.GoodGuy)
class Civilian(Player):
    pass
