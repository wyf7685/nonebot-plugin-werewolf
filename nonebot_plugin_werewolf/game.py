import contextlib
import functools
import secrets
from typing import ClassVar, NoReturn

import anyio
import anyio.abc
import nonebot
from nonebot.adapters import Bot
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import At, Target, UniMessage
from nonebot_plugin_alconna.uniseg.message import Receipt
from nonebot_plugin_uninfo import Interface, SceneType
from typing_extensions import Self, assert_never

from .config import PresetData
from .constant import STOP_COMMAND_PROMPT, game_status_conv, report_text, role_name_conv
from .exception import GameFinished
from .models import GameState, GameStatus, KillInfo, KillReason, Role, RoleGroup
from .player_set import PlayerSet
from .players import Player
from .utils import InputStore, ObjectStream, link

logger = nonebot.logger.opt(colors=True)


def init_players(bot: Bot, game: "Game", players: set[str]) -> PlayerSet:
    # group.colored_name not available yet
    logger.debug(f"初始化 <c>{game.group_id}</c> 的玩家职业")

    preset_data = PresetData.load()
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
    roles.extend([Role.Civilian] * c)

    if c >= 2 and secrets.randbelow(100) <= preset_data.joker_probability * 100:
        roles.remove(Role.Civilian)
        roles.append(Role.Joker)

    def _select_role() -> Role:
        return roles.pop(secrets.randbelow(len(roles)))

    player_set = PlayerSet(
        Player.new(_select_role(), bot, game, user_id) for user_id in players
    )
    logger.debug(f"职业分配完成: <e>{escape_tag(str(player_set))}</e>")

    return player_set


class DeadChannel:
    players: PlayerSet
    finished: anyio.Event
    counter: dict[str, int]
    stream: ObjectStream[tuple[Player, UniMessage]]
    task_group: anyio.abc.TaskGroup

    def __init__(self, players: PlayerSet, finished: anyio.Event) -> None:
        self.players = players
        self.finished = finished
        self.counter = {p.user_id: 0 for p in self.players}
        self.stream = ObjectStream[tuple[Player, UniMessage]](16)

    async def _decrease(self, user_id: str) -> None:
        await anyio.sleep(60)
        self.counter[user_id] -= 1

    async def _handle_finished(self) -> None:
        await self.finished.wait()
        self.task_group.cancel_scope.cancel()

    async def _handle_send(self) -> NoReturn:
        while True:
            player, msg = await self.stream.recv()
            msg = f"玩家 {player.name}:\n" + msg
            target = self.players.killed().exclude(player)
            try:
                await target.broadcast(msg)
            except Exception as err:
                with contextlib.suppress(Exception):
                    await player.send(f"消息转发失败: {err!r}")

    async def _handle_recv(self, player: Player) -> NoReturn:
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

            # 发言频率限制
            self.counter[user_id] += 1
            if self.counter[user_id] > 8:
                await player.send("❌发言频率超过限制, 该消息被屏蔽")
                continue

            # 推送消息
            await self.stream.send((player, msg))
            self.task_group.start_soon(self._decrease, user_id)

    async def run(self) -> NoReturn:
        async with anyio.create_task_group() as tg:
            self.task_group = tg
            tg.start_soon(self._handle_finished)
            tg.start_soon(self._handle_send)
            for p in self.players:
                tg.start_soon(self._handle_recv, p)


class Game:
    starting_games: ClassVar[dict[Target, dict[str, str]]] = {}
    running_games: ClassVar[set[Self]] = set()

    bot: Bot
    group: Target
    players: PlayerSet
    interface: Interface
    state: GameState
    killed_players: list[tuple[str, KillInfo]]

    def __init__(
        self,
        bot: Bot,
        group: Target,
        players: set[str],
        interface: Interface,
    ) -> None:
        self.bot = bot
        self.group = group
        self.players = init_players(bot, self, players)
        self.interface = interface
        self.state = GameState(0)
        self.killed_players = []
        self._player_map = {p.user_id: p for p in self.players}
        self._scene = None
        self._task_group = None

    async def _fetch_group_scene(self) -> None:
        scene = await self.interface.get_scene(SceneType.GROUP, self.group_id)
        if scene is None:
            scene = await self.interface.get_scene(SceneType.GUILD, self.group_id)

        self._scene = scene

    @functools.cached_property
    def group_id(self) -> str:
        return self.group.id

    @property
    def colored_name(self) -> str:
        name = f"<b><e>{escape_tag(self.group_id)}</e></b>"
        if self._scene and self._scene.name is not None:
            name = f"<y>{escape_tag(self._scene.name)}</y>({name})"
        return link(name, self._scene and self._scene.avatar)

    async def send(self, message: str | UniMessage) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        text = f"{self.colored_name} | <g>Send</g> | "
        for seg in message:
            if isinstance(seg, At):
                name = seg.target
                if name in self._player_map:
                    name = self._player_map[name].colored_name
                text += f"<y>@{name}</y>"
            else:
                text += escape_tag(str(seg)).replace("\n", "\\n")

        logger.info(text)
        return await message.send(self.group, self.bot)

    def raise_for_status(self) -> None:
        players = self.players.alive()
        w = players.select(RoleGroup.Werewolf)
        p = players.exclude(RoleGroup.Werewolf)

        # 狼人数量大于其他职业数量
        if w.size >= p.size:
            raise GameFinished(GameStatus.Werewolf)
        # 屠边-村民/中立全灭
        if not p.select(Role.Civilian, RoleGroup.Others).size:
            raise GameFinished(GameStatus.Werewolf)
        # 屠边-神职全灭
        if not p.exclude(Role.Civilian).size:
            raise GameFinished(GameStatus.Werewolf)
        # 狼人全灭
        if not w.size:
            raise GameFinished(GameStatus.GoodGuy)

    async def notify_player_role(self) -> None:
        msg = UniMessage()
        for p in sorted(self.players, key=lambda p: p.user_id):
            msg.at(p.user_id)

        w, p, c = PresetData.load().role_preset[len(self.players)]
        msg = (
            msg.text("\n\n📝正在分配职业，请注意查看私聊消息\n")
            .text(f"当前玩家数: {len(self.players)}\n")
            .text(f"职业分配: 狼人x{w}, 神职x{p}, 平民x{c}")
        )

        async with anyio.create_task_group() as tg:
            tg.start_soon(self.send, msg)
            for p in self.players:
                tg.start_soon(p.notify_role)

    async def wait_stop(self, *players: Player, timeout_secs: float) -> None:
        with anyio.move_on_after(timeout_secs):
            async with anyio.create_task_group() as tg:
                for p in players:
                    tg.start_soon(InputStore.fetch_until_stop, p.user_id, self.group_id)

    async def interact(
        self,
        player_type: Player | Role | RoleGroup,
        timeout_secs: float,
    ) -> None:
        players = self.players.alive().select(player_type)
        match player_type:
            case Player():
                text = player_type.role_name
            case Role():
                text = role_name_conv[player_type]
            case RoleGroup():
                text = f"{role_name_conv[player_type]}阵营"
            case x:
                assert_never(x)

        await players.broadcast(f"✏️{text}交互开始，限时 {timeout_secs/60:.2f} 分钟")
        try:
            with anyio.fail_after(timeout_secs):
                await players.interact()
        except TimeoutError:
            logger.debug(f"{text}交互超时 (<y>{timeout_secs}</y>s)")
            await players.broadcast(f"⚠️{text}交互超时")

    async def post_kill(self, players: Player | PlayerSet) -> None:
        if isinstance(players, Player):
            players = PlayerSet([players])
        if not players:
            return

        for player in players.dead():
            await player.post_kill()
            if player.kill_info is not None:
                self.killed_players.append((player.name, player.kill_info))

            shooter = self.state.shoot
            if shooter is not None and (shoot := shooter.selected) is not None:
                await self.send(
                    UniMessage.text("🔫玩家 ")
                    .at(shoot.user_id)
                    .text(f" 被{shooter.role_name}射杀, 请发表遗言\n")
                    .text(f"限时1分钟, 发送 “{STOP_COMMAND_PROMPT}” 结束发言")
                )
                await self.wait_stop(shoot, timeout_secs=60)
                self.state.shoot = shooter.selected = None
                await self.post_kill(shoot)

    async def select_killed(self) -> None:
        players = self.players.alive()
        self.state.killed = None

        w = players.select(RoleGroup.Werewolf)
        await self.interact(RoleGroup.Werewolf, 120)
        if (s := w.player_selected()).size == 1:
            self.state.killed = s.pop()
            await w.broadcast(f"🔪今晚选择的目标为: {self.state.killed.name}")
        else:
            await w.broadcast("⚠️狼人阵营意见未统一，此晚空刀")

        # 如果女巫存活，正常交互，限时1分钟
        if players.include(Role.Witch):
            await self.interact(Role.Witch, 60)
        # 否则等待 5-20s
        else:
            await anyio.sleep(5 + secrets.randbelow(15))

    async def run_night(self, players: PlayerSet) -> Player | None:
        # 狼人、预言家、守卫 同时交互，女巫在狼人后交互
        async with anyio.create_task_group() as tg:
            tg.start_soon(self.select_killed)
            tg.start_soon(
                players.select(Role.Witch).broadcast,
                "ℹ️请等待狼人决定目标...",
            )
            tg.start_soon(self.interact, Role.Prophet, 60)
            tg.start_soon(self.interact, Role.Guard, 60)
            tg.start_soon(
                players.exclude(
                    RoleGroup.Werewolf,
                    Role.Prophet,
                    Role.Witch,
                    Role.Guard,
                ).broadcast,
                "ℹ️请等待其他玩家结束交互...",
            )

        # 狼人击杀目标
        if (
            (killed := self.state.killed) is not None  # 狼人未空刀
            and killed not in self.state.protected  # 守卫保护
            and killed not in self.state.antidote  # 女巫使用解药
        ):
            # 狼人正常击杀玩家
            await killed.kill(
                KillReason.Werewolf,
                *players.select(RoleGroup.Werewolf),
            )

        # 女巫操作目标
        for witch in self.state.poison:
            if witch.selected is None:
                continue
            if witch.selected not in self.state.protected:  # 守卫未保护
                # 女巫毒杀玩家
                await witch.selected.kill(KillReason.Poison, witch)

        return killed

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
        for p, v in sorted(vote_result.items(), key=lambda x: len(x[1]), reverse=True):
            if p is not None:
                msg.at(p.user_id).text(f": {len(v)} 票\n")
                vote_reversed[len(v)] = [*vote_reversed.get(len(v), []), p]
        if (v := (len(players) - total_votes)) > 0:
            msg.text(f"弃票: {v} 票\n\n")

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
        if not await voted.kill(KillReason.Vote, *vote_result[voted]):
            # 投票放逐失败 (例: 白痴)
            return

        # 遗言
        await self.send(
            UniMessage.text("🔨玩家 ")
            .at(voted.user_id)
            .text(" 被投票放逐, 请发表遗言\n")
            .text(f"限时1分钟, 发送 “{STOP_COMMAND_PROMPT}” 结束发言")
        )
        await self.wait_stop(voted, timeout_secs=60)
        await self.post_kill(voted)

    async def mainloop(self) -> NoReturn:
        # 告知玩家角色信息
        await self.notify_player_role()

        # 游戏主循环
        while True:
            # 重置游戏状态，进入下一夜
            self.state.reset()
            await self.send("🌙天黑请闭眼...")
            players = self.players.alive()
            killed = await self.run_night(players)

            # 公告
            self.state.day += 1
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
                    .text(f"限时1分钟, 发送 “{STOP_COMMAND_PROMPT}” 结束发言")
                )
                await self.wait_stop(killed, timeout_secs=60)
            await self.post_kill(dead)

            # 判断游戏状态
            self.raise_for_status()

            # 公示存活玩家
            await self.send(f"📝当前存活玩家: \n\n{self.players.alive().show()}")

            # 开始自由讨论
            await self.send(
                "💬接下来开始自由讨论\n限时2分钟, "
                f"全员发送 “{STOP_COMMAND_PROMPT}” 结束发言"
            )
            await self.wait_stop(*self.players.alive(), timeout_secs=120)

            # 开始投票
            await self.send(
                "🗳️讨论结束, 进入投票环节，限时1分钟\n请在私聊中进行投票交互"
            )
            await self.run_vote()

            # 判断游戏状态
            self.raise_for_status()

    async def handle_game_finish(self, status: GameStatus) -> None:
        msg = UniMessage.text(f"🎉游戏结束，{game_status_conv[status]}获胜\n\n")
        for p in sorted(self.players, key=lambda p: (p.role.value, p.user_id)):
            msg.at(p.user_id).text(f": {p.role_name}\n")
        await self.send(msg)

        report: list[str] = ["📌玩家死亡报告:"]
        for name, info in self.killed_players:
            emoji, action = report_text[info.reason]
            report.append(f"{emoji} {name} 被 {', '.join(info.killers)} {action}")
        await self.send("\n\n".join(report))

    async def daemon(self, finished: anyio.Event) -> None:
        try:
            await self.mainloop()
        except anyio.get_cancelled_exc_class():
            logger.warning(f"{self.colored_name} 的狼人杀游戏进程被取消")
        except GameFinished as result:
            await self.handle_game_finish(result.status)
            logger.info(f"{self.colored_name} 的狼人杀游戏进程正常退出")
        except Exception as err:
            msg = f"{self.colored_name} 的狼人杀游戏进程出现未知错误: {err!r}"
            logger.exception(msg)
            await self.send(f"❌狼人杀游戏进程出现未知错误: {err!r}")
        finally:
            finished.set()

    async def start(self) -> None:
        await self._fetch_group_scene()
        finished = anyio.Event()
        dead_channel = DeadChannel(self.players, finished)
        self.running_games.add(self)

        try:
            async with anyio.create_task_group() as tg:
                self._task_group = tg
                tg.start_soon(self.daemon, finished)
                tg.start_soon(dead_channel.run)
        except anyio.get_cancelled_exc_class():
            logger.warning(f"{self.colored_name} 的狼人杀游戏进程被取消")
        except Exception as err:
            msg = f"{self.colored_name} 的狼人杀守护进程出现错误: {err!r}"
            logger.opt(exception=err).error(msg)
        finally:
            self._task_group = None
            self.running_games.discard(self)
            InputStore.cleanup(list(self._player_map), self.group_id)

    def terminate(self) -> None:
        if self._task_group is not None:
            logger.warning(f"中止 {self.colored_name} 的狼人杀游戏进程")
            self._task_group.cancel_scope.cancel()
