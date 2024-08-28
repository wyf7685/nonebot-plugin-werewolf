import asyncio

from nonebot import on_command, on_message, require
from nonebot.adapters import Event, Bot
from nonebot.rule import to_me

require("nonebot_plugin_alconna")
require("nonebot_plugin_waiter")
import nonebot_plugin_waiter as waiter
from nonebot_plugin_alconna import MsgTarget, UniMessage, UniMsg

from .game import Game, player_preset
from .input_store import store

running_games: dict[str, tuple[Game, asyncio.Task[None]]] = {}


async def user_in_game(event: Event, target: MsgTarget) -> bool:
    if not running_games:
        return False

    if target.private:
        user_id = target.id
        games = [*running_games.values()]
    elif target.id in running_games:
        user_id = event.get_user_id()
        games = [running_games[target.id]]
    else:
        return False

    for game, _ in games:
        return any(user_id == player.user_id for player in game.players)
    return False


async def user_not_in_game(event: Event, target: MsgTarget) -> bool:
    return not await user_in_game(event, target)


@on_message(rule=user_in_game).handle()
async def _(event: Event, target: MsgTarget, msg: UniMsg) -> None:
    if target.private:
        store.put(target.id, None, msg)
    else:
        store.put(event.get_user_id(), target.id, msg)


async def is_group(target: MsgTarget) -> bool:
    return not target.private


start_game = on_command("werewolf", rule=to_me() & is_group & user_not_in_game)


@start_game.handle()
async def _(bot: Bot, event: Event, target: MsgTarget) -> None:
    admin_id = event.get_user_id()
    players = [admin_id]
    await (
        UniMessage.at(admin_id)
        .text("成功创建游戏\n")
        .text("玩家请 @我 发送 “加入游戏”、“退出游戏”\n")
        .text("玩家 @我 发送 “当前玩家” 可查看玩家列表\n")
        .text("玩家均加入后，游戏发起者请 @我 发送 “开始游戏”")
        .send()
    )

    async def rule(target_: MsgTarget) -> bool:
        return not target_.private and target_.id == target.id

    @waiter.waiter(
        waits=[event.get_type()],
        keep_session=False,
        rule=to_me() & rule & user_not_in_game,
    )
    def wait(event: Event, msg: UniMsg):
        return event.get_user_id(), msg

    async for user, text in wait(default=(None, UniMessage())):
        if user is None:
            continue

        text = text.extract_plain_text()
        msg = UniMessage.at(user)

        if user == admin_id and text == "开始游戏":
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
                break

        elif text == "加入游戏":
            if user not in players:
                players.append(user)
                await msg.text("成功加入游戏").send()
            else:
                await msg.text("你已经加入游戏了").send()

        elif text == "退出游戏":
            if user in players:
                players.remove(user)
                await msg.text("成功退出游戏").send()
            else:
                await msg.text("你还没有加入游戏").send()

        elif text == "当前玩家":
            msg.text("\n当前玩家:\n")
            for u in players:
                msg.at(u)
            await msg.send()

    game = Game(
        bot,
        target,
        players,
        lambda: running_games.pop(target.id, None) and None,
    )
    task = asyncio.create_task(game.run())
    running_games[target.id] = (game, task)
