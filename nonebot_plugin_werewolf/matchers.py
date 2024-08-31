import asyncio
import asyncio.timeouts
import contextlib
from typing import Annotated

import nonebot_plugin_waiter as waiter
from nonebot import on_command, on_message, on_type
from nonebot.adapters import Bot, Event
from nonebot.rule import to_me
from nonebot_plugin_alconna import MsgTarget, UniMessage, UniMsg
from nonebot_plugin_userinfo import EventUserInfo, UserInfo

from .config import config
from .game import Game, player_preset
from .utils import InputStore

starting_games: dict[str, dict[str, str]] = {}
running_games: dict[str, tuple[Game, asyncio.Task[None]]] = {}


def user_in_game(user_id: str, group_id: str | None) -> bool:
    if group_id is not None and group_id not in running_games:
        return False
    games = running_games.values() if group_id is None else [running_games[group_id]]
    for game, _ in games:
        return any(user_id == player.user_id for player in game.players)
    return False


async def rule_in_game(event: Event, target: MsgTarget) -> bool:
    if not running_games:
        return False
    if target.private:
        return user_in_game(target.id, None)
    elif target.id in running_games:
        return user_in_game(event.get_user_id(), target.id)
    return False


async def rule_not_in_game(event: Event, target: MsgTarget) -> bool:
    return not await rule_in_game(event, target)


@on_message(rule=rule_in_game).handle()
async def handle_input(event: Event, target: MsgTarget, msg: UniMsg) -> None:
    if target.private:
        InputStore.put(target.id, None, msg)
    else:
        InputStore.put(event.get_user_id(), target.id, msg)


async def is_group(target: MsgTarget) -> bool:
    return not target.private


async def prepare_game(
    wait: waiter.Waiter[tuple[str, str, str]],
    players: dict[str, str],
    group_id: str,
    admin_id: str,
):
    async for user, name, text in wait(default=(None, "", "")):
        if user is None:
            continue
        msg = UniMessage.at(user)

        match (text, user == admin_id):
            case ("开始游戏", True):
                if len(players) < min(player_preset):
                    await (
                        msg.text(f"游戏至少需要 {min(player_preset)} 人, ")
                        .text(f"当前已有 {len(players)} 人")
                        .send()
                    )
                elif len(players) > max(player_preset):
                    await (
                        msg.text(f"游戏最多需要 {max(player_preset)} 人, ")
                        .text(f"当前已有 {len(players)} 人")
                        .send()
                    )
                else:
                    await msg.text("游戏即将开始...").send()
                    return

            case ("开始游戏", False):
                await msg.text("只有游戏发起者可以开始游戏").send()

            case ("结束游戏", True):
                del starting_games[group_id]
                await msg.text("已结束当前游戏").finish()

            case ("结束游戏", False):
                await msg.text("只有游戏发起者可以结束游戏").send()

            case ("加入游戏", True):
                await msg.text("游戏发起者已经加入游戏了").send()

            case ("加入游戏", False):
                if user not in players:
                    players[user] = name
                    await msg.text("成功加入游戏").send()
                else:
                    await msg.text("你已经加入游戏了").send()

            case ("退出游戏", True):
                await msg.text("游戏发起者无法退出游戏").send()

            case ("退出游戏", False):
                if user in players:
                    del players[user]
                    await msg.text("成功退出游戏").send()
                else:
                    await msg.text("你还没有加入游戏").send()

            case ("当前玩家", _):
                msg.text("\n当前玩家:\n")
                for name in players.values():
                    msg.text(f"\n{name}")
                await msg.send()


@on_command(
    "werewolf",
    rule=to_me() & is_group & rule_not_in_game,
    aliases={"狼人杀"},
).handle()
async def handle_start(
    bot: Bot,
    event: Event,
    target: MsgTarget,
    admin_info: Annotated[UserInfo, EventUserInfo()],
) -> None:
    admin_id = event.get_user_id()
    msg = (
        UniMessage.at(admin_id)
        .text("成功创建游戏\n")
        .text("玩家请 @我 发送 “加入游戏”、“退出游戏”\n")
        .text("玩家 @我 发送 “当前玩家” 可查看玩家列表\n")
        .text("游戏发起者 @我 发送 “结束游戏” 可结束当前游戏\n")
        .text("玩家均加入后，游戏发起者请 @我 发送 “开始游戏”\n")
    )
    if (
        config.enable_poke
        and OneBotV11Available
        and bot.adapter.get_name() == "OneBot V11"
    ):
        msg.text("\n可使用戳一戳代替游戏交互中的 “/stop” 命令")
    await msg.text("\n\n游戏准备阶段限时5分钟，超时将自动结束").send()

    async def rule(target_: MsgTarget) -> bool:
        return not target_.private and target_.id == target.id

    @waiter.waiter(
        waits=[event.get_type()],
        keep_session=False,
        rule=to_me() & rule & rule_not_in_game,
    )
    def wait(
        event: Event,
        info: Annotated[UserInfo | None, EventUserInfo()],
        msg: UniMsg,
    ):
        return (
            event.get_user_id(),
            info.user_name if info is not None else event.get_user_id(),
            msg.extract_plain_text().strip(),
        )

    starting_games[target.id] = players = {admin_id: admin_info.user_name}

    try:
        async with asyncio.timeouts.timeout(5 * 60):
            await prepare_game(wait, players, target.id, admin_id)
    except TimeoutError:
        del starting_games[target.id]
        await UniMessage.text("游戏准备超时，已自动结束").finish()

    game = Game(
        bot=bot,
        group=target,
        players=players,
        on_exit=lambda: running_games.pop(target.id, None) and None,
    )
    task = asyncio.create_task(game.run())
    running_games[target.id] = (game, task)
    del starting_games[target.id]


# OneBot V11 扩展
OneBotV11Available = False
with contextlib.suppress(ImportError, RuntimeError):
    if not config.enable_poke:
        raise RuntimeError

    from nonebot.adapters.onebot.v11 import Bot as V11Bot
    from nonebot.adapters.onebot.v11 import MessageSegment
    from nonebot.adapters.onebot.v11.event import PokeNotifyEvent

    OneBotV11Available = True

    # 游戏内戳一戳等效 "/stop"
    async def _rule_poke_1(event: PokeNotifyEvent) -> bool:
        user_id = str(event.user_id)
        group_id = str(event.group_id) if event.group_id is not None else None
        return (event.target_id == event.self_id) and user_in_game(user_id, group_id)

    @on_type(PokeNotifyEvent, rule=_rule_poke_1).handle()
    async def handle_poke_1(event: PokeNotifyEvent) -> None:
        InputStore.put(
            user_id=str(event.user_id),
            group_id=str(event.group_id) if event.group_id is not None else None,
            msg=UniMessage.text("/stop"),
        )

    # 准备阶段戳一戳等效加入游戏
    async def _rule_poke_2(event: PokeNotifyEvent) -> bool:
        if event.group_id is None:
            return False

        user_id = str(event.user_id)
        group_id = str(event.group_id)
        return (
            (event.target_id == event.self_id)
            and not user_in_game(user_id, group_id)
            and group_id in starting_games
        )

    @on_type(PokeNotifyEvent, rule=_rule_poke_2).handle()
    async def handle_poke_2(bot: V11Bot, event: PokeNotifyEvent) -> None:
        user_id = str(event.user_id)
        group_id = str(event.group_id)
        players = starting_games[group_id]

        if user_id not in players:
            res: dict[str, str] = await bot.get_group_member_info(
                group_id=int(group_id),
                user_id=int(user_id),
            )
            players[user_id] = res.get("nickname") or user_id
            await bot.send(event, MessageSegment.at(user_id) + "成功加入游戏")
