from typing import Annotated

from nonebot import on_command, on_message
from nonebot.adapters import Bot, Event
from nonebot.exception import FinishedException
from nonebot.rule import to_me
from nonebot_plugin_alconna import MsgTarget, UniMessage, UniMsg
from nonebot_plugin_userinfo import EventUserInfo, UserInfo

from ._timeout import timeout
from .game import Game
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

    players = {admin_id: admin_info.user_name}

    try:
        async with timeout(5 * 60):
            await prepare_game(event, players)
    except FinishedException:
        raise
    except TimeoutError:
        await UniMessage.text("游戏准备超时，已自动结束").finish()

    game = Game(bot, target, players)
    game.start()
