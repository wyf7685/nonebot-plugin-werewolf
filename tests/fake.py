# ruff: noqa: N806, ANN401
import contextlib
import itertools
from collections.abc import Callable, Generator
from types import TracebackType
from typing import TYPE_CHECKING, Any, Literal, overload
from typing_extensions import Self

import nonebot
from nonebot.adapters import Adapter, Bot, Event
from nonebot.adapters.onebot.v11.event import (
    GroupMessageEvent,
    MessageEvent,
    PrivateMessageEvent,
    Sender,
)
from nonebot.adapters.onebot.v11.message import Message
from nonebot.matcher import Matcher
from nonebug.mixin.call_api import ApiContext
from nonebug.mixin.dependent import DependentContext
from nonebug.mixin.process import MatcherContext
from pydantic import Field, create_model

fake_user_id = (lambda: (g := itertools.count(100000)) and (lambda: next(g)))()
fake_group_id = (lambda: (g := itertools.count(200000)) and (lambda: next(g)))()
fake_message_id = (lambda: (g := itertools.count(1)) and (lambda: next(g)))()


@contextlib.contextmanager
def ensure_context(
    bot: Bot,
    event: Event,
    matcher: Matcher | None = None,
) -> Generator[None]:
    # ref: `nonebot.internal.matcher.matcher:Matcher.ensure_context`
    from nonebot.internal.matcher import current_bot, current_event, current_matcher

    b = current_bot.set(bot)
    e = current_event.set(event)
    m = current_matcher.set(matcher) if matcher else None

    try:
        yield
    finally:
        current_bot.reset(b)
        current_event.reset(e)
        if m:
            current_matcher.reset(m)


def fake_bot(
    ctx: ApiContext | MatcherContext | DependentContext,
    adapter_base: type[Adapter],
    bot_base: type[Bot],
    **kwargs: Any,
) -> Bot:
    return ctx.create_bot(
        base=bot_base,
        adapter=nonebot.get_adapter(adapter_base),
        **kwargs,
    )


def fake_v11_bot(ctx: ApiContext | MatcherContext, **kwargs: Any) -> Bot:
    from nonebot.adapters.onebot.v11 import Adapter, Bot

    return ctx.create_bot(
        base=Bot,
        adapter=nonebot.get_adapter(Adapter),
        **kwargs,
    )


def fake_v11_group_message_event(**field: Any) -> GroupMessageEvent:
    from nonebot.adapters.onebot.v11 import Message

    _Fake = create_model("_Fake", __base__=GroupMessageEvent)

    class FakeEvent(_Fake):
        time: int = 1000000
        self_id: int = 1
        post_type: Literal["message"] = "message"
        sub_type: str = "normal"
        user_id: int = Field(default_factory=fake_user_id)
        message_type: Literal["group"] = "group"
        group_id: int = Field(default_factory=fake_group_id)
        message_id: int = Field(default_factory=fake_message_id)
        message: Message = Message("test")
        raw_message: str = "test"
        font: int = 0
        sender: Sender = Sender(
            card="",
            nickname="test",
            role="member",
        )
        to_me: bool = False

    return FakeEvent(**field)


def fake_v11_private_message_event(**field: Any) -> PrivateMessageEvent:
    from nonebot.adapters.onebot.v11 import Message, PrivateMessageEvent
    from nonebot.adapters.onebot.v11.event import Sender
    from pydantic import create_model

    _Fake = create_model("_Fake", __base__=PrivateMessageEvent)

    class FakeEvent(_Fake):
        time: int = 1000000
        self_id: int = 1
        post_type: Literal["message"] = "message"
        sub_type: str = "friend"
        user_id: int = Field(default_factory=fake_user_id)
        message_type: Literal["private"] = "private"
        message_id: int = Field(default_factory=fake_message_id)
        message: Message = Message("test")
        raw_message: str = "test"
        font: int = 0
        sender: Sender = Sender(nickname="test")
        to_me: bool = False

    return FakeEvent(**field)


@overload
def fake_v11_event() -> PrivateMessageEvent: ...
@overload
def fake_v11_event(user_id: int) -> PrivateMessageEvent: ...
@overload
def fake_v11_event(*, group_id: int) -> GroupMessageEvent: ...
@overload
def fake_v11_event(user_id: int, group_id: int) -> GroupMessageEvent: ...
@overload
def fake_v11_event(
    *,
    user_id: int | None = None,
    group_id: int | None = None,
) -> MessageEvent: ...


def fake_v11_event(
    user_id: int | None = None,
    group_id: int | None = None,
) -> MessageEvent:
    from nonebot.adapters.onebot.v11 import Message

    user_id = user_id or fake_user_id()
    if group_id is not None:
        return fake_v11_group_message_event(
            user_id=user_id,
            group_id=group_id,
            message=Message(),
        )

    return fake_v11_private_message_event(
        user_id=user_id,
        message=Message(),
    )


class MessageChecker:
    if TYPE_CHECKING:

        def __new__(cls, pred: Callable[[Message, str], bool], /) -> Message: ...

    def __init__(self, pred: Callable[[Message, str], bool], /) -> None:
        self.pred = pred

    def __eq__(self, value: object, /) -> bool:
        return isinstance(value, Message) and self.pred(
            value, value.extract_plain_text()
        )


class DependentTestWrapper:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.ctx.__exit__(exc_type, exc_value, traceback)

    def setup(self, bot: Bot, event: Event) -> None:
        self.ctx = ensure_context(bot, event)
        self.ctx.__enter__()
