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
    use_cmd_start=config.use_cmd_start,
    priority=config.matcher_priority.terminate,
)


async def running_game(target: MsgTarget) -> Game:
    if (game := get_running_games().get(target)) is None:
        terminate.skip()
    return game


@terminate.handle()
async def _(game: Annotated[Game, Depends(running_game)]) -> None:
    game.terminate()
    await UniMessage.text("已中止当前群组的游戏进程").finish(reply_to=True)
