import contextlib
import functools
import itertools
import secrets
from collections import Counter
from collections.abc import AsyncGenerator
from typing import NoReturn, final
from typing_extensions import Self

import anyio
import nonebot
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import At, Target, UniMessage
from nonebot_plugin_alconna.uniseg.receipt import Receipt
from nonebot_plugin_uninfo import Interface, SceneType

from .dead_channel import DeadChannel
from .exception import GameFinished
from .models import GameContext, GameStatus, KillInfo, KillReason, Role, RoleGroup
from .player import Player
from .player_set import PlayerSet
from .utils import (
    ConfigAccess,
    InputStore,
    LoggerWrapper,
    SendHandler,
    add_stop_button,
    link,
    logger_wrapper,
)

running_games: dict[Target, "Game"] = {}


def get_running_games() -> dict[Target, "Game"]:
    return running_games


class GameRegistry:
    def __init__(self) -> None:
        self._games: dict[Target, Game] = {}

    @contextlib.asynccontextmanager
    async def register(self, game: "Game") -> AsyncGenerator["Game"]:
        self._games[game.group] = game
        try:
            yield game
        finally:
            self._games.pop(game.group, None)

    def is_user_in_game(self, self_id: str, user_id: str, group_id: str | None) -> bool:
        if group_id is None:
            return any(
                p.user.self_id == self_id and p.user_id == user_id
                for p in itertools.chain.from_iterable(
                    g.players for g in self._games.values()
                )
            )
        for game in self._games.values():
            if self_id == game.group.self_id and group_id == game.group.id:
                return any(p.user_id == user_id for p in game.players)
        return False

    def has_running_games(self) -> bool:
        return bool(self._games)

    def __contains__(self, target: Target) -> bool:
        return any(target.verify(group) for group in self._games)

    def get(self, group: Target) -> "Game | None":
        for g, game in self._games.items():
            if g.verify(group):
                return game
        return None


game_registry = GameRegistry()


async def init_players(
    game: "Game",
    players: set[str],
    interface: Interface,
) -> PlayerSet:
    game.log.debug("初始化玩家职业")

    preset_data = game.preset
    if (preset := preset_data.role_preset.get(len(players))) is None:
        raise ValueError(
            f"玩家人数不符: "
            f"应为 {', '.join(map(str, preset_data.role_preset))} 人, "
            f"传入{len(players)}人"
        )

    w, p, c = preset
    roles = [
        *preset_data.werewolf_priority[:w],
        *preset_data.priesthood_priority[:p],
        *([Role.CIVILIAN] * c),
    ]

    if c >= 2 and secrets.randbelow(100) <= preset_data.jester_probability * 100:
        roles.remove(Role.CIVILIAN)
        roles.append(Role.JESTER)

    player_set = PlayerSet()
    for user_id in players:
        role = roles.pop(secrets.randbelow(len(roles)))
        player_set.add(await Player.new(role, game, user_id, interface))

    game.log.debug(f"职业分配完成: <e>{escape_tag(str(player_set))}</e>")
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


class GameMessenger(ConfigAccess):
    def __init__(self, group: Target, players: PlayerSet, log: LoggerWrapper) -> None:
        self.group = group
        self.player_map = {p.user_id: p for p in players}
        self.log = log
        self._send_handler = _SendHandler(group)

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
                if name in self.player_map:
                    name = self.player_map[name].colored_name
                text.append(f"<y>@{name}</y>")
            else:
                text.append(escape_tag(str(seg)).replace("\n", "\\n"))

        self.log.info("".join(text))
        return await self._send_handler.send(message, stop_btn_label)

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
                    tg.start_soon(InputStore.fetch_until_stop, p.user_id, self.group.id)

    async def notify_player_role(self, players: PlayerSet) -> None:
        msg = UniMessage()
        for p in sorted(players, key=lambda p: p.user_id):
            msg.at(p.user_id)

        w, p, c = self.preset.role_preset[len(players)]
        msg = (
            msg.text("\n\n📝正在分配职业，请注意查看私聊消息\n")
            .text(f"当前玩家数: {len(players)}\n")
            .text(f"职业分配: 狼人x{w}, 神职x{p}, 平民x{c}")
        )

        if self.behavior.show_roles_list_on_start:
            msg.text("\n\n📚职业列表:\n")
            counter = Counter(p.role for p in players)
            for role, cnt in sorted(counter.items(), key=lambda x: x[0].value):
                msg.text(f"- {role.emoji}{role.display}x{cnt}\n")

        async with anyio.create_task_group() as tg:
            tg.start_soon(self.send, msg)
            for p in players:
                tg.start_soon(p.notify_role)


class Game(ConfigAccess):
    group: Target
    log: LoggerWrapper
    players: PlayerSet
    context: GameContext
    messenger: GameMessenger
    killed_players: list[tuple[str, KillInfo]]
    finished: anyio.Event

    def __init__(self, group: Target) -> None:
        self.group = group
        self.context = GameContext(0)
        self.killed_players = []
        self.finished = anyio.Event()
        self._task_group = None

    @final
    @classmethod
    async def new(
        cls,
        group: Target,
        players: set[str],
        interface: Interface,
    ) -> Self:
        scene = await interface.get_scene(SceneType.GROUP, group.id)
        if scene is None:
            scene = await interface.get_scene(SceneType.GUILD, group.id)
        name = f"<b><e>{escape_tag(group.id)}</e></b>"
        if scene is not None and scene.name is not None:
            name = f"<y>{escape_tag(scene.name)}</y>({name})"
        log_prefix = link(name, scene.avatar if scene is not None else None)

        self = cls(group)
        self.log = logger_wrapper(log_prefix)
        self.players = await init_players(self, players, interface)
        self.messenger = GameMessenger(group, self.players, self.log)

        return self

    @functools.cached_property
    def group_id(self) -> str:
        return self.group.id

    @functools.cached_property
    def _shuffled(self) -> list[Player]:
        return self.players.shuffled

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

            shooter = self.context.shooter
            if shooter is not None and (shoot := shooter.selected) is not None:
                await self.messenger.send(
                    UniMessage.text("🔫玩家 ")
                    .at(shoot.user_id)
                    .text(f" 被{shooter.name}射杀, 请发表遗言\n")
                    .text(self.behavior.timeout.speak_timeout_prompt)
                )
                await self.messenger.wait_stop(shoot)
                self.context.shooter = shooter.selected = None
                await self.post_kill(shoot)

    async def run_night(self, players: PlayerSet) -> None:
        async with anyio.create_task_group() as tg:
            for p in players:
                tg.start_soon(p.interact)

        # 狼人击杀目标
        if (
            (killed := self.context.killed) is not None  # 狼人未空刀
            and killed not in self.context.protected  # 守卫保护
            and killed not in self.context.antidote  # 女巫使用解药
        ):
            # 狼人正常击杀玩家
            await killed.kill(
                KillReason.WEREWOLF,
                *players.select(RoleGroup.WEREWOLF),
            )
        else:
            self.context.killed = None

        # 女巫操作目标
        for witch in self.context.poison:
            if (
                (selected := witch.selected) is not None  # 理论上不会是 None (
                and selected not in self.context.protected  # 守卫保护
                # 虽然应该没什么人会加多个女巫玩...但还是加上判断比较好
                and selected not in self.context.antidote  # 女巫使用解药
            ):
                # 女巫毒杀玩家
                await selected.kill(KillReason.POISON, witch)

    async def run_discussion(self) -> None:
        timeout = self.behavior.timeout

        if not self.behavior.speak_in_turn:
            await self.messenger.send(
                f"💬接下来开始自由讨论\n{timeout.group_speak_timeout_prompt}",
                stop_btn_label="结束发言",
            )
            await self.messenger.wait_stop(
                *self.players.alive(),
                timeout_secs=timeout.group_speak,
            )
        else:
            await self.messenger.send("💬接下来开始轮流发言")
            for player in filter(lambda p: p.alive, self._shuffled):
                await self.messenger.send(
                    UniMessage.text("💬")
                    .at(player.user_id)
                    .text(f"\n轮到你发言\n{timeout.speak_timeout_prompt}"),
                    stop_btn_label="结束发言",
                )
                await self.messenger.wait_stop(player, timeout_secs=timeout.speak)
            await self.messenger.send("💬所有玩家发言结束")

    async def run_vote(self) -> None:
        # 筛选当前存活玩家
        players = self.players.alive()

        # 被票玩家: [投票玩家]
        vote_result: dict[Player, list[Player]] = await players.vote()
        # 票数: [被票玩家]
        vote_reversed: dict[int, list[Player]] = {}
        # 收集到的总票数
        total_votes = sum(map(len, vote_result.values()))

        self.log.debug(f"投票结果: {escape_tag(str(vote_result))}")

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
            await self.messenger.send(msg.text("🔨没有人被投票放逐"))
            return

        # 弃票大于最高票
        if (len(players) - total_votes) >= max(vote_reversed.keys()):
            await self.messenger.send(
                msg.text("🔨弃票数大于最高票数, 没有人被投票放逐")
            )
            return

        # 平票
        if len(vs := vote_reversed[max(vote_reversed.keys())]) != 1:
            await self.messenger.send(
                msg.text("🔨玩家 ")
                .text(", ".join(p.name for p in vs))
                .text(" 平票, 没有人被投票放逐")
            )
            return

        await self.messenger.send(msg.rstrip("\n"))

        # 仅有一名玩家票数最高
        voted = vs.pop()
        if await voted.kill(KillReason.VOTE, *vote_result[voted]) is None:
            # 投票放逐失败 (例: 白痴)
            return

        # 遗言
        await self.messenger.send(
            UniMessage.text("🔨玩家 ")
            .at(voted.user_id)
            .text(" 被投票放逐, 请发表遗言\n")
            .text(self.behavior.timeout.speak_timeout_prompt),
            stop_btn_label="结束发言",
        )
        await self.messenger.wait_stop(voted)
        await self.post_kill(voted)

    async def mainloop(self) -> NoReturn:
        # 告知玩家角色信息
        await self.messenger.notify_player_role(self.players)

        # 游戏主循环
        while True:
            # 重置游戏状态，进入下一夜
            self.context.reset()
            self.context.state = GameContext.State.NIGHT
            await self.messenger.send("🌙天黑请闭眼...")
            players = self.players.alive()

            # 夜间交互
            await self.run_night(players)

            # 公告
            self.context.day += 1
            self.context.state = GameContext.State.DAY
            msg = UniMessage.text(f"『第{self.context.day}天』☀️天亮了...\n")
            # 没有玩家死亡，平安夜
            if not (dead := players.dead()):
                await self.messenger.send(msg.text("昨晚是平安夜"))
            # 有玩家死亡，公布死者名单
            else:
                msg.text("☠️昨晚的死者是:")
                for p in dead.sorted:
                    msg.text("\n").at(p.user_id)
                await self.messenger.send(msg)

            # 第一晚被狼人杀死的玩家发表遗言
            if (
                self.context.day == 1  # 仅第一晚
                and (killed := self.context.killed) is not None  # 狼人未空刀且未保护
                and not killed.alive  # kill 成功
            ):
                await self.messenger.send(
                    UniMessage.text("⚙️当前为第一天\n请被狼人杀死的 ")
                    .at(killed.user_id)
                    .text(" 发表遗言\n")
                    .text(self.behavior.timeout.speak_timeout_prompt),
                    stop_btn_label="结束发言",
                )
                await self.messenger.wait_stop(killed)
            await self.post_kill(dead)

            # 判断游戏状态
            self.raise_for_status()

            # 公示存活玩家
            await self.messenger.send(
                f"📝当前存活玩家: \n\n{self.players.alive().show()}"
            )

            # 开始自由讨论
            await self.run_discussion()

            # 开始投票
            await self.messenger.send(
                "🗳️讨论结束, 进入投票环节, "
                f"限时{self.behavior.timeout.vote / 60:.1f}分钟\n"
                "请在私聊中进行投票交互"
            )
            self.context.state = GameContext.State.VOTE
            await self.run_vote()

            # 判断游戏状态
            self.raise_for_status()

    async def handle_game_finish(self, status: GameStatus) -> None:
        msg = UniMessage.text(f"🎉游戏结束，{status.display}获胜\n\n")
        for p in sorted(self.players, key=lambda p: (p.role.value, p.user_id)):
            msg.at(p.user_id).text(f": {p.role_name}\n")
        await self.messenger.send(msg)

        report = ["📌玩家死亡报告:"]
        for name, info in self.killed_players:
            emoji, action = info.reason.display
            report.append(f"{emoji} {name} 被 {', '.join(info.killers)} {action}")
        await self.messenger.send("\n\n".join(report))

    async def run_daemon(self) -> None:
        try:
            await self.mainloop()
        except anyio.get_cancelled_exc_class():
            self.log.warning("的狼人杀游戏进程被取消")
            raise
        except GameFinished as result:
            await self.handle_game_finish(result.status)
            self.log.info("狼人杀游戏进程正常退出")
        except Exception as exc:
            self.log.exception("狼人杀游戏进程出现未知错误")
            await self.messenger.send(f"❌狼人杀游戏进程出现未知错误: {exc!r}")
        finally:
            self.finished.set()

    async def run(self) -> None:
        dead_channel = DeadChannel(self.players, self.finished)

        try:
            async with (
                game_registry.register(self),
                anyio.create_task_group() as self._task_group,
            ):
                self._task_group.start_soon(dead_channel.run)
                await self.run_daemon()
        except Exception:
            self.log.exception("狼人杀守护进程出现错误")
        finally:
            self._task_group = None
            InputStore.cleanup((p.user_id for p in self.players), self.group_id)

    def start(self) -> None:
        nonebot.get_driver().task_group.start_soon(self.run)

    def terminate(self) -> None:
        if self._task_group is not None:
            self.log.warning("中止狼人杀游戏进程")
            self._task_group.cancel_scope.cancel()
