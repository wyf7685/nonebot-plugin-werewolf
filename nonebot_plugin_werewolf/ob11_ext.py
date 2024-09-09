import contextlib

from nonebot import on_type
from nonebot.internal.matcher import current_bot
from nonebot_plugin_alconna import UniMessage

from .config import config
from .game import starting_games
from .utils import InputStore, user_in_game


def ob11_ext_enabled() -> bool:
    return False


with contextlib.suppress(ImportError):
    from nonebot.adapters.onebot.v11 import Bot, MessageSegment
    from nonebot.adapters.onebot.v11.event import PokeNotifyEvent

    # 游戏内戳一戳等效 "/stop"
    async def _rule_poke_1(event: PokeNotifyEvent) -> bool:
        if not config.enable_poke:
            return False

        user_id = str(event.user_id)
        group_id = str(event.group_id) if event.group_id is not None else None
        return (
            config.enable_poke
            and (event.target_id == event.self_id)
            and user_in_game(user_id, group_id)
        )

    @on_type(PokeNotifyEvent, rule=_rule_poke_1).handle()
    async def handle_poke_1(event: PokeNotifyEvent) -> None:
        InputStore.put(
            user_id=str(event.user_id),
            group_id=str(event.group_id) if event.group_id is not None else None,
            msg=UniMessage.text("/stop"),
        )

    # 准备阶段戳一戳等效加入游戏
    async def _rule_poke_2(event: PokeNotifyEvent) -> bool:
        if not config.enable_poke or event.group_id is None:
            return False

        user_id = str(event.user_id)
        group_id = str(event.group_id)
        return (
            (event.target_id == event.self_id)
            and not user_in_game(user_id, group_id)
            and group_id in starting_games
        )

    @on_type(PokeNotifyEvent, rule=_rule_poke_2).handle()
    async def handle_poke_2(bot: Bot, event: PokeNotifyEvent) -> None:
        user_id = str(event.user_id)
        group_id = str(event.group_id)
        players = starting_games[group_id]

        if user_id not in players:
            res: dict[str, str] = await bot.get_group_member_info(
                group_id=int(group_id),
                user_id=int(user_id),
            )
            players[user_id] = res.get("card") or res.get("nickname") or user_id
            await bot.send(event, MessageSegment.at(user_id) + "成功加入游戏")

    def ob11_ext_enabled() -> bool:
        if not config.enable_poke:
            return False

        return isinstance(current_bot.get(), Bot)
