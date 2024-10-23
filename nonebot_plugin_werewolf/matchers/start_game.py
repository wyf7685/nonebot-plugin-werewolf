import re

import anyio
import nonebot
import nonebot_plugin_waiter as waiter
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from nonebot import on_command
from nonebot.adapters import Bot, Event
from nonebot.rule import to_me
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import MsgTarget, Target, UniMessage, UniMsg
from nonebot_plugin_uninfo import QryItrface, Uninfo

from ..config import config
from ..constant import STOP_COMMAND_PROMPT
from ..game import Game
from ..utils import extract_session_member_nick
from .depends import rule_not_in_game
from .poke import poke_enabled

start_game = on_command(
    "werewolf",
    rule=to_me() & rule_not_in_game,
    aliases={"狼人杀"},
)


@start_game.handle()
async def handle_start_warning(target: MsgTarget) -> None:
    if target.private:
        await UniMessage("⚠️请在群组中创建新游戏").finish(reply_to=True)


async def _prepare_receive(
    stream: MemoryObjectSendStream[tuple[Event, str, str]],
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
    def wait(event: Event, msg: UniMsg, session: Uninfo) -> tuple[Event, str, str]:
        text = msg.extract_plain_text().strip()
        name = extract_session_member_nick(session) or event.get_user_id()
        return (event, text, name)

    async for evt, text, name in wait(default=(None, "", "")):
        if evt is None:
            continue
        await stream.send((evt, text, re.sub(r"[\u2066-\u2069]", "", name)))


async def _prepare_handle(
    stream: MemoryObjectReceiveStream[tuple[Event, str, str]],
    players: dict[str, str],
    admin_id: str,
    finished: anyio.Event,
) -> None:
    logger = nonebot.logger.opt(colors=True)

    async def send(msg: str, /) -> None:
        await UniMessage.text(msg).send(target=event, reply_to=True)

    while True:
        event, text, name = await stream.receive()
        user_id = event.get_user_id()
        colored = f"<y>{escape_tag(name)}</y>(<c>{escape_tag(user_id)}</c>)"

        # 更新用户名
        # 当用户通过 chronoca:poke 加入游戏时, 插件无法获取用户名, 原字典值为用户ID
        if user_id in players and players.get(user_id) != name:
            logger.debug(f"更新玩家显示名称: {colored}")
            players[user_id] = name

        match (text, user_id == admin_id):
            case ("开始游戏", True):
                player_num = len(players)
                role_preset = config.get_role_preset()
                if player_num < min(role_preset):
                    await send(
                        f"⚠️游戏至少需要 {min(role_preset)} 人, "
                        f"当前已有 {player_num} 人"
                    )
                elif player_num > max(role_preset):
                    await send(
                        f"⚠️游戏最多需要 {max(role_preset)} 人, "
                        f"当前已有 {player_num} 人"
                    )
                elif player_num not in role_preset:
                    await send(f"⚠️不存在总人数为 {player_num} 的预设, 无法开始游戏")
                else:
                    await send("✏️游戏即将开始...")
                    logger.info(f"游戏发起者 {colored} 开始游戏")
                    finished.set()
                    players["#$start_game$#"] = user_id
                    return

            case ("开始游戏", False):
                await send("⚠️只有游戏发起者可以开始游戏")

            case ("结束游戏", True):
                logger.info(f"游戏发起者 {colored} 结束游戏")
                await send("ℹ️已结束当前游戏")
                finished.set()
                return

            case ("结束游戏", False):
                await send("⚠️只有游戏发起者可以结束游戏")

            case ("加入游戏", True):
                await send("ℹ️游戏发起者已经加入游戏了")

            case ("加入游戏", False):
                if user_id not in players:
                    players[user_id] = name
                    logger.info(f"玩家 {colored} 加入游戏")
                    await send("✅成功加入游戏")
                else:
                    await send("ℹ️你已经加入游戏了")

            case ("退出游戏", True):
                await send("ℹ️游戏发起者无法退出游戏")

            case ("退出游戏", False):
                if user_id in players:
                    del players[user_id]
                    logger.info(f"玩家 {colored} 退出游戏")
                    await send("✅成功退出游戏")
                else:
                    await send("ℹ️你还没有加入游戏")

            case ("当前玩家", _):
                await send(
                    "✨当前玩家:\n"
                    + "\n".join(
                        f"{idx}. {players[user_id]}"
                        for idx, user_id in enumerate(players, 1)
                    )
                )


async def prepare_game(event: Event, players: dict[str, str]) -> None:
    admin_id = event.get_user_id()
    group = UniMessage.get_target(event)
    Game.starting_games[group] = players

    finished = anyio.Event()
    send, recv = anyio.create_memory_object_stream[tuple[Event, str, str]]()

    async def _handle_cancel() -> None:
        await finished.wait()
        tg.cancel_scope.cancel()

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(_handle_cancel)
            tg.start_soon(_prepare_receive, send, event, group)
            tg.start_soon(_prepare_handle, recv, players, admin_id, finished)
    except Exception as err:
        await UniMessage(f"狼人杀准备阶段出现未知错误: {err!r}").send()

    del Game.starting_games[group]
    if players.pop("#$start_game$#", None) != admin_id:
        await start_game.finish()


@start_game.handle()
async def handle_start(
    bot: Bot,
    event: Event,
    target: MsgTarget,
    session: Uninfo,
    interface: QryItrface,
) -> None:
    admin_id = event.get_user_id()
    msg = (
        UniMessage.text("🎉成功创建游戏\n\n")
        .text("  玩家请 @我 发送 “加入游戏”、“退出游戏”\n")
        .text("  玩家 @我 发送 “当前玩家” 可查看玩家列表\n")
        .text("  游戏发起者 @我 发送 “结束游戏” 可结束当前游戏\n")
        .text("  玩家均加入后，游戏发起者请 @我 发送 “开始游戏”\n")
    )
    if poke_enabled():
        msg.text(f"\n可使用戳一戳代替游戏交互中的 “{STOP_COMMAND_PROMPT}” 命令\n")
    await msg.text("\n游戏准备阶段限时5分钟，超时将自动结束").send(reply_to=True)

    admin_name = extract_session_member_nick(session) or admin_id
    players = {admin_id: admin_name}

    try:
        with anyio.fail_after(5 * 60):
            await prepare_game(event, players)
    except TimeoutError:
        await UniMessage.text("⚠️游戏准备超时，已自动结束").finish()

    game = Game(bot, target, set(players), interface)
    await game.start()
