import asyncio
import asyncio.timeouts
from collections import defaultdict
from typing import Annotated, Any, ClassVar

import nonebot_plugin_waiter as waiter
from nonebot.adapters import Event
from nonebot.rule import to_me
from nonebot_plugin_alconna import MsgTarget, UniMessage, UniMsg
from nonebot_plugin_userinfo import EventUserInfo, UserInfo

from .game import player_preset, running_games


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
    async def fetch(cls, user_id: str, group_id: str | None = None) -> UniMessage[Any]:
        key = f"{group_id}_{user_id}"
        async with cls.locks[key]:
            cls.futures[key] = asyncio.get_event_loop().create_future()
            try:
                return await cls.futures[key]
            finally:
                del cls.futures[key]

    @classmethod
    def put(cls, user_id: str, group_id: str | None, msg: UniMessage) -> None:
        key = f"{group_id}_{user_id}"
        if future := cls.futures.get(key):
            future.set_result(msg)


def user_in_game(user_id: str, group_id: str | None) -> bool:
    if group_id is not None and group_id not in running_games:
        return False
    games = running_games.values() if group_id is None else [running_games[group_id]]
    for game, _ in games:
        return any(user_id == player.user_id for player in game.players)
    return False


async def rule_in_game(event: Event, target: MsgTarget) -> bool:
    if not running_games:
        return False
    if target.private:
        return user_in_game(target.id, None)
    elif target.id in running_games:
        return user_in_game(event.get_user_id(), target.id)
    return False


async def rule_not_in_game(event: Event, target: MsgTarget) -> bool:
    return not await rule_in_game(event, target)


async def is_group(target: MsgTarget) -> bool:
    return not target.private


async def _prepare_game_receive(
    queue: asyncio.Queue[tuple[str, str, str]],
    event: Event,
    group_id: str,
) -> None:
    async def rule(target_: MsgTarget) -> bool:
        return not target_.private and target_.id == group_id

    @waiter.waiter(
        waits=[event.get_type()],
        keep_session=False,
        rule=to_me() & rule & rule_not_in_game,
    )
    def wait(
        event: Event,
        info: Annotated[UserInfo | None, EventUserInfo()],
        msg: UniMsg,
    ) -> tuple[str, str, str]:
        return (
            event.get_user_id(),
            info.user_name if info is not None else event.get_user_id(),
            msg.extract_plain_text().strip(),
        )

    async for user, name, text in wait(default=(None, "", "")):
        if user is None:
            continue
        await queue.put((user, name, text))


async def _prepare_game_handle(
    queue: asyncio.Queue[tuple[str, str, str]],
    players: dict[str, str],
    admin_id: str,
) -> None:
    while True:
        user, name, text = await queue.get()
        msg = UniMessage.at(user)

        match (text, user == admin_id):
            case ("开始游戏", True):
                player_num = len(players)
                if player_num < min(player_preset):
                    await (
                        msg.text(f"游戏至少需要 {min(player_preset)} 人, ")
                        .text(f"当前已有 {player_num} 人")
                        .send()
                    )
                elif player_num > max(player_preset):
                    await (
                        msg.text(f"游戏最多需要 {max(player_preset)} 人, ")
                        .text(f"当前已有 {player_num} 人")
                        .send()
                    )
                elif player_num not in player_preset:
                    await (
                        msg.text(f"不存在总人数为 {player_num} 的预设, ")
                        .text("无法开始游戏")
                        .send()
                    )
                else:
                    await msg.text("游戏即将开始...").send()
                    return

            case ("开始游戏", False):
                await msg.text("只有游戏发起者可以开始游戏").send()

            case ("结束游戏", True):
                await msg.text("已结束当前游戏").finish()

            case ("结束游戏", False):
                await msg.text("只有游戏发起者可以结束游戏").send()

            case ("加入游戏", True):
                await msg.text("游戏发起者已经加入游戏了").send()

            case ("加入游戏", False):
                if user not in players:
                    players[user] = name
                    await msg.text("成功加入游戏").send()
                else:
                    await msg.text("你已经加入游戏了").send()

            case ("退出游戏", True):
                await msg.text("游戏发起者无法退出游戏").send()

            case ("退出游戏", False):
                if user in players:
                    del players[user]
                    await msg.text("成功退出游戏").send()
                else:
                    await msg.text("你还没有加入游戏").send()

            case ("当前玩家", _):
                msg.text("\n当前玩家:\n")
                for name in players.values():
                    msg.text(f"\n{name}")
                await msg.send()


async def prepare_game(event: Event, players: dict[str, str]) -> None:
    queue = asyncio.Queue()
    task_receive = asyncio.create_task(
        _prepare_game_receive(
            queue,
            event,
            UniMessage.get_target().id,
        )
    )

    try:
        await _prepare_game_handle(
            queue,
            players,
            event.get_user_id(),
        )
    finally:
        task_receive.cancel()
