import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import anyio
import nonebot
import nonebot_plugin_waiter.unimsg as waiter
from nonebot.adapters import Bot, Event
from nonebot.internal.matcher import current_bot
from nonebot.matcher import Matcher
from nonebot.permission import SuperUser
from nonebot.rule import Rule
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import (
    Button,
    MsgTarget,
    Target,
    UniMessage,
    UniMsg,
    get_target,
)
from nonebot_plugin_uninfo import Uninfo

from ..config import PresetData
from ..utils import ObjectStream, btn, extract_session_member_nick
from ..utils import SendHandler as BaseSendHandler
from .depends import rule_not_in_game

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def _btn(text: str) -> Button:
    return btn(text, text)


def solve_button(msg: UniMessage) -> UniMessage:
    return (
        msg.keyboard(_btn("当前玩家"))
        .keyboard(_btn("加入游戏"), _btn("退出游戏"))
        .keyboard(_btn("开始游戏"), _btn("结束游戏"))
    )


preparing_games: dict[Target, "PrepareGame"] = {}


class SendHandler(BaseSendHandler):
    def __init__(
        self,
        target: Event | Target | None = None,
        bot: Bot | None = None,
    ) -> None:
        super().__init__(target, bot)
        self.reply_to = not self._is_dc

    def solve_msg(self, msg: UniMessage) -> UniMessage:
        return solve_button(msg)

    async def send_finished(self) -> None:
        msg = UniMessage.text("ℹ️已结束当前游戏")
        if not self._is_dc:
            msg.keyboard(Button("input", label="发起游戏", text="werewolf")).keyboard(
                Button("input", label="重开上次游戏", text="werewolf restart")
            )
        async with anyio.create_task_group() as tg:
            tg.start_soon(self._edit)
            tg.start_soon(self._send, msg)


class PrepareGame:
    @dataclass
    class _Current:
        id: str
        name: str
        is_admin: bool
        is_super_user: bool

        @property
        def colored(self) -> str:
            return f"<y>{escape_tag(self.name)}</y>(<c>{escape_tag(self.id)}</c>)"

    def __init__(
        self,
        event: Event,
        players: dict[str, str],
        handler: SendHandler,
    ) -> None:
        self.event = event
        self.admin_id = event.get_user_id()
        self.group = get_target(event)
        self.stream = ObjectStream[tuple[Event, str, str]](16)
        self.players = players
        self.send_handler = handler
        self.logger = nonebot.logger.opt(colors=True)
        self.shoud_start_game = False

        self._handlers: dict[str, Callable[[], Awaitable[bool | None]]] = {
            "开始游戏": self._handle_start,
            "结束游戏": self._handle_end,
            "加入游戏": self._handle_join,
            "退出游戏": self._handle_quit,
            "当前玩家": self._handle_list,
        }

    async def run(self) -> None:
        preparing_games[self.group] = self
        try:
            async with anyio.create_task_group() as tg:
                self.task_group = tg
                tg.start_soon(self._wait_cancel)
                tg.start_soon(self._receive)
                tg.start_soon(self._handle)
        except Exception as err:
            self.logger.opt(exception=err).warning("狼人杀准备阶段出现未知错误")
            await UniMessage(f"狼人杀准备阶段出现未知错误: {err!r}").finish()
        finally:
            del preparing_games[self.group]

        if not self.shoud_start_game:
            await Matcher.finish()

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
            self.current = self._Current(
                id=user_id,
                name=name,
                is_admin=(user_id == self.admin_id),
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
