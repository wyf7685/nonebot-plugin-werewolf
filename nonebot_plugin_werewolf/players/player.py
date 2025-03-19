import functools
import weakref
from typing import TYPE_CHECKING, ClassVar, Final, Generic, Protocol, TypeVar, final
from typing_extensions import Self, override

import anyio
import nonebot
from nonebot.adapters import Bot
from nonebot.utils import escape_tag
from nonebot_plugin_alconna.uniseg import Receipt, Target, UniMessage
from nonebot_plugin_uninfo import Interface, SceneType

from ..constant import ROLE_EMOJI, ROLE_NAME_CONV, STOP_COMMAND, stop_command_prompt
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


_P = TypeVar("_P", bound="Player")
_P_Contra = TypeVar("_P_Contra", bound="Player", contravariant=True)
_T = TypeVar("_T")


class ActionProvider(Generic[_P]):
    p: _P

    def __init__(self, player: _P) -> None:
        self.p = player

    class proxy(Generic[_T]):  # noqa: N801
        def __init__(self, _t: type[_T] | None = None) -> None:
            super().__init__()

        def __set_name__(self, owner: type["ActionProvider"], name: str) -> None:
            self.__name = name

        def __get__(self, obj: "ActionProvider", objtype: type) -> _T:
            return getattr(obj.p, self.__name)

        def __set__(self, obj: "ActionProvider", value: _T) -> None:
            setattr(obj.p, self.__name, value)

    name = proxy[str]()
    user_id = proxy[str]()
    game = proxy["Game"]()
    selected = proxy["Player | None"]()


class InteractProvider(ActionProvider[_P], Generic[_P]):
    async def before(self) -> None: ...
    async def interact(self) -> None: ...
    async def after(self) -> None: ...


class KillProvider(ActionProvider[_P], Generic[_P]):
    alive = ActionProvider.proxy(bool)
    kill_info = ActionProvider.proxy[KillInfo | None]()

    async def kill(self, reason: KillReason, *killers: "Player") -> KillInfo | None:
        if self.alive:
            self.alive = False
            self.kill_info = KillInfo(reason=reason, killers=[p.name for p in killers])
        return self.kill_info

    async def post_kill(self) -> None: ...


class _InteractProviderGetter(Protocol, Generic[_P_Contra]):
    def __call__(self, player: _P_Contra, /) -> InteractProvider | None: ...


class _KillProviderGetter(Protocol, Generic[_P_Contra]):
    def __call__(self, player: _P_Contra) -> KillProvider: ...


class Player:
    _player_class: ClassVar[dict[Role, type["Player"]]] = {}

    role: ClassVar[Role]
    role_group: ClassVar[RoleGroup]
    interact_provider: ClassVar[_InteractProviderGetter[Self]] = lambda *_: None
    kill_provider: ClassVar[_KillProviderGetter[Self]] = KillProvider

    bot: Final[Bot]
    alive: bool = True
    killed: Final[anyio.Event]
    kill_info: KillInfo | None = None
    selected: "Player | None" = None

    @final
    def __init__(self, bot: Bot, game: "Game", user: Target) -> None:
        self.__user = user
        self.__game_ref = weakref.ref(game)
        self.bot = bot
        self.killed = anyio.Event()
        self._member = None
        self._send_handler = _SendHandler()
        self._send_handler.update(self.__user, bot)

    @final
    @override
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if hasattr(cls, "role") and hasattr(cls, "role_group"):
            cls._player_class[cls.role] = cls

    @final
    @classmethod
    async def new(
        cls,
        role: Role,
        bot: Bot,
        game: "Game",
        user_id: str,
        interface: Interface,
    ) -> "Player":
        if role not in cls._player_class:
            raise ValueError(f"Unexpected role: {role!r}")

        user = Target(
            user_id,
            private=True,
            self_id=game.group.self_id,
            scope=game.group.scope,
            adapter=game.group.adapter,
            extra=game.group.extra,
        )
        self = cls._player_class[role](bot, game, user)
        await self._fetch_member(interface)
        return self

    def __repr__(self) -> str:
        return f"<Player {self.role_name}: user={self.user_id!r} alive={self.alive}>"

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
        return ROLE_NAME_CONV[self.role]

    async def _fetch_member(self, interface: Interface) -> None:
        member = await interface.get_member(
            SceneType.GROUP,
            self.game.group.id,
            self.user_id,
        )
        if member is None:
            member = await interface.get_member(
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
        name = f"<b><e>{escape_tag(self.user_id)}</e></b>"

        if (nick := self._member_nick) is not None:
            name = f"<y>{nick}</y>({name})"

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
        *,
        stop_btn_label: str | None = None,
        select_players: "PlayerSet | None" = None,
        skip_handler: bool = False,
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

    @property
    def interact_timeout(self) -> float:
        return self.game.behavior.timeout.interact

    @final
    async def interact(self) -> None:
        if (provider := self.interact_provider(self)) is None:
            await self.send("ℹ️请等待其他玩家结束交互...")
            return

        await provider.before()

        timeout = self.interact_timeout
        await self.send(f"✏️{self.role_name}交互开始，限时 {timeout / 60:.2f} 分钟")

        try:
            with anyio.fail_after(timeout):
                await provider.interact()
        except TimeoutError:
            logger.debug(f"{self.role_name}交互超时 (<y>{timeout}</y>s)")
            await self.send(f"⚠️{self.role_name}交互超时")

        await provider.after()

    async def notify_role(self) -> None:
        await self.send(f"⚙️你的身份: {ROLE_EMOJI[self.role]}{self.role_name}")

    @final
    async def kill(self, reason: KillReason, *killers: "Player") -> KillInfo | None:
        return await self.kill_provider(self).kill(reason, *killers)

    @final
    async def post_kill(self) -> None:
        await self.kill_provider(self).post_kill()
        self.killed.set()

    async def vote(self, players: "PlayerSet") -> "Player | None":
        await self.send(
            f"💫请选择需要投票的玩家:\n"
            f"{players.show()}\n\n"
            "🗳️发送编号选择玩家\n"
            f"❌发送 “{stop_command_prompt()}” 弃票\n\n"
            "限时1分钟，超时将视为弃票",
            stop_btn_label="弃票",
            select_players=players,
        )

        try:
            with anyio.fail_after(self.game.behavior.timeout.vote):
                selected = await self.select_player(
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

    async def select_player(
        self,
        players: "PlayerSet",
        *,
        on_stop: str | None = None,
        on_index_error: str | None = None,
        stop_btn_label: str | None = None,
    ) -> "Player | None":
        on_stop = on_stop or "ℹ️你选择了取消，回合结束"
        on_index_error = (
            on_index_error or f"⚠️输入错误: 请发送玩家编号或 “{stop_command_prompt()}”"
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
