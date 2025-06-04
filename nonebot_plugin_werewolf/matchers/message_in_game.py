from nonebot import on_message
from nonebot.adapters import Event
from nonebot_plugin_alconna import Alconna, MsgTarget, UniMessage, UniMsg, on_alconna

from ..config import config
from ..constant import STOP_COMMAND
from ..utils import InputStore
from .depends import rule_in_game

message_in_game = on_message(
    rule=rule_in_game,
    priority=config.matcher_priority.in_game,
)


@message_in_game.handle()
async def handle_input(event: Event, target: MsgTarget, msg: UniMsg) -> None:
    if target.private:
        InputStore.put(msg, target.id)
    else:
        InputStore.put(msg, event.get_user_id(), target.id)


stopcmd = on_alconna(
    Alconna(config.get_stop_command()[0]),
    rule=rule_in_game,
    block=True,
    aliases=set(aliases) if (aliases := config.get_stop_command()[1:]) else None,
    use_cmd_start=config.use_cmd_start,
    priority=config.matcher_priority.stop,
)


@stopcmd.handle()
async def handle_stopcmd(event: Event, target: MsgTarget) -> None:
    await handle_input(event=event, target=target, msg=UniMessage.text(STOP_COMMAND))
