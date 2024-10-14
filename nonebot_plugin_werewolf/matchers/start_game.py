import asyncio
import re

import nonebot
import nonebot_plugin_waiter as waiter
from nonebot import on_command
from nonebot.adapters import Bot, Event
from nonebot.rule import to_me
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import MsgTarget, Target, UniMessage, UniMsg
from nonebot_plugin_uninfo import Uninfo

from .._timeout import timeout
from ..config import config
from ..game import Game
from .depends import rule_not_in_game
from .ob11_ext import ob11_ext_enabled

start_game = on_command(
    "werewolf",
    rule=to_me() & rule_not_in_game,
    aliases={"狼人杀"},
)


@start_game.handle()
async def handle_start_warning(target: MsgTarget) -> None:
    if target.private:
        await UniMessage("⚠️请在群组中创建新游戏").finish(reply_to=True)


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
    group = UniMessage.get_target(event)
    Game.starting_games[group] = players

    queue: asyncio.Queue[tuple[str, str, str]] = asyncio.Queue()
    task_receive = asyncio.create_task(_prepare_game_receive(queue, event, group))

    try:
        await _prepare_game_handle(queue, players, event.get_user_id())
    finally:
        task_receive.cancel()
        del Game.starting_games[group]


@start_game.handle()
async def handle_start(
    bot: Bot,
    event: Event,
    target: MsgTarget,
    session: Uninfo,
) -> None:
    admin_id = event.get_user_id()
    msg = (
        UniMessage.at(admin_id)
        .text("\n🎉成功创建游戏\n\n")
        .text("  玩家请 @我 发送 “加入游戏”、“退出游戏”\n")
        .text("  玩家 @我 发送 “当前玩家” 可查看玩家列表\n")
        .text("  游戏发起者 @我 发送 “结束游戏” 可结束当前游戏\n")
        .text("  玩家均加入后，游戏发起者请 @我 发送 “开始游戏”\n")
    )
    if ob11_ext_enabled():
        msg.text("\n可使用戳一戳代替游戏交互中的 “/stop” 命令\n")
    await msg.text("\n游戏准备阶段限时5分钟，超时将自动结束").send()

    admin_name = session.user.nick or session.user.name or admin_id
    if session.member:
        admin_name = session.member.nick or admin_name
    players = {admin_id: admin_name}

    try:
        async with timeout(5 * 60):
            await prepare_game(event, players)
    except TimeoutError:
        await UniMessage.text("⚠️游戏准备超时，已自动结束").finish()

    Game(bot, target, players).start()
