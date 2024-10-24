from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot_plugin_alconna import Alconna, MsgTarget, UniMessage, on_alconna

from ..game import Game


def rule_game_running(target: MsgTarget) -> bool:
    return any(target.verify(g.group) for g in Game.running_games)


force_stop = on_alconna(
    Alconna("中止游戏"),
    rule=to_me() & rule_game_running,
    permission=SUPERUSER,
    use_cmd_start=True,
)


@force_stop.handle()
async def _(target: MsgTarget) -> None:
    game = next(g for g in Game.running_games if target.verify(g.group))
    game.terminate()
    await UniMessage.text("已中止当前群组的游戏进程").finish(reply_to=True)
