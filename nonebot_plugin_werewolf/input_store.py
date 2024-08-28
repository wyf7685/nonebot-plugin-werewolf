import asyncio
from collections import defaultdict

from nonebot_plugin_alconna import UniMessage


class InputStore:
    locks: dict[str, asyncio.Lock]
    futures: dict[str, asyncio.Future[UniMessage]]

    def __init__(self) -> None:
        self.locks = defaultdict(asyncio.Lock)
        self.futures = {}

    async def fetch(self, user_id: str, group_id: str | None = None):
        key = f"{group_id}_{user_id}"
        async with self.locks[key]:
            self.futures[key] = asyncio.get_event_loop().create_future()
            try:
                return await self.futures[key]
            finally:
                del self.futures[key]

    def put(self, user_id: str, group_id: str | None, msg: UniMessage):
        key = f"{group_id}_{user_id}"
        if future := self.futures.get(key):
            future.set_result(msg)


store = InputStore()
