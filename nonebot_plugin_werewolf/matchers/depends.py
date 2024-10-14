import itertools

from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import MsgTarget

from ..game import Game


def user_in_game(self_id: str, user_id: str, group_id: str | None) -> bool:
    if group_id is None:
        return any(
            self_id == p.bot.self_id and user_id == p.user_id
            for p in itertools.chain(*[g.players for g in Game.running_games])
        )

    def check(game: Game) -> bool:
        return self_id == game.group.self_id and group_id == game.group.id

    if game := next(filter(check, Game.running_games), None):
        return any(user_id == player.user_id for player in game.players)

    return False


async def rule_in_game(bot: Bot, event: Event, target: MsgTarget) -> bool:
    if not Game.running_games:
        return False
    if target.private:
        return user_in_game(bot.self_id, target.id, None)
    return user_in_game(bot.self_id, event.get_user_id(), target.id)


async def rule_not_in_game(bot: Bot, event: Event, target: MsgTarget) -> bool:
    return not await rule_in_game(bot, event, target)


async def is_group(target: MsgTarget) -> bool:
    return not target.private
