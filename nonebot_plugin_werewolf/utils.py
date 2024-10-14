import asyncio
from collections import defaultdict
from typing import Any, ClassVar

from nonebot_plugin_alconna import UniMessage


def check_index(text: str, arrlen: int) -> int | None:
    if text.isdigit():
        index = int(text)
        if 1 <= index <= arrlen:
            return index
    return None


def link(text: str, url: str | None) -> str:
    return f"\u001b]8;;{url}\u0007{text}\u001b]8;;\u0007"


class InputStore:
    locks: ClassVar[dict[str, asyncio.Lock]] = defaultdict(asyncio.Lock)
    futures: ClassVar[dict[str, asyncio.Future[UniMessage]]] = {}
    clear_handle: ClassVar[dict[str, asyncio.Handle]] = {}

    @classmethod
    def clear_lock(cls, key: str) -> None:
        if key in cls.locks and not cls.locks[key].locked():
            del cls.locks[key]
        if key in cls.clear_handle:
            del cls.clear_handle[key]

    @classmethod
    async def fetch(cls, user_id: str, group_id: str | None = None) -> UniMessage[Any]:
        key = f"{group_id}_{user_id}"
        async with cls.locks[key]:
            cls.futures[key] = fut = asyncio.get_event_loop().create_future()
            try:
                return await fut
            finally:
                del cls.futures[key]
                if key in cls.clear_handle:
                    cls.clear_handle[key].cancel()
                loop = asyncio.get_event_loop()
                cls.clear_handle[key] = loop.call_later(120, cls.clear_lock, key)

    @classmethod
    def put(cls, msg: UniMessage, user_id: str, group_id: str | None = None) -> None:
        key = f"{group_id}_{user_id}"
        if (future := cls.futures.get(key)) and not future.cancelled():
            future.set_result(msg)
