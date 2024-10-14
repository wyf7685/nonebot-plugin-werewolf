from __future__ import annotations

import asyncio
import functools
import weakref
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, TypeVar, final

from nonebot.log import logger
from nonebot.utils import escape_tag
from nonebot_plugin_alconna.uniseg import Receipt, Target, UniMessage

from ..constant import KillReason, Role, RoleGroup, role_emoji, role_name_conv
from ..utils import InputStore, check_index

if TYPE_CHECKING:
    from collections.abc import Callable

    from nonebot.adapters import Bot

    from ..game import Game
    from ..player_set import PlayerSet


P = TypeVar("P", bound=type["Player"])


@dataclass
class KillInfo:
    reason: KillReason
    killers: PlayerSet


class Player:
    __player_class: ClassVar[dict[Role, type[Player]]] = {}
    role: ClassVar[Role]
    role_group: ClassVar[RoleGroup]

    __user: Final[Target]
    __game_ref: Final[weakref.ReferenceType[Game]]
    bot: Final[Bot]
    name: Final[str]
    alive: bool = True
    killed: Final[asyncio.Event]
    kill_info: KillInfo | None = None
    selected: Player | None = None

    @final
    def __init__(self, bot: Bot, game: Game, user_id: str, name: str) -> None:
        self.__user = Target(
            user_id,
            private=True,
            self_id=bot.self_id,
            adapter=bot.adapter.get_name(),
        )
        self.__game_ref = weakref.ref(game)
        self.bot = bot
        self.name = name
        self.killed = asyncio.Event()

    @classmethod
    def register_role(cls, role: Role, role_group: RoleGroup, /) -> Callable[[P], P]:
        def decorator(c: P, /) -> P:
            c.role = role
            c.role_group = role_group
            cls.__player_class[role] = c
            return c

        return decorator

    @final
    @classmethod
    def new(cls, role: Role, bot: Bot, game: Game, user_id: str, name: str) -> Player:
        if role not in cls.__player_class:
            raise ValueError(f"Unexpected role: {role!r}")

        return cls.__player_class[role](bot, game, user_id, name)

    def __repr__(self) -> str:
        return (
            f"<Player {self.role_name}: user={self.user_id!r} "
            f"name={self.name!r} alive={self.alive}>"
        )

    @property
    def game(self) -> Game:
        if game := self.__game_ref():
            return game
        raise ValueError("Game not exist")

    @functools.cached_property
    def user_id(self) -> str:
        return self.__user.id

    @functools.cached_property
    def role_name(self) -> str:
        return role_name_conv[self.role]

    @final
    def _log(self, text: str) -> None:
        text = text.replace("\n", "\\n")
        logger.opt(colors=True).info(
            f"<b><e>{self.game.group.id}</e></b> | "
            f"[<b><m>{self.role_name}</m></b>] "
            f"<y>{self.name}</y>(<b><e>{self.user_id}</e></b>) | "
            f"{text}",
        )

    @final
    async def send(self, message: str | UniMessage) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        self._log(f"<g>Send</g> | {escape_tag(str(message))}")
        return await message.send(target=self.__user, bot=self.bot)

    @final
    async def receive(self, prompt: str | UniMessage | None = None) -> UniMessage:
        if prompt:
            await self.send(prompt)

        result = await InputStore.fetch(self.user_id)
        self._log(f"<y>Recv</y> | {escape_tag(str(result))}")
        return result

    @final
    async def receive_text(self) -> str:
        return (await self.receive()).extract_plain_text()

    async def interact(self) -> None:
        return

    async def notify_role(self) -> None:
        await self.send(f"⚙️你的身份: {role_emoji[self.role]}{self.role_name}")

    async def kill(self, reason: KillReason, *killers: Player) -> bool:
        from ..player_set import PlayerSet

        self.alive = False
        self.kill_info = KillInfo(reason=reason, killers=PlayerSet(killers))
        return True

    async def post_kill(self) -> None:
        self.killed.set()

    async def vote(self, players: PlayerSet) -> Player | None:
        await self.send(
            f"💫请选择需要投票的玩家:\n{players.show()}"
            "\n\n🗳️发送编号选择玩家\n❌发送 “/stop” 弃票"
        )

        while True:
            text = await self.receive_text()
            if text == "/stop":
                await self.send("⚠️你选择了弃票")
                return None
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("⚠️输入错误: 请发送编号选择玩家")

        vote = players[selected]
        await self.send(f"🔨投票的玩家: {vote.name}")
        return vote
