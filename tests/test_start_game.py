# ruff: noqa: S101

from typing import Any, cast

import pytest
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.matcher import Matcher
from nonebug import App
from pytest_mock import MockerFixture

from .fake import (
    DependentTestWrapper,
    MessageChecker,
    fake_user_id,
    fake_v11_bot,
    fake_v11_group_message_event,
    fake_v11_private_message_event,
)


@pytest.mark.asyncio
async def test_start_game_private(app: App) -> None:
    from nonebot_plugin_werewolf.matchers.start_game import start_game as matcher

    async with app.test_matcher(matcher) as ctx:
        bot = fake_v11_bot(ctx)
        event = fake_v11_private_message_event(
            user_id=fake_user_id(),
            message=Message("werewolf"),
            to_me=True,
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_rule(matcher)
        ctx.should_call_send(
            event, MessageSegment.reply(event.message_id) + "⚠️请在群组中创建新游戏"
        )
        ctx.should_finished()


@pytest.mark.asyncio
async def test_start_game_exists(app: App) -> None:
    from nonebot_plugin_alconna import get_target

    from nonebot_plugin_werewolf.game import get_running_games
    from nonebot_plugin_werewolf.matchers.start_game import start_game as matcher

    async with app.test_matcher(matcher) as ctx:
        bot = fake_v11_bot(ctx)
        event = fake_v11_group_message_event(message=Message("werewolf"), to_me=True)
        target = get_target(event, bot)
        running_games = get_running_games()
        fake_game = cast("Any", lambda: ...)
        fake_game.group = get_target(
            fake_v11_group_message_event(message=Message()), bot
        )
        running_games[target] = fake_game
        ctx.receive_event(bot, event)
        ctx.should_pass_rule(matcher)
        ctx.should_call_send(
            event,
            MessageSegment.reply(event.message_id)
            + "⚠️当前群组内有正在进行的游戏\n无法开始新游戏",
        )
        ctx.should_finished()


@pytest.mark.asyncio
async def test_start_game_normal(app: App) -> None:
    from nonebot_plugin_werewolf.matchers.start_game import handle_notice

    async with (
        DependentTestWrapper() as wrapper,
        app.test_dependent(
            handle_notice,
            allow_types=Matcher.HANDLER_PARAM_TYPES,
        ) as ctx,
    ):
        bot = fake_v11_bot(ctx)
        event = fake_v11_group_message_event(message=Message("werewolf"), to_me=True)
        wrapper.setup(bot, event)
        ctx.pass_params(bot=bot, event=event, state={})
        ctx.should_call_send(
            event,
            MessageChecker(
                lambda _, text: text.startswith("🎉成功创建游戏")
                and "💫可使用戳一戳" in text
                and text.endswith("超时将自动结束")
            ),
        )
        ctx.should_return(None)


@pytest.mark.asyncio
async def test_start_game_restart_not_found(app: App) -> None:
    from nonebot_plugin_werewolf.matchers.start_game import handle_restart

    async with (
        DependentTestWrapper() as wrapper,
        app.test_dependent(
            handle_restart,
            allow_types=Matcher.HANDLER_PARAM_TYPES,
        ) as ctx,
    ):
        bot = fake_v11_bot(ctx)
        event = fake_v11_group_message_event(message=Message("werewolf -r"), to_me=True)
        wrapper.setup(bot, event)
        ctx.pass_params(bot=bot, event=event, state=(state := {}))
        ctx.should_call_send(event, Message("ℹ️未找到历史游戏记录，将创建新游戏"))
        ctx.should_return(None)

    assert "players" not in state


@pytest.mark.asyncio
async def test_start_game_restart_success(app: App, mocker: MockerFixture) -> None:
    from nonebot_plugin_werewolf.matchers.start_game import handle_restart

    fake_players = {str(i) * 10: f"Player{i}" for i in range(1, 7)}
    mock_load_players = mocker.patch(
        "nonebot_plugin_werewolf.matchers.start_game.load_players",
        return_value=fake_players,
    )

    async with (
        DependentTestWrapper() as wrapper,
        app.test_dependent(
            handle_restart,
            allow_types=Matcher.HANDLER_PARAM_TYPES,
        ) as ctx,
    ):
        bot = fake_v11_bot(ctx)
        event = fake_v11_group_message_event(message=Message("werewolf -r"), to_me=True)
        wrapper.setup(bot, event)
        ctx.pass_params(bot=bot, event=event, state=(state := {}))
        ctx.should_call_send(
            event,
            MessageChecker(
                lambda msg, text: text.startswith("🎉成功加载上次游戏:\n")
                and len(msg["at"]) == len(fake_players)
            ),
        )
        ctx.should_return(None)

    mock_load_players.assert_called_once()
    assert state["players"] == fake_players
