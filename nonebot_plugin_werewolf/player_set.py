import functools

import anyio
from nonebot_plugin_alconna.uniseg import UniMessage

from .models import Role, RoleGroup
from .players import Player


class PlayerSet(set[Player]):
    @property
    def size(self) -> int:
        return len(self)

    def alive(self) -> "PlayerSet":
        return PlayerSet(p for p in self if p.alive)

    def dead(self) -> "PlayerSet":
        return PlayerSet(p for p in self if not p.alive)

    def killed(self) -> "PlayerSet":
        return PlayerSet(p for p in self if p.killed.is_set())

    def include(self, *types: Player | Role | RoleGroup) -> "PlayerSet":
        return PlayerSet(
            player
            for player in self
            if (player in types or player.role in types or player.role_group in types)
        )

    def select(self, *types: Player | Role | RoleGroup) -> "PlayerSet":
        return self.include(*types)

    def exclude(self, *types: Player | Role | RoleGroup) -> "PlayerSet":
        return PlayerSet(
            player
            for player in self
            if (
                player not in types
                and player.role not in types
                and player.role_group not in types
            )
        )

    def player_selected(self) -> "PlayerSet":
        return PlayerSet(p.selected for p in self.alive() if p.selected is not None)

    @functools.cached_property
    def sorted(self) -> list[Player]:
        return sorted(self, key=lambda p: p.user_id)

    async def interact(self) -> None:
        async with anyio.create_task_group() as tg:
            for p in self.alive():
                tg.start_soon(p.interact)

    async def vote(self) -> dict[Player, list[Player]]:
        players = self.alive()
        result: dict[Player, list[Player]] = {}

        async def _vote(player: Player) -> None:
            vote = await player.vote(players)
            if vote is not None:
                result[vote] = [*result.get(vote, []), player]

        async with anyio.create_task_group() as tg:
            for p in players:
                tg.start_soon(_vote, p)

        return result

    async def broadcast(self, message: str | UniMessage) -> None:
        if not self:
            return

        async with anyio.create_task_group() as tg:
            for p in self:
                tg.start_soon(p.send, message)

    def show(self) -> str:
        return "\n".join(f"{i}. {p.name}" for i, p in enumerate(self.sorted, 1))

    def __getitem__(self, __index: int) -> Player:
        return self.sorted[__index]
