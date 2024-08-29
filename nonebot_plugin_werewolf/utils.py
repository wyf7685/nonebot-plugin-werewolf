import asyncio
from collections import defaultdict
from typing import ClassVar
# from collections.abc import Awaitable, Callable
# from typing import Any

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


# class GameProgress:
#     class _Mark:
#         pass

#     Night = _Mark()
#     Morning = _Mark()
#     Vote = _Mark()

#     progress: _Mark
#     hooks: dict[_Mark, list[Callable[[], Awaitable[Any]]]]

#     def __init__(self) -> None:
#         self.progress = self.Night
#         self.hooks = {self.Night: [], self.Morning: [], self.Vote: []}

#     def get(self) -> _Mark:
#         return self.progress

#     def register(self, progress: _Mark):
#         def decorator(func: Callable[[], Awaitable[Any]]):
#             self.hooks[progress].append(func)
#             return func

#         return decorator

#     async def switch(self, progress: _Mark):
#         await asyncio.gather(*[f() for f in self.hooks[progress]])
#         self.hooks[progress].clear()
#         self.progress = progress
