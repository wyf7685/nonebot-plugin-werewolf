from nonebot import on_command, on_message
from nonebot.adapters import Event
from nonebot_plugin_alconna import MsgTarget, UniMessage, UniMsg

from ..constant import STOP_COMMAND
from ..utils import InputStore
from .depends import rule_in_game

message_in_game = on_message(rule=rule_in_game, priority=10)


@message_in_game.handle()
async def handle_input(event: Event, target: MsgTarget, msg: UniMsg) -> None:
    if target.private:
        InputStore.put(msg, target.id)
    else:
        InputStore.put(msg, event.get_user_id(), target.id)


stopcmd = on_command("stop", rule=rule_in_game, block=True)


@stopcmd.handle()
async def handle_stopcmd(event: Event, target: MsgTarget) -> None:
    await handle_input(event=event, target=target, msg=UniMessage.text(STOP_COMMAND))
