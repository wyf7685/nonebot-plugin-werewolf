from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import MsgTarget, get_target

from ..game import game_registry


async def rule_in_game(bot: Bot, event: Event) -> bool:
    if not game_registry.has_running_games():
        return False

    try:
        target = get_target(event, bot)
    except NotImplementedError:
        return False

    if target.private:
        return game_registry.is_user_in_game(bot.self_id, target.id, None)

    try:
        user_id = event.get_user_id()
    except Exception:
        return False

    return game_registry.is_user_in_game(bot.self_id, user_id, target.id)


async def rule_not_in_game(bot: Bot, event: Event) -> bool:
    return not await rule_in_game(bot, event)


async def is_group(target: MsgTarget) -> bool:
    return not target.private
