import asyncio
import itertools
import re
from collections import defaultdict
from typing import Any, ClassVar

import nonebot
import nonebot_plugin_waiter as waiter
from nonebot.adapters import Bot, Event
from nonebot.rule import to_me
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import MsgTarget, Target, UniMessage, UniMsg
from nonebot_plugin_uninfo import Uninfo

from .config import config


def check_index(text: str, arrlen: int) -> int | None:
    if text.isdigit():
        index = int(text)
        if 1 <= index <= arrlen:
            return index
    return None


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


def user_in_game(self_id: str, user_id: str, group_id: str | None) -> bool:
    from .game import Game

    if group_id is None:
        return any(
            self_id == p.user.self_id and user_id == p.user_id
            for p in itertools.chain(*[g.players for g in Game.running_games])
        )

    def check(game: Game) -> bool:
        return self_id == game.group.self_id and group_id == game.group.id

    if game := next(filter(check, Game.running_games), None):
        return any(user_id == player.user_id for player in game.players)

    return False


async def rule_in_game(bot: Bot, event: Event, target: MsgTarget) -> bool:
    from .game import Game

    if not Game.running_games:
        return False
    if target.private:
        return user_in_game(bot.self_id, target.id, None)
    return user_in_game(bot.self_id, event.get_user_id(), target.id)


async def rule_not_in_game(bot: Bot, event: Event, target: MsgTarget) -> bool:
    return not await rule_in_game(bot, event, target)


async def is_group(target: MsgTarget) -> bool:
    return not target.private


async def _prepare_game_receive(
    queue: asyncio.Queue[tuple[str, str, str]],
    event: Event,
    group: Target,
) -> None:
    async def same_group(target: MsgTarget) -> bool:
        return group.verify(target)

    @waiter.waiter(
        waits=[event.get_type()],
        keep_session=False,
        rule=to_me() & same_group & rule_not_in_game,
    )
    def wait(
        event: Event,
        msg: UniMsg,
        session: Uninfo,
    ) -> tuple[str, str, str]:
        user_id = event.get_user_id()
        name = session.user.nick or session.user.name or user_id
        if session.member:
            name = session.member.nick or name
        return (
            user_id,
            msg.extract_plain_text().strip(),
            name,
        )

    async for user, text, name in wait(default=(None, "", "")):
        if user is None:
            continue
        await queue.put((user, text, re.sub(r"[\u2066-\u2069]", "", name)))


async def _prepare_game_handle(
    queue: asyncio.Queue[tuple[str, str, str]],
    players: dict[str, str],
    admin_id: str,
) -> None:
    logger = nonebot.logger.opt(colors=True)

    while True:
        user, text, name = await queue.get()
        msg = UniMessage.at(user).text("\n")
        colored = f"<y>{escape_tag(name)}</y>(<c>{escape_tag(user)}</c>)"

        match (text, user == admin_id):
            case ("开始游戏", True):
                player_num = len(players)
                role_preset = config.get_role_preset()
                if player_num < min(role_preset):
                    await (
                        msg.text(f"⚠️游戏至少需要 {min(role_preset)} 人, ")
                        .text(f"当前已有 {player_num} 人")
                        .send()
                    )
                elif player_num > max(role_preset):
                    await (
                        msg.text(f"⚠️游戏最多需要 {max(role_preset)} 人, ")
                        .text(f"当前已有 {player_num} 人")
                        .send()
                    )
                elif player_num not in role_preset:
                    await (
                        msg.text(f"⚠️不存在总人数为 {player_num} 的预设, ")
                        .text("无法开始游戏")
                        .send()
                    )
                else:
                    await msg.text("✏️游戏即将开始...").send()
                    logger.info(f"游戏发起者 {colored} 开始游戏")
                    return

            case ("开始游戏", False):
                await msg.text("⚠️只有游戏发起者可以开始游戏").send()

            case ("结束游戏", True):
                logger.info(f"游戏发起者 {colored} 结束游戏")
                await msg.text("ℹ️已结束当前游戏").finish()

            case ("结束游戏", False):
                await msg.text("⚠️只有游戏发起者可以结束游戏").send()

            case ("加入游戏", True):
                await msg.text("ℹ️游戏发起者已经加入游戏了").send()

            case ("加入游戏", False):
                if user not in players:
                    players[user] = name
                    logger.info(f"玩家 {colored} 加入游戏")
                    await msg.text("✅成功加入游戏").send()
                else:
                    await msg.text("ℹ️你已经加入游戏了").send()

            case ("退出游戏", True):
                await msg.text("ℹ️游戏发起者无法退出游戏").send()

            case ("退出游戏", False):
                if user in players:
                    del players[user]
                    logger.info(f"玩家 {colored} 退出游戏")
                    await msg.text("✅成功退出游戏").send()
                else:
                    await msg.text("ℹ️你还没有加入游戏").send()

            case ("当前玩家", _):
                msg.text("✨当前玩家:\n")
                for idx, name in enumerate(players.values(), 1):
                    msg.text(f"\n{idx}. {name}")
                await msg.send()


async def prepare_game(event: Event, players: dict[str, str]) -> None:
    from .game import Game

    group = UniMessage.get_target(event)
    Game.starting_games[group] = players

    queue: asyncio.Queue[tuple[str, str, str]] = asyncio.Queue()
    task_receive = asyncio.create_task(_prepare_game_receive(queue, event, group))

    try:
        await _prepare_game_handle(queue, players, event.get_user_id())
    finally:
        task_receive.cancel()
        del Game.starting_games[group]
