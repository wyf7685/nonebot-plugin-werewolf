import contextlib
import functools
import secrets
from collections import Counter
from typing import NoReturn, final
from typing_extensions import Self

import anyio
import nonebot
from nonebot.adapters import Bot
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import At, Target, UniMessage
from nonebot_plugin_alconna.uniseg.receipt import Receipt
from nonebot_plugin_uninfo import Interface, Scene, SceneType

from .config import GameBehavior, PresetData
from .constant import GAME_STATUS_CONV, REPORT_TEXT, ROLE_EMOJI, ROLE_NAME_CONV
from .exception import GameFinished
from .models import GameState, GameStatus, KillInfo, KillReason, Role, RoleGroup
from .player import Player
from .player_set import PlayerSet
from .utils import InputStore, ObjectStream, SendHandler, add_stop_button, link

logger = nonebot.logger.opt(colors=True)
starting_games: dict[Target, dict[str, str]] = {}
running_games: set["Game"] = set()


def get_starting_games() -> dict[Target, dict[str, str]]:
    return starting_games


def get_running_games() -> set["Game"]:
    return running_games


async def init_players(
    bot: Bot,
    game: "Game",
    players: set[str],
    interface: Interface,
) -> PlayerSet:
    logger.debug(f"初始化 {game.colored_name} 的玩家职业")

    preset_data = PresetData.get()
    if (preset := preset_data.role_preset.get(len(players))) is None:
        raise ValueError(
            f"玩家人数不符: "
            f"应为 {', '.join(map(str, preset_data.role_preset))} 人, "
            f"传入{len(players)}人"
        )

    w, p, c = preset
    roles: list[Role] = []
    roles.extend(preset_data.werewolf_priority[:w])
    roles.extend(preset_data.priesthood_proirity[:p])
    roles.extend([Role.CIVILIAN] * c)

    if c >= 2 and secrets.randbelow(100) <= preset_data.jester_probability * 100:
        roles.remove(Role.CIVILIAN)
        roles.append(Role.JESTER)

    def _select_role() -> Role:
        return roles.pop(secrets.randbelow(len(roles)))

    player_set = PlayerSet()
    for user_id in players:
        player_set.add(await Player.new(_select_role(), bot, game, user_id, interface))

    logger.debug(f"职业分配完成: <e>{escape_tag(str(player_set))}</e>")
    return player_set


class _SendHandler(SendHandler[str | None]):
    def solve_msg(
        self,
        msg: UniMessage,
        stop_btn_label: str | None = None,
    ) -> UniMessage:
        if stop_btn_label is not None:
            msg = add_stop_button(msg, stop_btn_label)
        return msg


class DeadChannel:
    players: PlayerSet
    finished: anyio.Event
    counter: dict[str, int]
    stream: ObjectStream[tuple[Player, UniMessage]]

    def __init__(self, players: PlayerSet, finished: anyio.Event) -> None:
        self.players = players
        self.finished = finished
        self.counter = {p.user_id: 0 for p in players}
        self.stream = ObjectStream[tuple[Player, UniMessage]](16)

    async def _decrease(self, user_id: str) -> None:
        await anyio.sleep(60)
        self.counter[user_id] -= 1

    async def _wait_finished(self) -> None:
        await self.finished.wait()
        self._task_group.cancel_scope.cancel()

    async def _broadcast(self) -> NoReturn:
        while True:
            player, msg = await self.stream.recv()
            msg = f"玩家 {player.name}:\n" + msg
            target = self.players.killed().exclude(player)
            try:
                await target.broadcast(msg)
            except Exception as err:
                with contextlib.suppress(Exception):
                    await player.send(f"消息转发失败: {err!r}")

    async def _receive(self, player: Player) -> NoReturn:
        await player.killed.wait()
        user_id = player.user_id

        await player.send(
            "ℹ️你已加入死者频道，请勿在群组内继续发言\n"
            "私聊发送消息将转发至其他已死亡玩家",
        )
        await (
            self.players.killed()
            .exclude(player)
            .broadcast(f"ℹ️玩家 {player.name} 加入了死者频道")
        )

        while True:
            msg = await player.receive()
            self.counter[user_id] += 1
            self._task_group.start_soon(self._decrease, user_id)

            # 发言频率限制
            if self.counter[user_id] > GameBehavior.get().dead_channel_rate_limit:
                await player.send("❌发言频率超过限制, 该消息被屏蔽")
                continue

            # 推送消息
            await self.stream.send((player, msg))

    async def run(self) -> None:
        async with anyio.create_task_group() as tg:
            self._task_group = tg
            tg.start_soon(self._wait_finished)
            tg.start_soon(self._broadcast)
            for p in self.players:
                tg.start_soon(self._receive, p)


class Game:
    bot: Bot
    group: Target
    players: PlayerSet
    state: GameState
    killed_players: list[tuple[str, KillInfo]]

    def __init__(self, bot: Bot, group: Target) -> None:
        self.bot = bot
        self.group = group
        self.state = GameState(0)
        self.killed_players = []
        self._player_map: dict[str, Player] = {}
        self._shuffled: list[Player] = []
        self._scene: Scene | None = None
        self._finished = self._task_group = None
        self._send_handler = _SendHandler(group, bot)

    @final
    @classmethod
    async def new(
        cls,
        bot: Bot,
        group: Target,
        players: set[str],
        interface: Interface,
    ) -> Self:
        self = cls(bot, group)

        self._scene = await interface.get_scene(SceneType.GROUP, self.group_id)
        if self._scene is None:
            self._scene = await interface.get_scene(SceneType.GUILD, self.group_id)

        self.players = await init_players(bot, self, players, interface)
        self._player_map |= {p.user_id: p for p in self.players}
        self._shuffled = self.players.shuffled

        return self

    @functools.cached_property
    def group_id(self) -> str:
        return self.group.id

    @property
    def colored_name(self) -> str:
        name = f"<b><e>{escape_tag(self.group_id)}</e></b>"
        if self._scene and self._scene.name is not None:
            name = f"<y>{escape_tag(self._scene.name)}</y>({name})"
        return link(name, self._scene and self._scene.avatar)

    def log(self, text: str) -> None:
        logger.info(f"{self.colored_name} | {text}")

    async def send(
        self,
        message: str | UniMessage,
        stop_btn_label: str | None = None,
    ) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        text = ["<g>Send</g> | "]
        for seg in message:
            if isinstance(seg, At):
                name = seg.target
                if name in self._player_map:
                    name = self._player_map[name].colored_name
                text.append(f"<y>@{name}</y>")
            else:
                text.append(escape_tag(str(seg)).replace("\n", "\\n"))

        self.log("".join(text))
        return await self._send_handler.send(message, stop_btn_label)

    def raise_for_status(self) -> None:
        players = self.players.alive()
        w = players.select(RoleGroup.WEREWOLF)
        p = players.exclude(RoleGroup.WEREWOLF)

        # 狼人数量大于其他职业数量
        if w.size >= p.size:
            raise GameFinished(GameStatus.WEREWOLF)
        # 屠边-村民/中立全灭
        if not p.select(Role.CIVILIAN, RoleGroup.OTHERS).size:
            raise GameFinished(GameStatus.WEREWOLF)
        # 屠边-神职全灭
        if not p.exclude(Role.CIVILIAN, RoleGroup.OTHERS).size:
            raise GameFinished(GameStatus.WEREWOLF)
        # 狼人全灭
        if not w.size:
            raise GameFinished(GameStatus.GOODGUY)

    @property
    def behavior(self) -> GameBehavior:
        return GameBehavior.get()

    async def notify_player_role(self) -> None:
        msg = UniMessage()
        for p in sorted(self.players, key=lambda p: p.user_id):
            msg.at(p.user_id)

        w, p, c = PresetData.get().role_preset[len(self.players)]
        msg = (
            msg.text("\n\n📝正在分配职业，请注意查看私聊消息\n")
            .text(f"当前玩家数: {len(self.players)}\n")
            .text(f"职业分配: 狼人x{w}, 神职x{p}, 平民x{c}")
        )

        if self.behavior.show_roles_list_on_start:
            msg.text("\n\n📚职业列表:\n")
            counter = Counter(p.role for p in self.players)
            for role, cnt in sorted(counter.items(), key=lambda x: x[0].value):
                msg.text(f"- {ROLE_EMOJI[role]}{ROLE_NAME_CONV[role]}x{cnt}\n")

        async with anyio.create_task_group() as tg:
            tg.start_soon(self.send, msg)
            for p in self.players:
                tg.start_soon(p.notify_role)

    async def wait_stop(
        self,
        *players: Player,
        timeout_secs: float | None = None,
    ) -> None:
        if timeout_secs is None:
            timeout_secs = self.behavior.timeout.speak
        with anyio.move_on_after(timeout_secs):
            async with anyio.create_task_group() as tg:
                for p in players:
                    tg.start_soon(InputStore.fetch_until_stop, p.user_id, self.group_id)

    async def post_kill(self, players: Player | PlayerSet) -> None:
        if isinstance(players, Player):
            players = PlayerSet([players])
        if not players:
            return

        for player in players.dead():
            await player.post_kill()
            if player.kill_info is None:
                continue
            self.killed_players.append((player.name, player.kill_info))

            shooter = self.state.shooter
            if shooter is not None and (shoot := shooter.selected) is not None:
                await self.send(
                    UniMessage.text("🔫玩家 ")
                    .at(shoot.user_id)
                    .text(f" 被{shooter.name}射杀, 请发表遗言\n")
                    .text(self.behavior.timeout.speak_timeout_prompt)
                )
                await self.wait_stop(shoot)
                self.state.shooter = shooter.selected = None
                await self.post_kill(shoot)

    async def run_night(self, players: PlayerSet) -> Player | None:
        async with anyio.create_task_group() as tg:
            for p in players:
                tg.start_soon(p.interact)

        # 狼人击杀目标
        if (
            (killed := self.state.killed) is not None  # 狼人未空刀
            and killed not in self.state.protected  # 守卫保护
            and killed not in self.state.antidote  # 女巫使用解药
        ):
            # 狼人正常击杀玩家
            await killed.kill(
                KillReason.WEREWOLF,
                *players.select(RoleGroup.WEREWOLF),
            )
        else:
            killed = None

        # 女巫操作目标
        for witch in self.state.poison:
            if witch.selected is None:
                continue
            if witch.selected not in self.state.protected:  # 守卫未保护
                # 女巫毒杀玩家
                await witch.selected.kill(KillReason.POISON, witch)

        return killed

    async def run_discussion(self) -> None:
        timeout = self.behavior.timeout

        if not self.behavior.speak_in_turn:
            await self.send(
                f"💬接下来开始自由讨论\n{timeout.group_speak_timeout_prompt}",
                stop_btn_label="结束发言",
            )
            await self.wait_stop(
                *self.players.alive(),
                timeout_secs=timeout.group_speak,
            )
        else:
            await self.send("💬接下来开始轮流发言")
            for player in filter(lambda p: p.alive, self._shuffled):
                await self.send(
                    UniMessage.text("💬")
                    .at(player.user_id)
                    .text(f"\n轮到你发言\n{timeout.speak_timeout_prompt}"),
                    stop_btn_label="结束发言",
                )
                await self.wait_stop(player, timeout_secs=timeout.speak)
            await self.send("💬所有玩家发言结束")

    async def run_vote(self) -> None:
        # 筛选当前存活玩家
        players = self.players.alive()

        # 被票玩家: [投票玩家]
        vote_result: dict[Player, list[Player]] = await players.vote()
        # 票数: [被票玩家]
        vote_reversed: dict[int, list[Player]] = {}
        # 收集到的总票数
        total_votes = sum(map(len, vote_result.values()))

        logger.debug(f"投票结果: {escape_tag(str(vote_result))}")

        # 投票结果公示
        msg = UniMessage.text("📊投票结果:\n")
        for player, votes in sorted(
            vote_result.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        ):
            if player is not None:
                msg.at(player.user_id).text(f": {len(votes)} 票\n")
                vote_reversed.setdefault(len(votes), []).append(player)
        if (discarded_votes := (len(players) - total_votes)) > 0:
            msg.text(f"弃票: {discarded_votes} 票\n")
        msg.text("\n")

        # 全员弃票  # 不是哥们？
        if total_votes == 0:
            await self.send(msg.text("🔨没有人被投票放逐"))
            return

        # 弃票大于最高票
        if (len(players) - total_votes) >= max(vote_reversed.keys()):
            await self.send(msg.text("🔨弃票数大于最高票数, 没有人被投票放逐"))
            return

        # 平票
        if len(vs := vote_reversed[max(vote_reversed.keys())]) != 1:
            await self.send(
                msg.text("🔨玩家 ")
                .text(", ".join(p.name for p in vs))
                .text(" 平票, 没有人被投票放逐")
            )
            return

        await self.send(msg.rstrip("\n"))

        # 仅有一名玩家票数最高
        voted = vs.pop()
        if await voted.kill(KillReason.VOTE, *vote_result[voted]) is None:
            # 投票放逐失败 (例: 白痴)
            return

        # 遗言
        await self.send(
            UniMessage.text("🔨玩家 ")
            .at(voted.user_id)
            .text(" 被投票放逐, 请发表遗言\n")
            .text(self.behavior.timeout.speak_timeout_prompt),
            stop_btn_label="结束发言",
        )
        await self.wait_stop(voted)
        await self.post_kill(voted)

    async def mainloop(self) -> NoReturn:
        # 告知玩家角色信息
        await self.notify_player_role()

        # 游戏主循环
        while True:
            # 重置游戏状态，进入下一夜
            self.state.reset()
            self.state.state = GameState.State.NIGHT
            await self.send("🌙天黑请闭眼...")
            players = self.players.alive()

            # 夜间交互，返回狼人目标
            killed = await self.run_night(players)

            # 公告
            self.state.day += 1
            self.state.state = GameState.State.DAY
            msg = UniMessage.text(f"『第{self.state.day}天』☀️天亮了...\n")
            # 没有玩家死亡，平安夜
            if not (dead := players.dead()):
                await self.send(msg.text("昨晚是平安夜"))
            # 有玩家死亡，公布死者名单
            else:
                msg.text("☠️昨晚的死者是:")
                for p in dead.sorted:
                    msg.text("\n").at(p.user_id)
                await self.send(msg)

            # 第一晚被狼人杀死的玩家发表遗言
            if self.state.day == 1 and killed is not None and not killed.alive:
                await self.send(
                    UniMessage.text("⚙️当前为第一天\n请被狼人杀死的 ")
                    .at(killed.user_id)
                    .text(" 发表遗言\n")
                    .text(self.behavior.timeout.speak_timeout_prompt),
                    stop_btn_label="结束发言",
                )
                await self.wait_stop(killed)
            await self.post_kill(dead)

            # 判断游戏状态
            self.raise_for_status()

            # 公示存活玩家
            await self.send(f"📝当前存活玩家: \n\n{self.players.alive().show()}")

            # 开始自由讨论
            await self.run_discussion()

            # 开始投票
            await self.send(
                "🗳️讨论结束, 进入投票环节，限时1分钟\n请在私聊中进行投票交互"
            )
            self.state.state = GameState.State.VOTE
            await self.run_vote()

            # 判断游戏状态
            self.raise_for_status()

    async def handle_game_finish(self, status: GameStatus) -> None:
        msg = UniMessage.text(f"🎉游戏结束，{GAME_STATUS_CONV[status]}获胜\n\n")
        for p in sorted(self.players, key=lambda p: (p.role.value, p.user_id)):
            msg.at(p.user_id).text(f": {p.role_name}\n")
        await self.send(msg)

        report = ["📌玩家死亡报告:"]
        for name, info in self.killed_players:
            emoji, action = REPORT_TEXT[info.reason]
            report.append(f"{emoji} {name} 被 {', '.join(info.killers)} {action}")
        await self.send("\n\n".join(report))

    async def run_daemon(self) -> None:
        try:
            await self.mainloop()
        except anyio.get_cancelled_exc_class():
            logger.warning(f"{self.colored_name} 的狼人杀游戏进程被取消")
        except GameFinished as result:
            await self.handle_game_finish(result.status)
            logger.info(f"{self.colored_name} 的狼人杀游戏进程正常退出")
        except Exception as err:
            logger.exception(f"{self.colored_name} 的狼人杀游戏进程出现未知错误")
            await self.send(f"❌狼人杀游戏进程出现未知错误: {err!r}")
        finally:
            if self._finished is not None:
                self._finished.set()

    async def start(self) -> None:
        self._finished = anyio.Event()
        dead_channel = DeadChannel(self.players, self._finished)
        get_running_games().add(self)

        try:
            async with anyio.create_task_group() as self._task_group:
                self._task_group.start_soon(self.run_daemon)
                self._task_group.start_soon(dead_channel.run)
        except anyio.get_cancelled_exc_class():
            logger.warning(f"{self.colored_name} 的狼人杀游戏进程被取消")
        except Exception as err:
            msg = f"{self.colored_name} 的狼人杀守护进程出现错误: {err!r}"
            logger.opt(exception=err).error(msg)
        finally:
            self._finished = None
            self._task_group = None
            get_running_games().discard(self)
            InputStore.cleanup(self._player_map.keys(), self.group_id)

    def terminate(self) -> None:
        if self._task_group is not None:
            logger.warning(f"中止 {self.colored_name} 的狼人杀游戏进程")
            self._task_group.cancel_scope.cancel()
