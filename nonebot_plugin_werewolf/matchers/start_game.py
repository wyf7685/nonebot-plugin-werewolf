import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import anyio
import nonebot
import nonebot_plugin_waiter.unimsg as waiter
from nonebot.adapters import Bot, Event
from nonebot.internal.matcher import current_bot
from nonebot.permission import SuperUser
from nonebot.rule import Rule, to_me
from nonebot.typing import T_State
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import (
    Alconna,
    Button,
    FallbackStrategy,
    MsgTarget,
    Option,
    Target,
    UniMessage,
    UniMsg,
    get_target,
    on_alconna,
)
from nonebot_plugin_localstore import get_plugin_data_file
from nonebot_plugin_uninfo import QryItrface, Uninfo

from ..config import GameBehavior, PresetData, config
from ..constant import stop_command_prompt
from ..game import Game, get_running_games, get_starting_games
from ..utils import ObjectStream, SendHandler, extract_session_member_nick
from .depends import rule_not_in_game
from .poke import poke_enabled

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

start_game = on_alconna(
    Alconna(
        "werewolf",
        Option("restart|-r|--restart|重开", dest="restart"),
    ),
    rule=to_me() & rule_not_in_game
    if config.get_require_at("start")
    else rule_not_in_game,
    aliases={"狼人杀"},
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


def solve_button(msg: UniMessage) -> UniMessage:
    def btn(text: str) -> Button:
        return Button("input", label=text, text=text)

    return (
        msg.keyboard(btn("当前玩家"))
        .keyboard(btn("加入游戏"), btn("退出游戏"))
        .keyboard(btn("开始游戏"), btn("结束游戏"))
    )


class PrepareGame:
    @dataclass
    class _Current:
        id: str
        name: str
        colored: str
        is_admin: bool
        is_super_user: bool

    class _SendHandler(SendHandler):
        def __init__(self) -> None:
            self.reply_to = True

        def solve_msg(self, msg: UniMessage) -> UniMessage:
            return solve_button(msg)

        async def send_finished(self) -> None:
            btn_start = Button("input", label="发起游戏", text="werewolf")
            btn_restart = Button("input", label="重开上次游戏", text="werewolf restart")
            msg = (
                UniMessage.text("ℹ️已结束当前游戏")
                .keyboard(btn_start)
                .keyboard(btn_restart)
            )
            async with anyio.create_task_group() as tg:
                tg.start_soon(self._edit)
                tg.start_soon(self._send, msg)

    def __init__(self, event: Event, players: dict[str, str]) -> None:
        self.event = event
        self.admin_id = event.get_user_id()
        self.group = get_target(event)
        self.stream = ObjectStream[tuple[Event, str, str]](16)
        self.players = players
        self.send_handler = self._SendHandler()
        self.logger = nonebot.logger.opt(colors=True)
        self.shoud_start_game = False
        get_starting_games()[self.group] = self.players

        self._handlers: dict[str, Callable[[], Awaitable[bool | None]]] = {
            "开始游戏": self._handle_start,
            "结束游戏": self._handle_end,
            "加入游戏": self._handle_join,
            "退出游戏": self._handle_quit,
            "当前玩家": self._handle_list,
        }

    async def run(self) -> None:
        try:
            async with anyio.create_task_group() as tg:
                self.task_group = tg
                tg.start_soon(self._wait_cancel)
                tg.start_soon(self._receive)
                tg.start_soon(self._handle)
        except Exception as err:
            await UniMessage(f"狼人杀准备阶段出现未知错误: {err!r}").finish()

        del get_starting_games()[self.group]
        if not self.shoud_start_game:
            await start_game.finish()

    async def _wait_cancel(self) -> None:
        await self.stream.wait_closed()
        self.task_group.cancel_scope.cancel()

    async def _receive(self) -> None:
        async def same_group(target: MsgTarget) -> bool:
            return self.group.verify(target)

        @waiter.waiter(
            waits=[self.event.get_type()],
            keep_session=False,
            rule=Rule(same_group) & rule_not_in_game,
        )
        def wait(event: Event, msg: UniMsg, session: Uninfo) -> tuple[Event, str, str]:
            text = msg.extract_plain_text().strip()
            name = extract_session_member_nick(session) or event.get_user_id()
            return (event, text, re.sub(r"[\u2066-\u2069]", "", name))

        async for event, text, name in wait(default=(None, "", "")):
            if event is not None:
                await self.stream.send((event, text, name))

    async def _handle(self) -> None:
        bot = current_bot.get()
        superuser = SuperUser()

        while not self.stream.closed:
            event, text, name = await self.stream.recv()
            user_id = event.get_user_id()
            colored = f"<y>{escape_tag(name)}</y>(<c>{escape_tag(user_id)}</c>)"
            self.current = self._Current(
                id=user_id,
                name=name,
                colored=colored,
                is_admin=user_id == self.admin_id,
                is_super_user=await superuser(bot, event),
            )
            self.send_handler.update(event)

            # 更新用户名
            # 当用户通过 chronoca:poke 加入游戏时, 插件无法获取用户名, 原字典值为用户ID
            if user_id in self.players and self.players.get(user_id) != name:
                self.logger.debug(f"更新玩家显示名称: {self.current.colored}")
                self.players[user_id] = name

            handler = self._handlers.get(text)
            if handler is not None and await handler():
                return

    async def _send(self, msg: str | UniMessage) -> None:
        await self.send_handler.send(msg)

    async def _send_finished(self) -> None:
        await self.send_handler.send_finished()

    async def _handle_start(self) -> bool:
        if not self.current.is_admin:
            await self._send("⚠️只有游戏发起者可以开始游戏")
            return False

        player_num = len(self.players)
        role_preset = PresetData.get().role_preset
        if player_num < min(role_preset):
            await self._send(
                f"⚠️游戏至少需要 {min(role_preset)} 人, 当前已有 {player_num} 人"
            )
        elif player_num > max(role_preset):
            await self._send(
                f"⚠️游戏最多需要 {max(role_preset)} 人, 当前已有 {player_num} 人"
            )
        elif player_num not in role_preset:
            await self._send(
                f"⚠️不存在总人数为 {player_num} 的预设, 无法开始游戏\n"
                f"可用的预设总人数: {', '.join(map(str, role_preset))}"
            )
        else:
            await self._send("✏️游戏即将开始...")
            self.logger.info(f"游戏发起者 {self.current.colored} 开始游戏")
            self.stream.close()
            self.shoud_start_game = True
            return True

        return False

    async def _handle_end(self) -> bool:
        if self.current.is_admin or self.current.is_super_user:
            prefix = "游戏发起者" if self.current.is_admin else "超级用户"
            self.logger.info(f"{prefix} {self.current.colored} 结束游戏")
            await self._send_finished()
            self.stream.close()
            return True

        await self._send("⚠️只有游戏发起者或超级用户可以结束游戏")
        return False

    async def _handle_join(self) -> None:
        if self.current.is_admin:
            await self._send("⚠️只有游戏发起者可以开始游戏")
            return

        if self.current.id not in self.players:
            self.players[self.current.id] = self.current.name
            self.logger.info(f"玩家 {self.current.colored} 加入游戏")
            await self._send("✅成功加入游戏")
        else:
            await self._send("ℹ️你已经加入游戏了")

    async def _handle_quit(self) -> None:
        if self.current.is_admin:
            await self._send("ℹ️游戏发起者无法退出游戏")
            return

        if self.current.id in self.players:
            del self.players[self.current.id]
            self.logger.info(f"玩家 {self.current.colored} 退出游戏")
            await self._send("✅成功退出游戏")
        else:
            await self._send("ℹ️你还没有加入游戏")

    async def _handle_list(self) -> None:
        lines = (
            f"{idx}. {self.players[user_id]}"
            for idx, user_id in enumerate(self.players, 1)
        )
        await self._send("✨当前玩家:\n" + "\n".join(lines))


@start_game.handle()
async def handle_notice(target: MsgTarget) -> None:
    if target.private:
        await UniMessage("⚠️请在群组中创建新游戏").finish(reply_to=True)
    if any(target.verify(game.group) for game in get_running_games()):
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
        msg.text(f"\n💫可使用戳一戳代替游戏交互中的 “{stop_command_prompt()}” 命令\n")
    msg.text("\nℹ️游戏准备阶段限时5分钟，超时将自动结束")
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
    bot: Bot,
    event: Event,
    target: MsgTarget,
    session: Uninfo,
    interface: QryItrface,
    state: T_State,
) -> None:
    players: dict[str, str] = state.get("players", {})
    admin_id = event.get_user_id()
    admin_name = extract_session_member_nick(session) or admin_id
    players[admin_id] = admin_name

    try:
        with anyio.fail_after(GameBehavior.get().timeout.prepare):
            await PrepareGame(event, players).run()
    except TimeoutError:
        await UniMessage.text("⚠️游戏准备超时，已自动结束").finish()

    dump_players(target, players)
    game = await Game.new(bot, target, set(players), interface)
    await game.start()
