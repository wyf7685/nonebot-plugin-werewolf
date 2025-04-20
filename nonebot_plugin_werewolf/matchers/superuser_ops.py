from typing import Annotated

from nonebot.params import Depends
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot_plugin_alconna import Alconna, MsgTarget, UniMessage, on_alconna

from ..config import config
from ..game import Game, get_running_games

terminate = on_alconna(
    Alconna("中止游戏"),
    rule=to_me() if config.get_require_at("terminate") else None,
    permission=SUPERUSER,
    priority=config.matcher_priority.terminate,
)


async def running_game(target: MsgTarget) -> Game:
    for game in get_running_games():
        if target.verify(game.group):
            return game
    return terminate.skip()


RunningGame = Annotated[Game, Depends(running_game)]


@terminate.handle()
async def _(game: RunningGame) -> None:
    game.terminate()
    await UniMessage.text("已中止当前群组的游戏进程").finish(reply_to=True)
