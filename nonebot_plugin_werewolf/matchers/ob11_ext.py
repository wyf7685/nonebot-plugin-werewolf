import contextlib

from nonebot import on_notice
from nonebot.internal.matcher import current_bot
from nonebot_plugin_alconna import MsgTarget, UniMessage

from ..config import config
from ..game import Game
from ..utils import InputStore, user_in_game


def ob11_ext_enabled() -> bool:
    return False


with contextlib.suppress(ImportError):
    from nonebot.adapters.onebot.v11 import Bot
    from nonebot.adapters.onebot.v11.event import PokeNotifyEvent

    # 游戏内戳一戳等效 "/stop"
    async def _rule_poke_stop(bot: Bot, event: PokeNotifyEvent) -> bool:
        if not config.enable_poke:
            return False

        user_id = str(event.user_id)
        group_id = str(event.group_id) if event.group_id is not None else None
        return (
            config.enable_poke
            and (event.target_id == event.self_id)
            and user_in_game(bot.self_id, user_id, group_id)
        )

    @on_notice(rule=_rule_poke_stop).handle()
    async def handle_poke_stop(event: PokeNotifyEvent) -> None:
        InputStore.put(
            msg=UniMessage.text("/stop"),
            user_id=str(event.user_id),
            group_id=str(event.group_id) if event.group_id is not None else None,
        )

    # 准备阶段戳一戳等效加入游戏
    async def _rule_poke_join(
        bot: Bot, event: PokeNotifyEvent, target: MsgTarget
    ) -> bool:
        if not config.enable_poke or event.group_id is None:
            return False

        user_id = str(event.user_id)
        group_id = str(event.group_id)
        return (
            (event.target_id == event.self_id)
            and not user_in_game(bot.self_id, user_id, group_id)
            and any(target.verify(group) for group in Game.starting_games)
        )

    @on_notice(rule=_rule_poke_join).handle()
    async def handle_poke_join(
        bot: Bot,
        event: PokeNotifyEvent,
        target: MsgTarget,
    ) -> None:
        user_id = event.get_user_id()
        group_id = target.id
        players = next(p for g, p in Game.starting_games.items() if target.verify(g))

        if user_id not in players:
            res: dict[str, str] = await bot.get_group_member_info(
                group_id=int(group_id),
                user_id=int(user_id),
            )
            players[user_id] = res.get("card") or res.get("nickname") or user_id
            await UniMessage.at(user_id).text("\n✅成功加入游戏").send(target, bot)

    def ob11_ext_enabled() -> bool:
        if not config.enable_poke:
            return False

        return isinstance(current_bot.get(), Bot)
