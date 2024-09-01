import asyncio
import asyncio.timeouts
import contextlib

from nonebot_plugin_alconna.uniseg import UniMessage

from .constant import Role, RoleGroup
from .player import Player
from .utils import InputStore


class PlayerSet(set[Player]):
    @property
    def size(self) -> int:
        return len(self)

    def alive(self) -> "PlayerSet":
        return PlayerSet(p for p in self if p.alive)

    def dead(self) -> "PlayerSet":
        return PlayerSet(p for p in self if not p.alive)

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

    def sorted(self) -> list[Player]:
        return sorted(self, key=lambda p: p.user_id)

    async def interact(self, timeout_secs: float = 60) -> None:
        async with asyncio.timeouts.timeout(timeout_secs):
            await asyncio.gather(*[p.interact() for p in self.alive()])

    async def vote(self, timeout_secs: float = 60) -> dict[Player, list[Player]]:
        async def vote(player: Player) -> "tuple[Player, Player] | None":
            try:
                async with asyncio.timeouts.timeout(timeout_secs):
                    return await player.vote(self)
            except TimeoutError:
                await player.send("投票超时，将视为弃票")

        result: dict[Player, list[Player]] = {}
        for item in await asyncio.gather(*[vote(p) for p in self.alive()]):
            if item is not None:
                player, voted = item
                result[voted] = [*result.get(voted, []), player]
        return result

    async def broadcast(self, message: str | UniMessage) -> None:
        await asyncio.gather(*[p.send(message) for p in self])

    async def wait_group_stop(self, group_id: str, timeout_secs: float) -> None:
        async def wait(p: Player):
            while True:
                msg = await InputStore.fetch(p.user_id, group_id)
                if msg.extract_plain_text() == "/stop":
                    break

        with contextlib.suppress(TimeoutError):
            async with asyncio.timeouts.timeout(timeout_secs):
                await asyncio.gather(*[wait(p) for p in self])

    def show(self) -> str:
        return "\n".join(f"{i}. {p.name}" for i, p in enumerate(self.sorted(), 1))

    def __getitem__(self, __index: int) -> Player:
        return self.sorted()[__index]
