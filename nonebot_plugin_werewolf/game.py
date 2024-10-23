import secrets
from typing import ClassVar, NoReturn

import anyio
from nonebot.adapters import Bot
from nonebot.log import logger
from nonebot.utils import escape_tag
from nonebot_plugin_alconna import At, Target, UniMessage
from nonebot_plugin_alconna.uniseg.message import Receipt
from nonebot_plugin_uninfo import Interface, SceneType
from typing_extensions import Self, assert_never

from .config import config
from .constant import (
    STOP_COMMAND,
    STOP_COMMAND_PROMPT,
    GameState,
    GameStatus,
    KillReason,
    Role,
    RoleGroup,
    role_name_conv,
)
from .exception import GameFinished
from .player_set import PlayerSet
from .players import Player
from .utils import InputStore, link


def init_players(bot: Bot, game: "Game", players: set[str]) -> PlayerSet:
    logger.opt(colors=True).debug(f"初始化 <c>{game.group.id}</c> 的玩家职业")
    role_preset = config.get_role_preset()
    if (preset := role_preset.get(len(players))) is None:
        raise ValueError(
            f"玩家人数不符: "
            f"应为 {', '.join(map(str, role_preset))} 人, 传入{len(players)}人"
        )

    w, p, c = preset
    roles: list[Role] = []
    roles.extend(config.werewolf_priority[:w])
    roles.extend(config.priesthood_proirity[:p])
    roles.extend([Role.Civilian] * c)

    if c >= 2 and secrets.randbelow(100) <= config.joker_probability * 100:
        roles.remove(Role.Civilian)
        roles.append(Role.Joker)

    def _select_role() -> Role:
        return roles.pop(secrets.randbelow(len(roles)))

    player_set = PlayerSet(
        Player.new(_select_role(), bot, game, user_id) for user_id in players
    )
    logger.debug(f"职业分配完成: {player_set}")

    return player_set


class Game:
    starting_games: ClassVar[dict[Target, dict[str, str]]] = {}
    running_games: ClassVar[set[Self]] = set()

    bot: Bot
    group: Target
    players: PlayerSet
    interface: Interface
    state: GameState
    killed_players: list[Player]

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

    async def _fetch_group_scene(self) -> None:
        scene = await self.interface.get_scene(SceneType.GROUP, self.group.id)
        if scene is None:
            scene = await self.interface.get_scene(SceneType.GUILD, self.group.id)

        self._scene = scene

    @property
    def colored_name(self) -> str:
        name = escape_tag(self.group.id)

        if self._scene is None or self._scene.name is None:
            name = f"<b><e>{name}</e></b>"
        else:
            name = f"<y>{escape_tag(self._scene.name)}</y>(<b><e>{name}</e></b>)"

        if self._scene is not None and self._scene.avatar is not None:
            name = link(name, self._scene.avatar)

        return name

    async def send(self, message: str | UniMessage) -> Receipt:
        if isinstance(message, str):
            message = UniMessage.text(message)

        text = f"{self.colored_name} | <g>Send</g> | "
        for seg in message:
            if isinstance(seg, At):
                text += f"<y>@{self._player_map[seg.target].colored_name}</y>"
            else:
                text += escape_tag(str(seg)).replace("\n", "\\n")

        logger.opt(colors=True).info(text)
        return await message.send(self.group, self.bot)

    def at_all(self) -> UniMessage:
        msg = UniMessage()
        for p in sorted(self.players, key=lambda p: (p.role_name, p.user_id)):
            msg.at(p.user_id)
        return msg

    def check_game_status(self) -> None:
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

    def show_killed_players(self) -> str:
        result: list[str] = []

        for player in self.killed_players:
            if player.kill_info is None:
                continue

            line = f"{player.name} 被 " + ", ".join(
                p.name for p in player.kill_info.killers
            )
            match player.kill_info.reason:
                case KillReason.Werewolf:
                    line = f"🔪 {line} 刀了"
                case KillReason.Poison:
                    line = f"🧪 {line} 毒死"
                case KillReason.Shoot:
                    line = f"🔫 {line} 射杀"
                case KillReason.Vote:
                    line = f"🗳️ {line} 票出"
                case x:
                    assert_never(x)
            result.append(line)

        return "\n\n".join(result)

    async def notify_player_role(self) -> None:
        preset = config.get_role_preset()[len(self.players)]
        msg = (
            self.at_all()
            .text("\n\n📝正在分配职业，请注意查看私聊消息\n")
            .text(f"当前玩家数: {len(self.players)}\n")
            .text(f"职业分配: 狼人x{preset[0]}, 神职x{preset[1]}, 平民x{preset[2]}")
        )

        async with anyio.create_task_group() as tg:
            tg.start_soon(self.send, msg)
            for p in self.players:
                tg.start_soon(p.notify_role)

    async def wait_stop(self, *players: Player, timeout_secs: float) -> None:
        async def wait(p: Player) -> None:
            while True:
                msg = await InputStore.fetch(p.user_id, self.group.id)
                if msg.extract_plain_text().strip() == STOP_COMMAND:
                    break

        with anyio.move_on_after(timeout_secs):
            async with anyio.create_task_group() as tg:
                for p in players:
                    tg.start_soon(wait, p)

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
            logger.opt(colors=True).debug(f"{text}交互超时 (<y>{timeout_secs}</y>s)")
            await players.broadcast(f"⚠️{text}交互超时")

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

    async def handle_new_dead(self, players: Player | PlayerSet) -> None:
        if isinstance(players, Player):
            players = PlayerSet([players])
        if not players:
            return

        async with anyio.create_task_group() as tg:
            tg.start_soon(
                players.broadcast,
                "ℹ️你已加入死者频道，请勿在群内继续发言\n"
                "私聊发送消息将转发至其他已死亡玩家",
            )
            tg.start_soon(
                self.players.dead().exclude(*players).broadcast,
                f"ℹ️玩家 {', '.join(p.name for p in players)} 加入了死者频道",
            )

    async def post_kill(self, players: Player | PlayerSet) -> None:
        if isinstance(players, Player):
            players = PlayerSet([players])
        if not players:
            return

        for player in players.dead():
            await player.post_kill()
            await self.handle_new_dead(player)
            self.killed_players.append(player)

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

    async def run_vote(self) -> None:
        # 筛选当前存活玩家
        players = self.players.alive()

        # 被票玩家: [投票玩家]
        vote_result: dict[Player, list[Player]] = await players.vote()
        # 票数: [被票玩家]
        vote_reversed: dict[int, list[Player]] = {}
        # 收集到的总票数
        total_votes = sum(map(len, vote_result.values()))

        logger.debug(f"投票结果: {vote_result}")

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

    async def run_dead_channel(self, finished: anyio.Event) -> NoReturn:
        send, recv = anyio.create_memory_object_stream[tuple[Player, UniMessage]](10)

        async def handle_cancel() -> None:
            await finished.wait()
            tg.cancel_scope.cancel()

        async def handle_send() -> NoReturn:
            while True:
                player, msg = await recv.receive()
                msg = f"玩家 {player.name}:\n" + msg
                await self.players.killed().exclude(player).broadcast(msg)

        async def handle_recv(player: Player) -> NoReturn:
            await player.killed.wait()

            counter = 0

            async def decrease() -> None:
                nonlocal counter
                await anyio.sleep(60)
                counter -= 1

            while True:
                msg = await player.receive()
                counter += 1
                if counter <= 10:
                    await send.send((player, msg))
                    tg.start_soon(decrease)
                else:
                    await player.send("❌发言频率超过限制, 该消息被屏蔽")

        async with anyio.create_task_group() as tg:
            tg.start_soon(handle_cancel)
            tg.start_soon(handle_send)
            for p in self.players:
                tg.start_soon(handle_recv, p)

    async def run(self) -> NoReturn:
        await self._fetch_group_scene()
        # 告知玩家角色信息
        await self.notify_player_role()

        # 游戏主循环
        while True:
            # 重置游戏状态，进入下一夜
            self.state.reset()
            players = self.players.alive()
            await self.send("🌙天黑请闭眼...")

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
            self.check_game_status()

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
            self.check_game_status()

    async def handle_game_finish(self, status: GameStatus) -> None:
        match status:
            case GameStatus.GoodGuy:
                winner = "好人"
            case GameStatus.Werewolf:
                winner = "狼人"
            case GameStatus.Joker:
                winner = "小丑"
            case x:
                assert_never(x)

        msg = UniMessage.text(f"🎉游戏结束，{winner}获胜\n\n")
        for p in sorted(self.players, key=lambda p: (p.role.value, p.user_id)):
            msg.at(p.user_id).text(f": {p.role_name}\n")
        await self.send(msg)
        await self.send(f"📌玩家死亡报告:\n\n{self.show_killed_players()}")

    async def start(self) -> None:
        async def daemon() -> None:
            try:
                await self.run()
            except anyio.get_cancelled_exc_class():
                logger.warning(f"{self.group.id} 的狼人杀游戏进程被取消")
            except GameFinished as result:
                await self.handle_game_finish(result.status)
                logger.info(f"{self.group.id} 的狼人杀游戏进程正常退出")
            except Exception as err:
                msg = f"{self.group.id} 的狼人杀游戏进程出现未知错误: {err!r}"
                logger.exception(msg)
                await self.send(f"❌狼人杀游戏进程出现未知错误: {err!r}")
            finally:
                finished.set()

        finished = anyio.Event()
        self.running_games.add(self)
        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(daemon)
                tg.start_soon(self.run_dead_channel, finished)
        except Exception as err:
            msg = f"{self.group.id} 的狼人杀守护进程出现错误: {err!r}"
            logger.opt(exception=err).error(msg)
        finally:
            self.running_games.discard(self)
            InputStore.cleanup(list(self._player_map), self.group.id)
