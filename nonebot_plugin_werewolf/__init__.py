import asyncio
import contextlib
from typing import Annotated

from nonebot import on_command, on_message, on_type, require
from nonebot.adapters import Bot, Event
from nonebot.rule import to_me

require("nonebot_plugin_alconna")
require("nonebot_plugin_userinfo")
require("nonebot_plugin_waiter")
from nonebot_plugin_alconna import MsgTarget, UniMessage, UniMsg
from nonebot_plugin_userinfo import EventUserInfo, UserInfo
from nonebot_plugin_waiter import waiter

from .config import config
from .game import Game, player_preset
from .utils import InputStore

running_games: dict[str, tuple[Game, asyncio.Task[None]]] = {}


async def user_in_game(event: Event, target: MsgTarget) -> bool:
    if not running_games:
        return False

    if target.private:
        user_id = target.id
        games = running_games.values()
    elif target.id in running_games:
        user_id = event.get_user_id()
        games = [running_games[target.id]]
    else:
        return False

    for game, _ in games:
        return any(user_id == player.user_id for player in game.players)
    return False


async def user_not_in_game(event: Event, target: MsgTarget) -> bool:
    return not await user_in_game(event, target)


@on_message(rule=user_in_game).handle()
async def handle_input(event: Event, target: MsgTarget, msg: UniMsg) -> None:
    if target.private:
        InputStore.put(target.id, None, msg)
    else:
        InputStore.put(event.get_user_id(), target.id, msg)


async def is_group(target: MsgTarget) -> bool:
    return not target.private


@on_command(
    "werewolf",
    rule=to_me() & is_group & user_not_in_game,
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
    await msg.send()

    async def rule(target_: MsgTarget) -> bool:
        return not target_.private and target_.id == target.id

    @waiter(
        waits=[event.get_type()],
        keep_session=False,
        rule=to_me() & rule & user_not_in_game,
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

    players = {admin_id: admin_info.user_name}
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
                    break

            case ("结束游戏", True):
                await msg.text("已结束当前游戏").finish()

            case ("加入游戏", False):
                if user not in players:
                    players[user] = name
                    await msg.text("成功加入游戏").send()
                else:
                    await msg.text("你已经加入游戏了").send()

            case ("退出游戏", False):
                if user in players:
                    del players[user]
                    await msg.text("成功退出游戏").send()
                else:
                    await msg.text("你还没有加入游戏").send()

            case ("当前玩家", _):
                msg.text("\n当前玩家:\n")
                for u in players:
                    msg.at(u)
                await msg.send()

    game = Game(
        bot,
        target,
        players,
        lambda: running_games.pop(target.id, None) and None,
    )
    task = asyncio.create_task(game.run())
    running_games[target.id] = (game, task)


# OneBot V11 扩展: 戳一戳等效 "/stop"
OneBotV11Available = False
with contextlib.suppress(ImportError):
    from nonebot.adapters.onebot.v11.event import PokeNotifyEvent

    OneBotV11Available = True

    @on_type(PokeNotifyEvent).handle()
    async def handle_poke(bot: Bot, event: PokeNotifyEvent):
        if str(event.target_id) == bot.self_id:
            InputStore.put(
                str(event.user_id),
                str(event.group_id) if event.group_id is not None else None,
                UniMessage.text("/stop"),
            )
