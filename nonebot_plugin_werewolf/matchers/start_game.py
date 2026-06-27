import json

import anyio
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot_plugin_alconna import (
    Alconna,
    FallbackStrategy,
    MsgTarget,
    Option,
    Target,
    UniMessage,
    on_alconna,
)
from nonebot_plugin_localstore import get_plugin_data_file
from nonebot_plugin_uninfo import QryItrface, Uninfo

from ..config import GameBehavior, config, stop_command_prompt
from ..game import Game, game_registry
from ..utils import extract_session_member_nick
from ._prepare_game import PrepareGame, solve_button
from .depends import rule_not_in_game
from .poke import poke_enabled

start_game = on_alconna(
    Alconna(
        "werewolf",
        Option("restart|-r|--restart|重开", dest="restart"),
    ),
    rule=to_me() & rule_not_in_game
    if config.get_require_at("start")
    else rule_not_in_game,
    aliases={"狼人杀"},
    use_cmd_start=config.use_cmd_start,
    priority=config.matcher_priority.start,
)
player_data_file = get_plugin_data_file("players.json")
if not player_data_file.exists():
    player_data_file.write_text("[]")


def dump_players(target: Target, players: dict[str, str]) -> None:
    data: list[dict] = json.loads(player_data_file.read_text(encoding="utf-8"))

    for item in data:
        if Target.load(item["target"]).verify(target):
            item["players"] = players
            break
    else:
        data.append({"target": target.dump(), "players": players})

    player_data_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_players(target: Target) -> dict[str, str] | None:
    for item in json.loads(player_data_file.read_text(encoding="utf-8")):
        if Target.load(item["target"]).verify(target):
            return item["players"]
    return None


@start_game.handle()
async def handle_notice(target: MsgTarget) -> None:
    if target.private:
        await UniMessage.text("⚠️请在群组中创建新游戏").finish(reply_to=True)
    if game_registry.get(target) is not None:
        await (
            UniMessage.text("⚠️当前群组内有正在进行的游戏\n")
            .text("无法开始新游戏")
            .finish(reply_to=True)
        )

    msg = UniMessage.text(
        "🎉成功创建游戏\n\n"
        "  玩家请发送 “加入游戏”、“退出游戏”\n"
        "  玩家发送 “当前玩家” 可查看玩家列表\n"
        "  游戏发起者发送 “结束游戏” 可结束当前游戏\n"
        "  玩家均加入后，游戏发起者请发送 “开始游戏”\n"
    )
    if poke_enabled():
        msg.text(f"\n💫可使用戳一戳代替游戏交互中的 “{stop_command_prompt}” 命令\n")

    prepare_timeout = GameBehavior.get().timeout.prepare
    msg.text(f"\nℹ️游戏准备阶段限时{prepare_timeout / 60:.1f}分钟，超时将自动结束")
    await solve_button(msg).send(reply_to=True, fallback=FallbackStrategy.ignore)


@start_game.assign("restart")
async def handle_restart(target: MsgTarget, state: T_State) -> None:
    players = load_players(target)
    if players is None:
        await UniMessage.text("ℹ️未找到历史游戏记录，将创建新游戏").send()
        return

    msg = UniMessage.text("🎉成功加载上次游戏:\n")
    for user in players:
        msg.text("\n- ").at(user)
    await msg.send()

    state["players"] = players


@start_game.handle()
async def handle_start(
    state: T_State,
    session: Uninfo,
    target: MsgTarget,
    interface: QryItrface,
) -> None:
    players: dict[str, str] = state.get("players", {})
    admin_id = session.user.id
    admin_name = extract_session_member_nick(session) or admin_id
    players[admin_id] = admin_name

    with anyio.move_on_after(GameBehavior.get().timeout.prepare) as scope:
        await PrepareGame(admin_id, players).run()
    if scope.cancelled_caught:
        await UniMessage.text("⚠️游戏准备超时，已自动结束").finish(reply_to=True)

    dump_players(target, players)
    game = await Game.new(target, set(players), interface)
    game.start()
