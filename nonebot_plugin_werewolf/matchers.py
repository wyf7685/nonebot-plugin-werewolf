import asyncio
import asyncio.timeouts
from typing import Annotated

from nonebot import on_command, on_message
from nonebot.adapters import Bot, Event
from nonebot.exception import FinishedException
from nonebot.rule import to_me
from nonebot_plugin_alconna import MsgTarget, UniMessage, UniMsg
from nonebot_plugin_userinfo import EventUserInfo, UserInfo

from .game import Game, running_games, starting_games
from .ob11_ext import ob11_ext_enabled
from .utils import InputStore, is_group, prepare_game, rule_in_game, rule_not_in_game

in_game_message = on_message(rule=rule_in_game)
start_game = on_command(
    "werewolf",
    rule=to_me() & is_group & rule_not_in_game,
    aliases={"狼人杀"},
)


@in_game_message.handle()
async def handle_input(event: Event, target: MsgTarget, msg: UniMsg) -> None:
    if target.private:
        InputStore.put(target.id, None, msg)
    else:
        InputStore.put(event.get_user_id(), target.id, msg)


@start_game.handle()
async def handle_start(
    bot: Bot,
    event: Event,
    target: MsgTarget,
    admin_info: Annotated[UserInfo, EventUserInfo()],
) -> None:
    if target.id in running_games:
        await UniMessage.text("当前群聊内有正在进行的游戏，无法创建游戏").finish()

    admin_id = event.get_user_id()
    msg = (
        UniMessage.at(admin_id)
        .text("成功创建游戏\n")
        .text("玩家请 @我 发送 “加入游戏”、“退出游戏”\n")
        .text("玩家 @我 发送 “当前玩家” 可查看玩家列表\n")
        .text("游戏发起者 @我 发送 “结束游戏” 可结束当前游戏\n")
        .text("玩家均加入后，游戏发起者请 @我 发送 “开始游戏”\n")
    )
    if ob11_ext_enabled():
        msg.text("\n可使用戳一戳代替游戏交互中的 “/stop” 命令")
    await msg.text("\n\n游戏准备阶段限时5分钟，超时将自动结束").send()

    players = starting_games[target.id] = {admin_id: admin_info.user_name}

    try:
        async with asyncio.timeouts.timeout(5 * 60):
            await prepare_game(event, players)
    except FinishedException:
        raise
    except TimeoutError:
        await UniMessage.text("游戏准备超时，已自动结束").finish()
    finally:
        del starting_games[target.id]

    game = Game(bot=bot, group=target, players=players)
    game.start()
