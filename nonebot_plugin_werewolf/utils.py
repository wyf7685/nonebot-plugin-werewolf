import abc
import functools
import itertools
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar, Generic, ParamSpec, TypeVar

import anyio
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna.uniseg import (
    Button,
    FallbackStrategy,
    Keyboard,
    Receipt,
    Target,
    UniMessage,
)
from nonebot_plugin_uninfo import Session

from .config import config, stop_command_prompt
from .constant import STOP_COMMAND

if TYPE_CHECKING:
    from .player import Player
    from .player_set import PlayerSet

T = TypeVar("T")
P = ParamSpec("P")


def check_index(text: str, arrlen: int) -> int | None:
    if text.isdigit():
        index = int(text)
        if 1 <= index <= arrlen:
            return index
    return None


def link(text: str, url: str | None) -> str:
    return text if url is None else f"\u001b]8;;{url}\u0007{text}\u001b]8;;\u0007"


def extract_session_member_nick(session: Session) -> str | None:
    return (
        (session.member and session.member.nick)
        or session.user.nick
        or session.user.name
    )


class _InputTask:
    _event: anyio.Event
    _msg: UniMessage

    def __init__(self) -> None:
        self._event = anyio.Event()

    def set(self, msg: UniMessage) -> None:
        self._msg = msg
        self._event.set()

    async def wait(self) -> UniMessage:
        await self._event.wait()
        return self._msg


class InputStore:
    locks: ClassVar[dict[str, anyio.Lock]] = defaultdict(anyio.Lock)
    tasks: ClassVar[dict[str, _InputTask]] = {}

    @staticmethod
    def _key(user_id: str, group_id: str | None) -> str:
        return f"{group_id}_{user_id}"

    @classmethod
    async def fetch(cls, user_id: str, group_id: str | None = None) -> UniMessage[Any]:
        key = cls._key(user_id, group_id)
        async with cls.locks[key]:
            cls.tasks[key] = task = _InputTask()
            try:
                return await task.wait()
            finally:
                cls.tasks.pop(key, None)

    @classmethod
    async def fetch_until_stop(cls, user_id: str, group_id: str | None = None) -> None:
        while True:
            msg = await cls.fetch(user_id, group_id)
            if msg.extract_plain_text().strip() == STOP_COMMAND:
                return

    @classmethod
    def put(cls, msg: UniMessage, user_id: str, group_id: str | None = None) -> None:
        key = cls._key(user_id, group_id)
        if task := cls.tasks.pop(key, None):
            task.set(msg)

    @classmethod
    def cleanup(cls, players: Iterable[str], group_id: str) -> None:
        for p, g in itertools.product(players, (group_id, None)):
            key = cls._key(p, g)
            if key in cls.locks:
                del cls.locks[key]
            if key in cls.tasks:
                del cls.tasks[key]


@functools.cache
def cached_player_set() -> type["PlayerSet"]:
    from .player_set import PlayerSet

    return PlayerSet


def as_player_set(*player: "Player") -> "PlayerSet":
    return cached_player_set()(player)


def btn(label: str, text: str, /) -> Button:
    return Button(flag="input", label=label, text=text)


def add_stop_button(msg: str | UniMessage, label: str | None = None) -> UniMessage:
    if isinstance(msg, str):
        msg = UniMessage.text(msg)

    stop = stop_command_prompt
    return msg.keyboard(btn(label or stop, stop))


def add_players_button(msg: str | UniMessage, players: "PlayerSet") -> UniMessage:
    if isinstance(msg, str):
        msg = UniMessage.text(msg)

    it = enumerate(players, 1)
    while line := tuple(itertools.islice(it, 3)):
        msg.keyboard(*(btn(p.name, str(i)) for i, p in line))
    return msg


class SendHandler(abc.ABC, Generic[P]):
    bot: Bot | None
    target: Event | Target | None
    reply_to: bool | None = None
    last_msg: UniMessage | None = None
    last_receipt: Receipt | None = None

    def __init__(
        self,
        target: Event | Target | None = None,
        bot: Bot | None = None,
    ) -> None:
        self.bot = bot
        self.target = target

    def update(self, target: Event | Target, bot: Bot | None = None) -> None:
        self.bot = bot
        self.target = target

    @functools.cached_property
    def _is_dc(self) -> bool:
        try:
            from nonebot.adapters.discord import Bot
        except ImportError:
            return False

        return isinstance(self.bot, Bot)

    async def _fetch_bot(self) -> None:
        if self.bot is None and isinstance(self.target, Target):
            self.bot = await self.target.select()

    async def _edit(self) -> None:
        await self._fetch_bot()

        last = self.last_receipt
        if (
            config.enable_button
            and self.last_msg is not None
            and last is not None
            and last.editable
            and not self._is_dc
        ):
            await last.edit(self.last_msg.exclude(Keyboard))

    async def _send(self, message: UniMessage) -> None:
        if self.target is None:
            raise RuntimeError("Target cannot be None when sending a message.")

        if not config.enable_button or self._is_dc:
            # TODO: support discord button
            message = message.exclude(Keyboard)

        await self._fetch_bot()
        receipt = await message.send(
            target=self.target,
            bot=self.bot,
            reply_to=self.reply_to,
            fallback=FallbackStrategy.ignore,
        )
        self.last_msg = message
        self.last_receipt = receipt

    @abc.abstractmethod
    def solve_msg(
        self,
        msg: UniMessage,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> UniMessage:
        raise NotImplementedError

    async def send(
        self,
        msg: str | UniMessage,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Receipt:
        msg = UniMessage.text(msg) if isinstance(msg, str) else msg
        msg = self.solve_msg(msg, *args, **kwargs)

        async with anyio.create_task_group() as tg:
            tg.start_soon(self._edit)
            tg.start_soon(self._send, msg)

        if TYPE_CHECKING:
            assert self.last_receipt is not None

        return self.last_receipt
