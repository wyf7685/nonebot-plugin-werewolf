import functools
import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, Final, TypeVar, final

import anyio
import nonebot
from nonebot.adapters import Bot
from nonebot.utils import escape_tag
from nonebot_plugin_alconna.uniseg import Receipt, Target, UniMessage
from nonebot_plugin_uninfo import SceneType

from ..constant import STOP_COMMAND, STOP_COMMAND_PROMPT, role_emoji, role_name_conv
from ..models import KillInfo, KillReason, Role, RoleGroup
from ..utils import InputStore, check_index, link

if TYPE_CHECKING:
    from ..game import Game
    from ..player_set import PlayerSet


_P = TypeVar("_P", bound=type["Player"])

logger = nonebot.logger.opt(colors=True)


class Player:
    __player_class: ClassVar[dict[Role, type["Player"]]] = {}
    role: ClassVar[Role]
    role_group: ClassVar[RoleGroup]

    bot: Final[Bot]
    alive: bool = True
    killed: Final[anyio.Event]
    kill_info: KillInfo | None = None
    selected: "Player | None" = None

    @final
    def __init__(self, bot: Bot, game: "Game", user_id: str) -> None:
        self.__user = Target(
            user_id,
            private=True,
            self_id=bot.self_id,
            adapter=bot.adapter.get_name(),
        )
        self.__game_ref = weakref.ref(game)
        self.bot = bot
        self.killed = anyio.Event()
        self._member = None

    @classmethod
    def register_role(cls, role: Role, role_group: RoleGroup, /) -> Callable[[_P], _P]:
        def decorator(c: _P, /) -> _P:
            c.role = role
            c.role_group = role_group
            cls.__player_class[role] = c
            return c

        return decorator

    @final
    @classmethod
    def new(cls, role: Role, bot: Bot, game: "Game", user_id: str) -> "Player":
        if role not in cls.__player_class:
            raise ValueError(f"Unexpected role: {role!r}")

        return cls.__player_class[role](bot, game, user_id)

    def __repr__(self) -> str:
        return (
            f"<Player {self.role_name}: user={self.user_id!r} " f"alive={self.alive}>"
        )

    @property
    def game(self) -> "Game":
        if game := self.__game_ref():
            return game
        raise ValueError("Game not exist")

    @functools.cached_property
    def user_id(self) -> str:
        return self.__user.id

    @functools.cached_property
    def role_name(self) -> str:
        return role_name_conv[self.role]

    async def _fetch_member(self) -> None:
        member = await self.game.interface.get_member(
            SceneType.GROUP,
            self.game.group.id,
            self.user_id,
        )
        if member is None:
            member = await self.game.interface.get_member(
                SceneType.GUILD,
                self.game.group.id,
                self.user_id,
            )

        self._member = member

    @final
    @property
    def _member_nick(self) -> str | None:
        return self._member and (
            self._member.nick or self._member.user.nick or self._member.user.name
        )

    @final
    @property
    def name(self) -> str:
        return self._member_nick or self.user_id

    @final
    @property
    def colored_name(self) -> str:
        name = escape_tag(self.user_id)

        if self._member is None or (nick := self._member_nick) is None:
            name = f"<b><e>{name}</e></b>"
        else:
            name = f"<y>{nick}</y>(<b><e>{name}</e></b>)"

        if self._member is not None and self._member.user.avatar is not None:
            name = link(name, self._member.user.avatar)

        return name

    @final
    def _log(self, text: str) -> None:
        text = text.replace("\n", "\\n")
        logger.info(
            f"{self.game.colored_name} | "
            f"[<b><m>{self.role_name}</m></b>] "
            f"{self.colored_name} | {text}",
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
        await self._fetch_member()
        await self.send(f"⚙️你的身份: {role_emoji[self.role]}{self.role_name}")

    async def kill(self, reason: KillReason, *killers: "Player") -> bool:
        if self.alive:
            self.alive = False
            self.kill_info = KillInfo(reason=reason, killers=[p.name for p in killers])
        return True

    async def post_kill(self) -> None:
        self.killed.set()

    async def vote(self, players: "PlayerSet") -> "Player | None":
        await self.send(
            f"💫请选择需要投票的玩家:\n{players.show()}"
            f"\n\n🗳️发送编号选择玩家\n❌发送 “{STOP_COMMAND_PROMPT}” 弃票"
            f"\n\n限时1分钟，超时将视为弃票"
        )

        try:
            with anyio.fail_after(60):
                selected = await self._select_player(
                    players,
                    on_stop="⚠️你选择了弃票",
                    on_index_error="⚠️输入错误: 请发送编号选择玩家",
                )
        except TimeoutError:
            selected = None
            await self.send("⚠️投票超时，将视为弃票")

        if selected is not None:
            await self.send(f"🔨投票的玩家: {selected.name}")
        return selected

    async def _check_selected(self, player: "Player") -> "Player | None":
        return player

    async def _select_player(
        self,
        players: "PlayerSet",
        *,
        on_stop: str | None = None,
        on_index_error: str | None = None,
    ) -> "Player | None":
        on_stop = on_stop or "ℹ️你选择了取消，回合结束"
        on_index_error = (
            on_index_error or f"⚠️输入错误: 请发送玩家编号或 “{STOP_COMMAND_PROMPT}”"
        )
        selected = None

        while selected is None:
            text = await self.receive_text()
            if text == STOP_COMMAND:
                if on_stop is not None:
                    await self.send(on_stop)
                return None
            index = check_index(text, len(players))
            if index is None:
                await self.send(on_index_error)
                continue
            selected = await self._check_selected(players[index - 1])

        return selected
