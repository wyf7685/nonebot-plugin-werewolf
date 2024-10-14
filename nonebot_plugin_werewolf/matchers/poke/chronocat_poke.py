import contextlib

from nonebot import on_message
from nonebot.internal.matcher import current_bot
from nonebot_plugin_alconna import MsgTarget, UniMessage

from ...config import config
from ...game import Game
from ...utils import InputStore
from ..depends import user_in_game


def chronocat_poke_enabled() -> bool:
    return False


with contextlib.suppress(ImportError):
    from nonebot.adapters.satori import Bot
    from nonebot.adapters.satori.event import (
        MessageCreatedEvent,
        PublicMessageCreatedEvent,
    )

    def check_poke_tome(
        event: MessageCreatedEvent,
    ) -> bool:
        if event.login and event.login.platform and event.login.platform != "chronocat":
            return False

        poke = event.get_message().include("chronocat:poke")
        if not poke:
            return False

        return any(seg.data["userId"] == event.self_id for seg in poke)

    def extract_user_group(event: MessageCreatedEvent) -> tuple[str, str | None]:
        user_id = event.get_user_id()
        group_id = None
        if isinstance(event, PublicMessageCreatedEvent):
            group_id = (event.guild and event.guild.id) or event.channel.id
        return user_id, group_id

    # 游戏内戳一戳等效 "/stop"
    async def _rule_poke_stop(bot: Bot, event: MessageCreatedEvent) -> bool:
        if not config.enable_poke:
            return False
        return check_poke_tome(event) and (
            user_in_game(bot.self_id, *extract_user_group(event))
        )

    @on_message(rule=_rule_poke_stop).handle()
    async def handle_poke_stop(event: MessageCreatedEvent) -> None:
        InputStore.put(UniMessage.text("/stop"), *extract_user_group(event))

    # 准备阶段戳一戳等效加入游戏
    async def _rule_poke_join(
        bot: Bot, event: MessageCreatedEvent, target: MsgTarget
    ) -> bool:
        if not config.enable_poke:
            return False

        user_id, group_id = extract_user_group(event)

        return (
            group_id is not None
            and check_poke_tome(event)
            and not user_in_game(bot.self_id, user_id, group_id)
            and any(target.verify(group) for group in Game.starting_games)
        )

    @on_message(rule=_rule_poke_join).handle()
    async def handle_poke_join(
        bot: Bot,
        event: MessageCreatedEvent,
        target: MsgTarget,
    ) -> None:
        user_id = event.get_user_id()
        players = next(p for g, p in Game.starting_games.items() if target.verify(g))

        if user_id not in players:
            players.add(user_id)
            await UniMessage.at(user_id).text("\n✅成功加入游戏").send(target, bot)

    def chronocat_poke_enabled() -> bool:
        if not config.enable_poke:
            return False

        return isinstance(current_bot.get(), Bot)
