import json
import re

import anyio
import nonebot
import nonebot_plugin_waiter as waiter
from nonebot.adapters import Bot, Event
from nonebot.internal.matcher import current_bot
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule, to_me
from nonebot.typing import T_State
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import (
    Alconna,
    Button,
    FallbackStrategy,
    MsgTarget,
    Option,
    Target,
    UniMessage,
    UniMsg,
    on_alconna,
)
from nonebot_plugin_localstore import get_plugin_data_file
from nonebot_plugin_uninfo import QryItrface, Uninfo

from ..config import PresetData, config
from ..constant import STOP_COMMAND_PROMPT
from ..game import Game
from ..utils import ObjectStream, extract_session_member_nick
from .depends import rule_not_in_game
from .poke import poke_enabled

start_game = on_alconna(
    Alconna(
        "werewolf",
        Option("restart|--restart|重开", dest="restart"),
    ),
    rule=to_me() & rule_not_in_game,
    aliases={"狼人杀"},
    use_cmd_start=True,
)
player_data_file = get_plugin_data_file("players.json")
if not player_data_file.exists():
    player_data_file.write_text("[]")


def dump_players(target: Target, players: dict[str, str]) -> None:
    data: list[dict] = json.loads(player_data_file.read_text(encoding="utf-8"))

    for item in data:
        if Target.load(item["target"]).verify(target):
            item["players"] = players
            break
    else:
        data.append({"target": target.dump(), "players": players})

    player_data_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_players(target: Target) -> dict[str, str] | None:
    data: list[dict] = json.loads(player_data_file.read_text(encoding="utf-8"))

    for item in data:
        if Target.load(item["target"]).verify(target):
            return item["players"]
    return None


def solve_button(msg: UniMessage) -> UniMessage:
    if config.enable_button:
        msg.keyboard(
            *[
                Button("input", i, text=i)
                for i in ["加入游戏", "退出游戏", "当前玩家", "开始游戏", "结束游戏"]
            ]
        )
    return msg


async def _prepare_receive(
    stream: ObjectStream[tuple[Event, str, str]],
    event_type: str,
    group: Target,
) -> None:
    @Rule
    async def same_group(target: MsgTarget) -> bool:
        return group.verify(target)

    @waiter.waiter(
        waits=[event_type],
        keep_session=False,
        rule=same_group & rule_not_in_game,
    )
    def wait(event: Event, msg: UniMsg, session: Uninfo) -> tuple[Event, str, str]:
        text = msg.extract_plain_text().strip()
        name = extract_session_member_nick(session) or event.get_user_id()
        return (event, text, re.sub(r"[\u2066-\u2069]", "", name))

    async for event, text, name in wait(default=(None, "", "")):
        if event is None:
            continue
        await stream.send((event, text, name))


async def _prepare_handle(
    stream: ObjectStream[tuple[Event, str, str]],
    players: dict[str, str],
    admin_id: str,
) -> None:
    logger = nonebot.logger.opt(colors=True)

    async def send(msg: str, /, *, button: bool = True) -> None:
        message = UniMessage.text(msg)
        if button:
            message = solve_button(message)

        await message.send(
            target=event,
            reply_to=True,
            fallback=FallbackStrategy.ignore,
        )

    while not stream.closed:
        event, text, name = await stream.recv()
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
                role_preset = PresetData.load().role_preset
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
                    stream.close()
                    players["#$start_game$#"] = user_id
                    return

            case ("开始游戏", False):
                await send("⚠️只有游戏发起者可以开始游戏")

            case ("结束游戏", True):
                logger.info(f"游戏发起者 {colored} 结束游戏")
                await send("ℹ️已结束当前游戏", button=False)
                stream.close()
                return

            case ("结束游戏", False):
                if await SUPERUSER(current_bot.get(), event):
                    logger.info(f"超级用户 {colored} 结束游戏")
                    await send("ℹ️已结束当前游戏", button=False)
                    stream.close()
                    return
                await send("⚠️只有游戏发起者或超级用户可以结束游戏")

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

    stream = ObjectStream[tuple[Event, str, str]](16)

    async def _handle_cancel() -> None:
        await stream.wait_closed()
        tg.cancel_scope.cancel()

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(_handle_cancel)
            tg.start_soon(_prepare_receive, stream, event.get_type(), group)
            tg.start_soon(_prepare_handle, stream, players, admin_id)
    except Exception as err:
        await UniMessage(f"狼人杀准备阶段出现未知错误: {err!r}").send()

    del Game.starting_games[group]
    if players.pop("#$start_game$#", None) != admin_id:
        await start_game.finish()


@start_game.handle()
async def handle_notice(target: MsgTarget, state: T_State) -> None:
    if target.private:
        await UniMessage("⚠️请在群组中创建新游戏").finish(reply_to=True)
    if any(target.verify(g.group) for g in Game.running_games):
        await (
            UniMessage.text("⚠️当前群组内有正在进行的游戏\n")
            .text("无法开始新游戏")
            .finish(reply_to=True)
        )

    msg = (
        UniMessage.text("🎉成功创建游戏\n\n")
        .text("  玩家请发送 “加入游戏”、“退出游戏”\n")
        .text("  玩家发送 “当前玩家” 可查看玩家列表\n")
        .text("  游戏发起者发送 “结束游戏” 可结束当前游戏\n")
        .text("  玩家均加入后，游戏发起者请发送 “开始游戏”\n")
    )
    if poke_enabled():
        msg.text(f"\n💫可使用戳一戳代替游戏交互中的 “{STOP_COMMAND_PROMPT}” 命令\n")
    msg.text("\nℹ️游戏准备阶段限时5分钟，超时将自动结束")
    await solve_button(msg).send(reply_to=True, fallback=FallbackStrategy.ignore)

    state["players"] = {}


@start_game.assign("restart")
async def handle_restart(target: MsgTarget, state: T_State) -> None:
    players = load_players(target)
    if players is None:
        await UniMessage.text("ℹ️未找到历史游戏记录，将创建新游戏").send()
        return

    msg = UniMessage.text("🎉成功加载上次游戏:\n")
    for user in players:
        msg.text("\n- ").at(user)
    await msg.send()

    state["players"] = players


@start_game.handle()
async def handle_start(
    bot: Bot,
    event: Event,
    target: MsgTarget,
    session: Uninfo,
    interface: QryItrface,
    state: T_State,
) -> None:
    players: dict[str, str] = state["players"]
    admin_id = event.get_user_id()
    admin_name = extract_session_member_nick(session) or admin_id
    players[admin_id] = admin_name

    try:
        with anyio.fail_after(5 * 60):
            await prepare_game(event, players)
    except TimeoutError:
        await UniMessage.text("⚠️游戏准备超时，已自动结束").finish()

    dump_players(target, players)
    game = Game(bot, target, set(players), interface)
    await game.start()
