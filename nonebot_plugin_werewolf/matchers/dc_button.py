import contextlib

from nonebot import on_type
from nonebot_plugin_alconna import Target, UniMessage
from nonebot_plugin_uninfo import get_session

from ..config import config
from ..utils import BUTTON_ACTION_CACHE, InputStore, extract_session_member_nick
from ._prepare_game import preparing_games

with contextlib.suppress(ImportError, RuntimeError):
    if not config.enable_button:
        raise RuntimeError  # skip matcher definition

    from nonebot.adapters.discord import Bot
    from nonebot.adapters.discord.api.model import (
        ChannelType,
        InteractionCallbackType,
        InteractionResponse,
    )
    from nonebot.adapters.discord.event import MessageComponentInteractionEvent
    from nonebot_plugin_alconna.uniseg.constraint import SupportAdapter, SupportScope

    @on_type(MessageComponentInteractionEvent).handle()
    async def handle_dc_button(
        bot: Bot, event: MessageComponentInteractionEvent
    ) -> None:
        if not (
            event.data.custom_id.startswith("nbp-werewolf_")
            and (action := BUTTON_ACTION_CACHE.get(event.data.custom_id))
        ):
            return

        await bot.create_interaction_response(
            interaction_id=event.id,
            interaction_token=event.token,
            response=InteractionResponse(
                type=InteractionCallbackType.DEFERRED_UPDATE_MESSAGE,
            ),
        )

        session = await get_session(bot, event)
        if session is None:
            return

        user_id = str((event.user or event.member.user).id)
        channel_id = str(event.channel_id)
        is_private = event.message.type == ChannelType.DM
        target = Target(
            channel_id,
            channel=True,
            private=is_private,
            adapter=SupportAdapter.discord,
            self_id=bot.self_id,
            scope=SupportScope.discord,
        )

        if p := preparing_games.get(target):
            name = extract_session_member_nick(session) or user_id
            await p.stream[0].send((event, action, name))
            return

        InputStore.put(
            msg=UniMessage.text(action),
            user_id=user_id,
            group_id=None if is_private else channel_id,
        )
