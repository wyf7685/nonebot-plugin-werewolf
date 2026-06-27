import contextlib

from nonebot import on_notice
from nonebot.internal.matcher import current_bot
from nonebot_plugin_alconna import MsgTarget, UniMessage

from ...config import config
from ...constant import STOP_COMMAND
from ...game import game_registry
from ...utils import InputStore
from .._prepare_game import preparing_games


def milky_poke_enabled() -> bool:
    return False


with contextlib.suppress(ImportError, RuntimeError):
    if not config.enable_poke:
        raise RuntimeError  # skip matcher definition

    from nonebot.adapters.milky import Bot
    from nonebot.adapters.milky.event import GroupNudgeEvent

    # 游戏内戳一戳等效 "stop" 命令
    async def _rule_poke_stop(bot: Bot, event: GroupNudgeEvent) -> bool:
        user_id = str(event.data.sender_id)
        group_id = str(event.data.group_id)
        return (
            event.data.receiver_id == event.self_id
        ) and game_registry.is_user_in_game(bot.self_id, user_id, group_id)

    @on_notice(rule=_rule_poke_stop).handle()
    async def handle_poke_stop(event: GroupNudgeEvent) -> None:
        InputStore.put(
            msg=UniMessage.text(STOP_COMMAND),
            user_id=str(event.data.sender_id),
            group_id=str(event.data.group_id),
        )

    # 准备阶段戳一戳等效加入游戏
    async def _rule_poke_join(
        bot: Bot, event: GroupNudgeEvent, target: MsgTarget
    ) -> bool:
        if event.data.group_id is None:
            return False

        user_id = str(event.data.sender_id)
        group_id = str(event.data.group_id)
        return (
            (event.data.receiver_id == event.self_id)
            and not game_registry.is_user_in_game(bot.self_id, user_id, group_id)
            and target in preparing_games
        )

    @on_notice(rule=_rule_poke_join).handle()
    async def handle_poke_join(
        bot: Bot,
        event: GroupNudgeEvent,
        target: MsgTarget,
    ) -> None:
        user_id = event.get_user_id()
        players = preparing_games[target].players

        if event.data.group_id is None or user_id in players:
            return

        member_info = await bot.get_group_member_info(
            group_id=event.data.group_id,
            user_id=event.data.sender_id,
            no_cache=True,
        )
        players[user_id] = member_info.card or member_info.nickname or user_id
        await UniMessage.at(user_id).text("\n✅成功加入游戏").send(target, bot)

    def milky_poke_enabled() -> bool:
        return isinstance(current_bot.get(), Bot)
