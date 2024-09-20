from typing import Annotated

from nonebot import on_command
from nonebot.adapters import Bot, Event
from nonebot.rule import to_me
from nonebot_plugin_alconna import MsgTarget, UniMessage
from nonebot_plugin_userinfo import EventUserInfo, UserInfo

from .._timeout import timeout
from ..game import Game
from ..ob11_ext import ob11_ext_enabled
from ..utils import prepare_game, rule_not_in_game

start_game = on_command(
    "werewolf",
    rule=to_me() & rule_not_in_game,
    aliases={"狼人杀"},
)


@start_game.handle()
async def handle_start_warning(target: MsgTarget) -> None:
    if target.private:
        await UniMessage("⚠️请在群组中创建新游戏").finish(reply_to=True)


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
        .text("\n⚙️成功创建游戏\n\n")
        .text("玩家请 @我 发送 “加入游戏”、“退出游戏”\n")
        .text("玩家 @我 发送 “当前玩家” 可查看玩家列表\n")
        .text("游戏发起者 @我 发送 “结束游戏” 可结束当前游戏\n")
        .text("玩家均加入后，游戏发起者请 @我 发送 “开始游戏”\n")
    )
    if ob11_ext_enabled():
        msg.text("\n可使用戳一戳代替游戏交互中的 “/stop” 命令\n")
    await msg.text("\n游戏准备阶段限时5分钟，超时将自动结束").send()

    players = {admin_id: admin_info.user_name}

    try:
        async with timeout(5 * 60):
            await prepare_game(event, players)
    except TimeoutError:
        await UniMessage.text("游戏准备超时，已自动结束").finish()

    Game(bot, target, players).start()
