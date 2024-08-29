# import asyncio
# from collections.abc import Awaitable, Callable
# from typing import Any


def check_index(text: str, arrlen: int) -> int | None:
    if not text.isdigit():
        return None
    index = int(text)
    if 1 <= index <= arrlen:
        return index


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
