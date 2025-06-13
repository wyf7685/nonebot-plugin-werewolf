import functools
import random
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from typing_extensions import Self

import anyio
from nonebot_plugin_alconna.uniseg import UniMessage

from .models import Role, RoleGroup
from .player import Player


class PlayerSet(set[Player]):
    __slots__ = ("__dict__",)  # for cached_property `sorted`

    @property
    def size(self) -> int:
        return len(self)

    @classmethod
    def from_(cls, iterable: Iterable[Player], /) -> Self:
        return cls(iterable)

    def alive(self) -> Self:
        return self.from_(p for p in self if p.alive)

    def dead(self) -> Self:
        return self.from_(p for p in self if not p.alive)

    def killed(self) -> Self:
        return self.from_(p for p in self if p.killed.is_set())

    def include(self, *types: Player | Role | RoleGroup) -> Self:
        return self.from_(
            player
            for player in self
            if (player in types or player.role in types or player.role_group in types)
        )

    def select(self, *types: Player | Role | RoleGroup) -> Self:
        return self.include(*types)

    def exclude(self, *types: Player | Role | RoleGroup) -> Self:
        return self.from_(
            player
            for player in self
            if (
                player not in types
                and player.role not in types
                and player.role_group not in types
            )
        )

    def player_selected(self) -> Self:
        return self.from_(p.selected for p in self.alive() if (p.selected is not None))

    @functools.cached_property
    def sorted(self) -> list[Player]:
        return sorted(self, key=lambda p: p.user_id)

    @property
    def shuffled(self) -> list[Player]:
        players = self.sorted.copy()
        random.shuffle(players)
        return players

    async def vote(self) -> dict[Player, list[Player]]:
        players = self.alive()
        result: dict[Player, list[Player]] = {}

        async def _vote(player: Player) -> None:
            if vote := await player.vote(players):
                result.setdefault(vote, []).append(player)

        async with anyio.create_task_group() as tg:
            for p in players:
                tg.start_soon(_vote, p)

        return result

    async def broadcast(self, message: str | UniMessage) -> None:
        if not self:
            return

        send = functools.partial(
            Player.send,
            message=message,
            stop_btn_label=None,
            select_players=None,
            skip_handler=True,
        )

        async with anyio.create_task_group() as tg:
            for p in self:
                tg.start_soon(send, p)

    def show(self) -> str:
        return "\n".join(f"{i}. {p.name}" for i, p in enumerate(self.sorted, 1))

    def __getitem__(self, index: int, /) -> Player:
        return self.sorted[index]

    def __and__(self, other: AbstractSet[Player], /) -> Self:  # type: ignore[override]
        return self.from_(super().__and__(other))

    def __or__(self, other: AbstractSet[Player], /) -> Self:  # type: ignore[override]
        return self.from_(super().__or__(other))

    def __sub__(self, other: AbstractSet[Player], /) -> Self:  # type: ignore[override]
        return self.from_(super().__sub__(other))
