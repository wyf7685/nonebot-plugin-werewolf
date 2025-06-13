import functools
import weakref
from types import EllipsisType
from typing import TYPE_CHECKING, ClassVar, Final, Generic, TypeVar, final
from typing_extensions import Self, override

import anyio
import nonebot
from nonebot.utils import escape_tag
from nonebot_plugin_alconna.uniseg import Receipt, Target, UniMessage
from nonebot_plugin_uninfo import Interface, SceneType

from .config import stop_command_prompt
from .constant import STOP_COMMAND
from .models import KillInfo, KillReason, Role, RoleGroup
from .utils import (
    InputStore,
    SendHandler,
    add_players_button,
    add_stop_button,
    check_index,
    link,
)

if TYPE_CHECKING:
    from .game import Game
    from .player_set import PlayerSet


logger = nonebot.logger.opt(colors=True)


_P = TypeVar("_P", bound="Player")
_T = TypeVar("_T")


class ActionProvider(Generic[_P]):
    p: _P

    @final
    def __init__(self, player: _P, /) -> None:
        self.p = player

    class proxy(Generic[_T]):  # noqa: N801
        def __init__(
            self, _: type[_T] | None = None, /, *, readonly: bool = False
        ) -> None:
            self.readonly = readonly

        def __set_name__(self, owner: type["ActionProvider"], name: str) -> None:
            self.name = name

        def __get__(self, obj: "ActionProvider", objtype: type) -> _T:
            return getattr(obj.p, self.name)

        def __set__(self, obj: "ActionProvider", value: _T) -> None:
            if self.readonly:
                raise AttributeError(f"readonly attribute {self.name}")
            setattr(obj.p, self.name, value)

    name = proxy[str](readonly=True)
    user_id = proxy[str](readonly=True)
    game = proxy["Game"](readonly=True)
    selected = proxy["Player | None"]()


class InteractProvider(ActionProvider[_P], Generic[_P]):
    async def before(self) -> None: ...
    async def interact(self) -> None: ...
    async def after(self) -> None: ...


class KillProvider(ActionProvider[_P], Generic[_P]):
    alive = ActionProvider.proxy[bool]()
    kill_info = ActionProvider.proxy[KillInfo | None]()

    async def kill(self, reason: KillReason, *killers: "Player") -> KillInfo | None:
        if self.alive:
            self.alive = False
            self.kill_info = KillInfo(reason=reason, killers=[p.name for p in killers])
        return self.kill_info

    async def post_kill(self) -> None: ...


class NotifyProvider(ActionProvider[_P], Generic[_P]):
    role = ActionProvider.proxy[Role]()
    role_group = ActionProvider.proxy[RoleGroup]()
    role_name = ActionProvider.proxy[str]()

    def message(self, message: UniMessage) -> UniMessage:
        return message

    async def notify(self) -> None:
        msg = UniMessage.text(f"⚙️你的身份: {self.role.emoji}{self.role_name}\n")
        await self.p.send(self.message(msg))


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
    _player_class: ClassVar[dict[Role, type["Player"]]] = {}

    role: ClassVar[Role]
    role_group: ClassVar[RoleGroup]
    interact_provider: ClassVar[type[InteractProvider[Self]] | None]
    kill_provider: ClassVar[type[KillProvider[Self]]]
    notify_provider: ClassVar[type[NotifyProvider[Self]]]

    user: Final[Target]
    alive: bool = True
    killed: Final[anyio.Event]
    kill_info: KillInfo | None = None
    selected: "Player | None" = None

    @final
    def __init__(self, game: "Game", user: Target) -> None:
        self.__game_ref = weakref.ref(game)
        self.user = user
        self.killed = anyio.Event()
        self._member = None
        self._send_handler = _SendHandler(self.user)

    @final
    @override
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if not (hasattr(cls, "role") and hasattr(cls, "role_group")):
            return

        assert cls.role not in cls._player_class  # noqa: S101
        cls._player_class[cls.role] = cls
        for k, v in {
            "interact_provider": None,
            "kill_provider": KillProvider,
            "notify_provider": NotifyProvider,
        }.items():
            if not hasattr(cls, k):
                setattr(cls, k, v)

    @final
    @classmethod
    async def new(
        cls,
        role: Role,
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
        self = cls._player_class[role](game, user)

        await self._fetch_member(interface)
        return self

    def __repr__(self) -> str:
        return f"<Player {self.role_name}: user={self.user_id!r} alive={self.alive}>"

    @final
    @property
    def game(self) -> "Game":
        if game := self.__game_ref():
            return game
        raise ValueError("Game not exist")

    @final
    @functools.cached_property
    def user_id(self) -> str:
        return self.user.id

    @final
    @functools.cached_property
    def role_name(self) -> str:
        return self.role.display

    @final
    async def _fetch_member(self, interface: Interface) -> None:
        member = await interface.get_member(
            SceneType.GROUP,
            self.game.group_id,
            self.user_id,
        )
        if member is None:
            member = await interface.get_member(
                SceneType.GUILD,
                self.game.group_id,
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
            return await message.send(self.user)
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
        if self.interact_provider is None:
            await self.send("ℹ️请等待其他玩家结束交互...")
            return

        provider = self.interact_provider(self)

        await provider.before()
        timeout = self.interact_timeout
        await self.send(f"✏️{self.role_name}交互开始，限时 {timeout / 60:.2f} 分钟")

        with anyio.move_on_after(timeout) as scope:
            await provider.interact()
        if scope.cancelled_caught:
            logger.debug(f"{self.role_name}交互超时 (<y>{timeout}</y>s)")
            await self.send(f"⚠️{self.role_name}交互超时")

        await provider.after()

    async def notify_role(self) -> None:
        await self.notify_provider(self).notify()

    @final
    async def kill(self, reason: KillReason, *killers: "Player") -> KillInfo | None:
        return await self.kill_provider(self).kill(reason, *killers)

    @final
    async def post_kill(self) -> None:
        await self.kill_provider(self).post_kill()
        self.killed.set()

    async def vote(self, players: "PlayerSet") -> "Player | None":
        vote_timeout = self.game.behavior.timeout.vote
        await self.send(
            f"💫请选择需要投票的玩家:\n"
            f"{players.show()}\n\n"
            "🗳️发送编号选择玩家\n"
            f"❌发送 “{stop_command_prompt}” 弃票\n\n"
            f"限时{vote_timeout / 60:.1f}分钟，超时将视为弃票",
            stop_btn_label="弃票",
            select_players=players,
        )

        selected = None
        with anyio.move_on_after(vote_timeout) as scope:
            selected = await self.select_player(
                players,
                on_stop="⚠️你选择了弃票",
                on_index_error="⚠️输入错误: 请发送编号选择玩家",
            )
        if scope.cancelled_caught:
            await self.send("⚠️投票超时，将视为弃票")

        if selected is not None:
            await self.send(f"🔨投票的玩家: {selected.name}")
        return selected

    async def _check_selected(self, player: "Player") -> "Player | None":
        return player

    @final
    async def select_player(
        self,
        players: "PlayerSet",
        *,
        on_stop: str | EllipsisType | None = ...,
        on_index_error: str | None = None,
        stop_btn_label: str | None = None,
    ) -> "Player | None":
        on_stop = on_stop if on_stop is not None else "ℹ️你选择了取消，回合结束"
        on_index_error = (
            on_index_error or f"⚠️输入错误: 请发送玩家编号或 “{stop_command_prompt}”"
        )
        selected = None

        while selected is None:
            text = await self.receive_text()
            if text == STOP_COMMAND:
                if on_stop is not ...:
                    await self.send(on_stop)
                return None
            if (index := check_index(text, players.size)) is None:
                await self.send(
                    on_index_error,
                    stop_btn_label=stop_btn_label,
                    select_players=players,
                )
                continue
            selected = await self._check_selected(players[index - 1])

        return selected
