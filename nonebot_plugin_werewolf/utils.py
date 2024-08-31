import asyncio
from collections import defaultdict
from typing import ClassVar

from nonebot_plugin_alconna import UniMessage


def check_index(text: str, arrlen: int) -> int | None:
    if text.isdigit():
        index = int(text)
        if 1 <= index <= arrlen:
            return index
    return None


class InputStore:
    locks: ClassVar[dict[str, asyncio.Lock]] = defaultdict(asyncio.Lock)
    futures: ClassVar[dict[str, asyncio.Future[UniMessage]]] = {}

    @classmethod
    async def fetch(cls, user_id: str, group_id: str | None = None):
        key = f"{group_id}_{user_id}"
        async with cls.locks[key]:
            cls.futures[key] = asyncio.get_event_loop().create_future()
            try:
                return await cls.futures[key]
            finally:
                del cls.futures[key]

    @classmethod
    def put(cls, user_id: str, group_id: str | None, msg: UniMessage):
        key = f"{group_id}_{user_id}"
        if future := cls.futures.get(key):
            future.set_result(msg)
