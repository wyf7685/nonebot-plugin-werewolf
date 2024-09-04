from __future__ import annotations

import asyncio
import asyncio.timeouts
import contextlib
import random
import time

from nonebot.adapters import Bot
from nonebot.log import logger
from nonebot_plugin_alconna import Target, UniMessage

from .constant import (
    GameState,
    GameStatus,
    KillReason,
    Role,
    RoleGroup,
    priesthood_proirity,
    role_preset,
    werewolf_priority,
)
from .player import Player
from .player_set import PlayerSet
from .utils import InputStore

starting_games: dict[str, dict[str, str]] = {}
running_games: dict[str, Game] = {}


def init_players(bot: Bot, game: Game, players: dict[str, str]) -> PlayerSet:
    preset = role_preset.get(len(players))
    if preset is None:
        raise ValueError(
            f"玩家人数不符: "
            f"应为 {', '.join(map(str, role_preset))} 人, 传入{len(players)}人"
        )

    roles: list[Role] = []
    roles.extend(werewolf_priority[: preset[0]])
    roles.extend(priesthood_proirity[: preset[1]])
    roles.extend([Role.Civilian] * preset[2])

    r = random.Random(time.time())
    shuffled: list[Role] = []
    for _ in range(len(players)):
        idx = r.randint(0, len(roles) - 1)
        shuffled.append(roles.pop(idx))

    async def selector(target_: Target, b: Bot):
        return target_.self_id == bot.self_id and b is bot

    return PlayerSet(
        Player.new(
            role,
            bot,
            game,
            Target(
                user_id,
                private=True,
                self_id=bot.self_id,
                selector=selector,
            ),
            players[user_id],
        )
        for user_id, role in zip(players, shuffled)
    )


class Game:
    bot: Bot
    group: Target
    players: PlayerSet
    state: GameState
    killed_players: list[Player]

    def __init__(
        self,
        bot: Bot,
        group: Target,
        players: dict[str, str],
    ) -> None:
        self.bot = bot
        self.group = group
        self.players = init_players(bot, self, players)
        self.state = GameState(0)
        self.killed_players = []

    async def send(self, message: str | UniMessage):
        if isinstance(message, str):
            message = UniMessage.text(message)
        return await message.send(self.group, self.bot)

    def at_all(self) -> UniMessage:
        msg = UniMessage()
        for p in sorted(self.players, key=lambda p: (p.role_name, p.user_id)):
            msg.at(p.user_id)
        return msg

    def check_game_status(self) -> GameStatus:
        players = self.players.alive()
        w = players.select(RoleGroup.Werewolf)
        p = players.exclude(RoleGroup.Werewolf)

        if w.size >= p.size:
            return GameStatus.Bad
        if not p.select(Role.Civilian):
            return GameStatus.Bad
        if not p.exclude(Role.Civilian):
            return GameStatus.Bad
        if not w.size:
            return GameStatus.Good

        return GameStatus.Unset

    def show_killed_players(self) -> str:
        msg = ""

        for player in self.killed_players:
            if player.kill_info is None:
                continue

            msg += f"{player.name} 被 " + ", ".join(
                p.name for p in player.kill_info.killers
            )
            match player.kill_info.reason:
                case KillReason.Kill:
                    msg += " 刀了"
                case KillReason.Poison:
                    msg += " 毒死"
                case KillReason.Shoot:
                    msg += " 射杀"
                case KillReason.Vote:
                    msg += " 票出"
            msg += "\n\n"

        return msg.strip()

    async def notify_player_role(self) -> None:
        preset = role_preset[len(self.players)]
        await asyncio.gather(
            self.send(
                self.at_all()
                .text("\n\n正在分配职业，请注意查看私聊消息\n")
                .text(f"当前玩家数: {len(self.players)}\n")
                .text(f"职业分配: 狼人x{preset[0]}, 神职x{preset[1]}, 平民x{preset[2]}")
            ),
            *[p.notify_role() for p in self.players],
        )

    async def wait_stop(
        self,
        players: Player | PlayerSet,
        timeout_secs: float,
    ) -> None:
        if isinstance(players, Player):
            players = PlayerSet([players])

        async def wait(p: Player):
            while True:
                msg = await InputStore.fetch(p.user_id, self.group.id)
                if msg.extract_plain_text() == "/stop":
                    break

        with contextlib.suppress(TimeoutError):
            async with asyncio.timeouts.timeout(timeout_secs):
                await asyncio.gather(*[wait(p) for p in players])

    async def interact(
        self,
        type_: Player | Role | RoleGroup,
        timeout_secs: float,
    ) -> None:
        players = self.players.alive().select(type_)
        text = (
            type_.role_name  # Player
            if isinstance(type_, Player)
            else (
                type_.name  # Role
                if isinstance(type_, Role)
                else f"{type_.name}阵营"  # RoleGroup
            )
        )

        await players.broadcast(f"{text}交互开始，限时 {timeout_secs/60:.2f} 分钟")
        try:
            await players.interact(timeout_secs)
        except TimeoutError:
            await players.broadcast(f"{text}交互时间结束")

    async def select_killed(self) -> None:
        players = self.players.alive()
        self.state.killed = None

        w = players.select(RoleGroup.Werewolf)
        await self.interact(RoleGroup.Werewolf, 120)
        if (s := w.player_selected()).size == 1:
            self.state.killed = s.pop()
            await w.broadcast(f"今晚选择的目标为: {self.state.killed.name}")
        else:
            await w.broadcast("狼人阵营意见未统一，此晚空刀")

        # 如果女巫存活，正常交互，限时1分钟
        if players.include(Role.Witch):
            await self.interact(Role.Witch, 60)
        # 否则等待 5-20s
        else:
            await asyncio.sleep(random.uniform(5, 20))

    async def handle_new_dead(self, players: Player | PlayerSet) -> None:
        if isinstance(players, Player):
            players = PlayerSet([players])
        if not players:
            return

        await asyncio.gather(
            players.broadcast(
                "你已加入死者频道，请勿在群内继续发言\n"
                "私聊发送消息将转发至其他已死亡玩家"
            ),
            self.players.dead()
            .exclude(*players)
            .broadcast(f"玩家 {', '.join(p.name for p in players)} 加入了死者频道"),
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

            (shooter, shoot) = self.state.shoot
            if shooter is not None and shoot is not None:
                await self.send(
                    UniMessage.text("玩家 ")
                    .at(shoot.user_id)
                    .text(f" 被{shooter.role_name}射杀, 请发表遗言\n")
                    .text("限时1分钟, 发送 “/stop” 结束发言")
                )
                await self.wait_stop(shoot, 60)
                self.state.shoot = (None, None)
                await self.post_kill(shoot)

    async def run_vote(self) -> None:
        # 筛选当前存活玩家
        players = self.players.alive()

        # 被票玩家: [投票玩家]
        vote_result: dict[Player, list[Player]] = await players.vote(60)
        # 票数: [被票玩家]
        vote_reversed: dict[int, list[Player]] = {}
        # 收集到的总票数
        total_votes = sum(map(len, vote_result.values()))

        # 投票结果公示
        msg = UniMessage.text("投票结果:\n")
        for p, v in sorted(vote_result.items(), key=lambda x: len(x[1]), reverse=True):
            if p is not None:
                msg.at(p.user_id).text(f": {len(v)} 票\n")
                vote_reversed[len(v)] = [*vote_reversed.get(len(v), []), p]
        if v := (len(players) - total_votes):
            msg.text(f"弃票: {v} 票\n")
        await self.send(msg)

        # 全员弃票  # 不是哥们？
        if total_votes == 0:
            await self.send("没有人被票出")
            return

        # 弃票大于最高票
        if (len(players) - total_votes) >= max(vote_reversed.keys()):
            await self.send("弃票数大于最高票数, 没有人被票出")
            return

        # 平票
        if len(vs := vote_reversed[max(vote_reversed.keys())]) != 1:
            await self.send(
                UniMessage.text("玩家 ")
                .text(", ".join(p.name for p in vs))
                .text(" 平票, 没有人被票出")
            )
            return

        # 仅有一名玩家票数最高
        voted = vs.pop()
        if not await voted.kill(KillReason.Vote, *vote_result[voted]):
            # 投票放逐失败 (例: 白痴)
            return

        # 遗言
        await self.send(
            UniMessage.text("玩家 ")
            .at(voted.user_id)
            .text(" 被投票放逐, 请发表遗言\n")
            .text("限时1分钟, 发送 “/stop” 结束发言")
        )
        await self.wait_stop(voted, 60)
        await self.post_kill(voted)

    async def run_dead_channel(self) -> None:
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[tuple[Player, UniMessage]] = asyncio.Queue()

        async def send():
            while True:
                player, msg = await queue.get()
                msg = f"玩家 {player.name}:\n" + msg
                await self.players.dead().exclude(player).broadcast(msg)

        async def recv(player: Player):
            counter = 0

            def decrease():
                nonlocal counter
                counter -= 1

            while True:
                if not player.killed:
                    await asyncio.sleep(1)
                    continue
                msg = await player.receive()
                counter += 1
                if counter <= 10:
                    await queue.put((player, msg))
                    loop.call_later(60, decrease)
                else:
                    await player.send("发言频率超过限制, 该消息被屏蔽")

        await asyncio.gather(send(), *[recv(p) for p in self.players])

    async def run(self) -> None:
        # 告知玩家角色信息
        await self.notify_player_role()
        # 天数记录 主要用于第一晚狼人击杀的遗言
        day_count = 0

        while self.check_game_status() == GameStatus.Unset:
            # 重置游戏状态，进入下一夜
            self.state = GameState(day_count)
            players = self.players.alive()
            await self.send("天黑请闭眼...")

            # 狼人、预言家、守卫 同时交互，女巫在狼人后交互
            await asyncio.gather(
                self.select_killed(),
                players.select(Role.Witch).broadcast("请等待狼人决定目标..."),
                players.select(Role.Civilian).broadcast("请等待其他玩家结束交互..."),
                self.interact(Role.Prophet, 60),
                self.interact(Role.Guard, 60),
            )

            # 狼人击杀目标
            killed = self.state.killed
            # 守卫保护目标
            protected = self.state.protected
            # 女巫的操作目标和内容
            potioned, (antidote, poison) = self.state.potion

            # 狼人未空刀
            if killed is not None:
                # 除非守卫保护或女巫使用解药，否则狼人正常击杀玩家
                if not ((killed is protected) or (antidote and potioned is killed)):
                    await killed.kill(
                        KillReason.Kill, *players.select(RoleGroup.Werewolf)
                    )
            # 如果女巫使用毒药且守卫未保护，杀死该玩家
            if poison and (potioned is not None) and (potioned is not protected):
                await potioned.kill(KillReason.Poison, *players.select(Role.Witch))

            day_count += 1
            msg = UniMessage.text(f"『第{day_count}天』天亮了...\n")
            # 没有玩家死亡，平安夜
            if not (dead := players.dead()):
                await self.send(msg.text("昨晚是平安夜"))
            # 有玩家死亡，公布死者名单
            else:
                msg.text("昨晚的死者是:")
                for p in dead.sorted():
                    msg.text("\n").at(p.user_id)
                await self.send(msg)

            # 第一晚被狼人杀死的玩家发表遗言
            if day_count == 1 and killed is not None and not killed.alive:
                await self.send(
                    UniMessage.text("当前为第一天\n请被狼人杀死的 ")
                    .at(killed.user_id)
                    .text(" 发表遗言\n")
                    .text("限时1分钟, 发送 “/stop” 结束发言")
                )
                await self.wait_stop(killed, 60)
            await self.post_kill(dead)

            # 判断游戏状态
            if self.check_game_status() != GameStatus.Unset:
                break

            # 公示存活玩家
            await self.send(f"当前存活玩家: \n\n{self.players.alive().show()}")

            # 开始自由讨论
            await self.send("接下来开始自由讨论\n限时2分钟, 全员发送 “/stop” 结束发言")
            await self.wait_stop(self.players.alive(), 120)

            # 开始投票
            await self.send("讨论结束, 进入投票环节，限时1分钟\n请在私聊中进行投票交互")
            await self.run_vote()

        # 游戏结束
        winner = "好人" if self.check_game_status() == GameStatus.Good else "狼人"
        msg = UniMessage.text(f"🎉游戏结束，{winner}获胜\n\n")
        for p in sorted(self.players, key=lambda p: (p.role.value, p.user_id)):
            msg.at(p.user_id).text(f": {p.role_name}\n")
        await self.send(msg)
        await self.send(f"玩家死亡报告:\n\n{self.show_killed_players()}")

    def start(self):
        event = asyncio.Event()
        game_task = asyncio.create_task(self.run())
        game_task.add_done_callback(lambda _: event.set())
        dead_channel = asyncio.create_task(self.run_dead_channel())

        async def daemon():
            await event.wait()

            try:
                game_task.result()
                logger.info(f"{self.group.id} 的狼人杀游戏进程正常退出")
            except asyncio.CancelledError as err:
                logger.warning(f"{self.group.id} 的狼人杀游戏进程被取消: {err}")
            except Exception as err:
                msg = f"{self.group.id} 的狼人杀游戏进程出现错误: {err!r}"
                logger.opt(exception=err).error(msg)
                await self.send(msg)
            finally:
                dead_channel.cancel()
                running_games.pop(self.group.id, None)

        def daemon_callback(task: asyncio.Task[None]):
            if err := task.exception():
                logger.opt(exception=err).error(
                    f"{self.group.id} 的狼人杀守护进程出现错误: {err!r}"
                )

        running_games[self.group.id] = self
        asyncio.create_task(daemon()).add_done_callback(daemon_callback)
