import contextlib

from nonebot import on_message
from nonebot.internal.matcher import current_event
from nonebot_plugin_alconna import MsgTarget, UniMessage

from ...config import config
from ...constant import STOP_COMMAND
from ...utils import InputStore
from .._prepare_game import preparing_games
from ..depends import user_in_game


def chronocat_poke_enabled() -> bool:
    return False


with contextlib.suppress(ImportError, RuntimeError):
    if not config.enable_poke:
        raise RuntimeError  # skip matcher definition

    from nonebot.adapters.satori import Bot
    from nonebot.adapters.satori.event import (
        MessageCreatedEvent,
        PublicMessageCreatedEvent,
    )

    def extract_poke_tome(event: MessageCreatedEvent) -> str | None:
        if event.login and event.login.platform and event.login.platform != "chronocat":
            return None

        poke = event.get_message().include("chronocat:poke")
        if not poke:
            return None

        gen = (
            seg.data["operatorId"]
            for seg in poke
            if seg.data["userId"] == event.login.sn
        )
        return next(gen, None)

    def extract_user_group(event: MessageCreatedEvent) -> tuple[str, str | None]:
        user_id = event.get_user_id()
        group_id = None
        if isinstance(event, PublicMessageCreatedEvent):
            group_id = (event.guild and event.guild.id) or event.channel.id
        return user_id, group_id

    # 游戏内戳一戳等效 "stop" 命令
    async def _rule_poke_stop(bot: Bot, event: MessageCreatedEvent) -> bool:
        return extract_poke_tome(event) is not None and (
            user_in_game(bot.self_id, *extract_user_group(event))
        )

    @on_message(rule=_rule_poke_stop).handle()
    async def handle_poke_stop(event: MessageCreatedEvent) -> None:
        InputStore.put(
            UniMessage.text(STOP_COMMAND),
            extract_poke_tome(event) or event.get_user_id(),
            extract_user_group(event)[1],
        )

    # 准备阶段戳一戳等效加入游戏
    async def _rule_poke_join(
        bot: Bot,
        event: PublicMessageCreatedEvent,
        target: MsgTarget,
    ) -> bool:
        return (
            (user_id := extract_poke_tome(event)) is not None
            and not user_in_game(
                self_id=bot.self_id,
                user_id=user_id,
                group_id=(event.guild and event.guild.id) or event.channel.id,
            )
            and target in preparing_games
        )

    @on_message(rule=_rule_poke_join).handle()
    async def handle_poke_join(
        bot: Bot,
        event: PublicMessageCreatedEvent,
        target: MsgTarget,
    ) -> None:
        user_id = extract_poke_tome(event) or event.get_user_id()
        players = preparing_games[target].players

        if user_id not in players:
            # XXX:
            #   截止 chronocat v0.2.19
            #   通过 guild.member.get / user.get 获取的用户信息均不包含用户名
            #   跳过用户名获取, 使用用户 ID 代替
            #
            # member = await bot.guild_member_get(
            #     guild_id=(event.guild and event.guild.id) or event.channel.id,
            #     user_id=user_id,
            # )
            # name = member.nick or (
            #     member.user and (member.user.nick or member.user.name)
            # )
            # if name is None:
            #     user = await bot.user_get(user_id=user_id)
            #     name = user.nick or user.name
            # players[user_id] = name or user_id

            players[user_id] = user_id
            await UniMessage.at(user_id).text("\n✅成功加入游戏").send(target, bot)

    def chronocat_poke_enabled() -> bool:
        event = current_event.get()
        return (
            isinstance(event, MessageCreatedEvent)
            and event.login.platform == "chronocat"
        )
