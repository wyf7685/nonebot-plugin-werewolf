import asyncio
import asyncio.timeouts
import contextlib
from typing import Annotated

from nonebot import on_command, on_message, on_type, require
from nonebot.adapters import Bot, Event
from nonebot.rule import to_me

require("nonebot_plugin_alconna")
require("nonebot_plugin_userinfo")
require("nonebot_plugin_waiter")
import nonebot_plugin_waiter as waiter
from nonebot_plugin_alconna import MsgTarget, UniMessage, UniMsg
from nonebot_plugin_userinfo import EventUserInfo, UserInfo

from .config import config
from .game import Game, player_preset
from .utils import InputStore


starting_games: dict[str, dict[str, str]] = {}
running_games: dict[str, tuple[Game, asyncio.Task[None]]] = {}


def user_in_game(user_id: str, group_id: str | None):
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


@on_message(rule=rule_in_game).handle()
async def handle_input(event: Event, target: MsgTarget, msg: UniMsg) -> None:
    if target.private:
        InputStore.put(target.id, None, msg)
    else:
        InputStore.put(event.get_user_id(), target.id, msg)


async def is_group(target: MsgTarget) -> bool:
    return not target.private


async def prepare_game(
    wait: waiter.Waiter[tuple[str, str, str]],
    players: dict[str, str],
    admin_id: str,
):
    async for user, name, text in wait(default=(None, "", "")):
        if user is None:
            continue
        msg = UniMessage.at(user)

        match (text, user == admin_id):
            case ("开始游戏", True):
                if len(players) < min(player_preset):
                    await (
                        msg.text(f"游戏至少需要 {min(player_preset)} 人, ")
                        .text(f"当前已有 {len(players)} 人")
                        .send()
                    )
                elif len(players) > max(player_preset):
                    await (
                        msg.text(f"游戏最多需要 {max(player_preset)} 人, ")
                        .text(f"当前已有 {len(players)} 人")
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


@on_command(
    "werewolf",
    rule=to_me() & is_group & rule_not_in_game,
    aliases={"狼人杀"},
).handle()
async def handle_start(
    bot: Bot,
    event: Event,
    target: MsgTarget,
    admin_info: Annotated[UserInfo, EventUserInfo()],
) -> None:
    admin_id = event.get_user_id()
    msg = (
        UniMessage.at(admin_id)
        .text("成功创建游戏\n")
        .text("玩家请 @我 发送 “加入游戏”、“退出游戏”\n")
        .text("玩家 @我 发送 “当前玩家” 可查看玩家列表\n")
        .text("游戏发起者 @我 发送 “结束游戏” 可结束当前游戏\n")
        .text("玩家均加入后，游戏发起者请 @我 发送 “开始游戏”\n")
    )
    if (
        config.enable_poke
        and OneBotV11Available
        and bot.adapter.get_name() == "OneBot V11"
    ):
        msg.text("\n可使用戳一戳代替游戏交互中的 “/stop” 命令")
    await msg.text("\n\n游戏准备阶段限时5分钟，超时将自动结束").send()

    async def rule(target_: MsgTarget) -> bool:
        return not target_.private and target_.id == target.id

    @waiter.waiter(
        waits=[event.get_type()],
        keep_session=False,
        rule=to_me() & rule & rule_not_in_game,
    )
    def wait(
        event: Event,
        info: Annotated[UserInfo | None, EventUserInfo()],
        msg: UniMsg,
    ):
        return (
            event.get_user_id(),
            info.user_name if info is not None else event.get_user_id(),
            msg.extract_plain_text().strip(),
        )

    starting_games[target.id] = {admin_id: admin_info.user_name}

    try:
        async with asyncio.timeouts.timeout(5 * 60):
            await prepare_game(wait, starting_games[target.id], admin_id)
    except TimeoutError:
        await UniMessage.text("游戏准备超时，已自动结束").finish()

    game = Game(
        bot=bot,
        group=target,
        players=starting_games[target.id],
        on_exit=lambda: running_games.pop(target.id, None) and None,
    )
    task = asyncio.create_task(game.run())
    running_games[target.id] = (game, task)
    del starting_games[target.id]


# OneBot V11 扩展: 戳一戳等效 "/stop"
OneBotV11Available = False
with contextlib.suppress(ImportError):
    from nonebot.adapters.onebot.v11 import Bot as V11Bot, MessageSegment
    from nonebot.adapters.onebot.v11.event import PokeNotifyEvent

    OneBotV11Available = True

    async def _rule_poke(event: PokeNotifyEvent):
        return (event.target_id == event.self_id) and user_in_game(
            user_id=event.get_user_id(),
            group_id=str(event.group_id) if event.group_id else None,
        )

    @on_type(PokeNotifyEvent, rule=_rule_poke).handle()
    async def handle_poke(bot: V11Bot, event: PokeNotifyEvent):
        user_id = str(event.user_id)
        group_id = str(event.group_id) if event.group_id is not None else None
        InputStore.put(user_id, group_id, UniMessage.text("/stop"))

        if group_id is not None:
            players = starting_games.get(str(event.group_id))
            if players is not None:
                res: dict[str, str] = await bot.get_group_member_info(
                    group_id=int(group_id),
                    user_id=int(user_id),
                )
                players[user_id] = res.get("nickname") or user_id
                await bot.send(event, MessageSegment.at(user_id) + "成功加入游戏")
