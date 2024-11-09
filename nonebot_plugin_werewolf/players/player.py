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
from ..utils import (
    InputStore,
    SendHandler,
    add_players_button,
    add_stop_button,
    check_index,
    link,
)

if TYPE_CHECKING:
    from ..game import Game
    from ..player_set import PlayerSet


_P = TypeVar("_P", bound=type["Player"])

logger = nonebot.logger.opt(colors=True)


class _SendHandler(SendHandler[str | None]):
    def solve_msg(
        self,
        msg: UniMessage,
        stop_btn_label: str | None = None,
    ) -> UniMessage:
        if stop_btn_label is not None:
            msg = add_stop_button(msg, stop_btn_label)
        return msg


class Player:
    __player_class: ClassVar[dict[Role, type["Player"]]] = {}
    role: ClassVar[Role]
    role_group: ClassVar[RoleGroup]

    bot: Final[Bot]
    alive: bool = True
    killed: Final[anyio.Event]
    kill_info: KillInfo | None = None
    selected: "Player | None" = None
    interact_timeout: float = 60

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
        self._send_handler = _SendHandler()
        self._send_handler.update(self.__user, bot)

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
    def log(self, text: str) -> None:
        text = text.replace("\n", "\\n")
        self.game.log(f"[<b><m>{self.role_name}</m></b>] {self.colored_name} | {text}")

    @final
    async def send(
        self,
        message: str | UniMessage,
        stop_btn_label: str | None = None,
        select_players: "PlayerSet | None" = None,
        skip_handler: bool = False,  # noqa: FBT001, FBT002
    ) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        self.log(f"<g>Send</g> | {escape_tag(str(message))}")

        if select_players:
            message = add_players_button(message, select_players)
        if skip_handler:
            return await message.send(self.__user, self.bot)
        return await self._send_handler.send(message, stop_btn_label)

    @final
    async def receive(self) -> UniMessage:
        result = await InputStore.fetch(self.user_id)
        self.log(f"<y>Recv</y> | {escape_tag(str(result))}")
        return result

    @final
    async def receive_text(self) -> str:
        return (await self.receive()).extract_plain_text()

    async def _before_interact(self) -> None:
        return

    async def _interact(self) -> None:
        return

    async def _after_interact(self) -> None:
        return

    async def interact(self) -> None:
        if not getattr(self._interact, "__override__", False):
            await self.send("ℹ️请等待其他玩家结束交互...")
            return

        await self._before_interact()

        text = self.role_name
        timeout = self.interact_timeout
        await self.send(f"✏️{text}交互开始，限时 {timeout/60:.2f} 分钟")

        try:
            with anyio.fail_after(timeout):
                await self._interact()
        except TimeoutError:
            logger.debug(f"{text}交互超时 (<y>{timeout}</y>s)")
            await self.send(f"⚠️{text}交互超时")

        await self._after_interact()

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
            f"💫请选择需要投票的玩家:\n"
            f"{players.show()}\n\n"
            "🗳️发送编号选择玩家\n"
            f"❌发送 “{STOP_COMMAND_PROMPT}” 弃票\n\n"
            "限时1分钟，超时将视为弃票",
            stop_btn_label="弃票",
            select_players=players,
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
        stop_btn_label: str | None = None,
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
                await self.send(
                    on_index_error,
                    stop_btn_label=stop_btn_label,
                    select_players=players,
                )
                continue
            selected = await self._check_selected(players[index - 1])

        return selected
