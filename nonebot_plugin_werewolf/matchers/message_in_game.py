from nonebot import on_message
from nonebot.adapters import Event
from nonebot_plugin_alconna import MsgTarget, UniMsg

from ..utils import InputStore, rule_in_game

message_in_game = on_message(rule=rule_in_game)


@message_in_game.handle()
async def handle_input(event: Event, target: MsgTarget, msg: UniMsg) -> None:
    if target.private:
        InputStore.put(msg, target.id)
    else:
        InputStore.put(msg, event.get_user_id(), target.id)
