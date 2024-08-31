import asyncio
import asyncio.timeouts
import random
from collections.abc import Callable

from nonebot.adapters import Bot
from nonebot_plugin_alconna import Target, UniMessage

from .constant import GameState, GameStatus, KillReason, Role, RoleGroup, player_preset
from .player import Player, PlayerSet


def init_players(bot: Bot, game: "Game", players: dict[str, str]) -> PlayerSet:
    preset = player_preset.get(len(players))
    if preset is None:
        raise ValueError(
            f"玩家人数不符: "
            f"应为{min(player_preset)}-{max(player_preset)}人, 传入{len(players)}人"
        )

    roles: list[Role] = []
    roles.extend([Role.狼人, Role.狼人, Role.狼王, Role.狼人][: preset[0]])
    roles.extend([Role.预言家, Role.女巫, Role.猎人, Role.守卫, Role.白痴][: preset[1]])
    roles.extend([Role.平民] * preset[2])

    random.shuffle(roles)

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
        for user_id, role in zip(players, roles)
    )


class Game:
    bot: Bot
    group: Target
    players: PlayerSet
    state: GameState
    _on_exit: Callable[[], None]

    def __init__(
        self,
        bot: Bot,
        group: Target,
        players: dict[str, str],
        on_exit: Callable[[], None],
    ) -> None:
        self.bot = bot
        self.group = group
        self.players = init_players(bot, self, players)
        self.state = GameState()
        self._on_exit = on_exit

    async def send(self, message: str | UniMessage):
        if isinstance(message, str):
            message = UniMessage.text(message)
        return await message.send(self.group, self.bot)

    def at_all(self) -> UniMessage:
        msg = UniMessage()
        for p in sorted(self.players, key=lambda p: (p.role.name, p.user_id)):
            msg.at(p.user_id)
        return msg

    def check_game_status(self) -> GameStatus:
        players = self.players.alive()

        w = players.select(RoleGroup.狼人)
        if not w.size:
            return GameStatus.Good

        p = players.exclude(RoleGroup.狼人)
        if w.size >= p.size:
            return GameStatus.Bad
        if not players.select(Role.平民):
            return GameStatus.Bad
        if not players.select(RoleGroup.好人).exclude(Role.平民):
            return GameStatus.Bad

        return GameStatus.Unset

    async def notify_player_role(self) -> None:
        preset = player_preset[len(self.players)]
        await asyncio.gather(
            self.send(
                self.at_all()
                .text("\n正在分配职业，请注意查看私聊消息\n")
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

        await players.wait_group_stop(self.group.id, timeout_secs)

    async def interact(
        self,
        type_: Player | Role | RoleGroup,
        timeout_secs: float,
    ) -> None:
        players = self.players.alive().select(type_)
        text = (
            type_.role.name  # Player
            if isinstance(type_, Player)
            else (
                type_.name if isinstance(type_, Role) else f"{type_.name}阵营"  # Role
            )  # RoleGroup
        )

        await players.broadcast(f"{text}交互开始，限时 {timeout_secs/60:.2f} 分钟")
        try:
            await players.interact(timeout_secs)
        except TimeoutError:
            await players.broadcast(f"{text}交互时间结束")

    async def select_killed(self) -> None:
        players = self.players.alive()
        self.state.killed = None

        w = players.select(RoleGroup.狼人)
        await self.interact(RoleGroup.狼人, 120)
        if (s := w.player_selected()).size == 1:
            self.state.killed = s.pop()
            await w.broadcast(f"今晚选择的目标为: {self.state.killed.name}")
        else:
            await w.broadcast("狼人阵营意见未统一，此晚空刀")

        # 如果女巫存活，正常交互，限时1分钟
        if players.include(Role.女巫):
            await self.interact(Role.女巫, 60)
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

        for player in players:
            await player.post_kill()
            await self.handle_new_dead(player)

            (shooter, shoot) = self.state.shoot
            if shooter is not None and shoot is not None:
                await self.send(
                    UniMessage.text("玩家 ")
                    .at(shoot.user_id)
                    .text(f" 被{shooter.role.name}射杀, 请发表遗言\n")
                    .text("限时1分钟, 发送 “/stop” 结束发言")
                )
                await self.wait_stop(shoot, 60)
            self.state.shoot = (None, None)

    async def run_vote(self) -> None:
        # 统计投票结果
        vote_result: dict[Player | None, int] = {}
        vote_reversed: dict[int, list[Player]] = {}
        for p in await self.players.alive().vote(60):
            vote_result[p] = vote_result.get(p, 0) + 1

        # 投票结果公示
        msg = UniMessage.text("投票结果:\n")
        for p, v in sorted(vote_result.items(), key=lambda x: x[1], reverse=True):
            if p is not None:
                msg.at(p.user_id).text(f": {v} 票\n")
                vote_reversed[v] = [*vote_reversed.get(v, []), p]
        if v := vote_result.get(None, 0):
            msg.text(f"弃票: {v} 票\n")
        await self.send(msg)

        # 全员弃票  # 不是哥们？
        if not vote_reversed:
            await self.send("没有人被票出")
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
        if not await voted.kill(KillReason.Vote):
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
        queue: asyncio.Queue[tuple[Player, UniMessage]] = asyncio.Queue()

        async def send():
            while True:
                player, msg = await queue.get()
                msg = f"玩家 {player.name}:\n" + msg
                await self.players.dead().exclude(player).broadcast(msg)

        async def recv(player: Player):
            while True:
                if not player.killed:
                    await asyncio.sleep(1)
                    continue
                msg = await player.receive()
                await queue.put((player, msg))

        await asyncio.gather(send(), *[recv(p) for p in self.players])

    async def run(self) -> None:
        # 告知玩家角色信息
        await self.notify_player_role()
        # 死者频道
        dead_channel = asyncio.create_task(self.run_dead_channel())
        # 天数记录 主要用于第一晚狼人击杀的遗言
        day_count = 0

        while self.check_game_status() == GameStatus.Unset:
            # 重置游戏状态，进入下一夜
            self.state = GameState()
            players = self.players.alive()
            await self.send("天黑请闭眼...")

            # 狼人、预言家、守卫 同时交互，女巫在狼人后交互
            await asyncio.gather(
                self.select_killed(),
                players.select(Role.女巫).broadcast("请等待狼人决定目标..."),
                self.interact(Role.预言家, 60),
                self.interact(Role.守卫, 60),
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
                    await killed.kill(KillReason.Kill)
            # 如果女巫使用毒药且守卫未保护，杀死该玩家
            if poison and (potioned is not None) and (potioned is not protected):
                await potioned.kill(KillReason.Poison)

            day_count += 1
            msg = UniMessage.text(f"【第{day_count}天】天亮了...\n")
            # 没有玩家死亡，平安夜
            if not (dead := players.dead()):
                await self.send(msg.text("昨晚是平安夜"))
            # 有玩家死亡，执行死亡流程
            else:
                # 公开死者名单
                msg.text("昨晚的死者是:")
                for p in dead.sorted():
                    msg.text("\n").at(p.user_id)
                await self.send(msg)
                await self.post_kill(dead)

            # 判断游戏状态
            if self.check_game_status() != GameStatus.Unset:
                break

            # 公示存活玩家
            await self.send(f"当前存活玩家: \n\n{self.players.alive().show()}")

            # 第一晚被狼人杀死的玩家发表遗言
            if day_count == 1 and killed is not None and not killed.alive:
                await self.send(
                    UniMessage.text("当前为第一天\n请被狼人杀死的 ")
                    .at(killed.user_id)
                    .text(" 发表遗言\n限时1分钟, 发送 “/stop” 结束发言")
                )
                await self.wait_stop(killed, 60)

            # 开始自由讨论
            await self.send("接下来开始自由讨论\n限时2分钟, 全员发送 “/stop” 结束发言")
            await self.wait_stop(self.players.alive(), 120)

            # 开始投票
            await self.send("讨论结束, 进入投票环节，限时1分钟\n请在私聊中进行投票交互")
            await self.run_vote()

        # 游戏结束
        dead_channel.cancel()
        winner = "好人" if self.check_game_status() == GameStatus.Good else "狼人"
        msg = UniMessage.text(f"游戏结束，{winner}获胜\n\n")
        for p in sorted(self.players, key=lambda p: (p.role.name, p.user_id)):
            msg.at(p.user_id).text(f": {p.role.name}\n")
        await self.send(msg)
        self._on_exit()
