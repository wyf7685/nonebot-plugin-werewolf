import asyncio
import random
from dataclasses import dataclass
from enum import Enum, auto
from collections.abc import Callable

from nonebot.adapters import Bot
from nonebot_plugin_alconna import Target, UniMessage

import asyncio.timeouts

from .player import Player, PlayerSet, Role

player_preset: dict[int, tuple[int, int, int]] = {
    # 总人数: (狼, 神, 民)
    6: (1, 3, 2),
    7: (1, 3, 3),
    8: (2, 3, 3),
    9: (2, 4, 3),
    10: (3, 4, 3),
    11: (3, 4, 4),
    12: (3, 4, 5),
}


def init_players(bot: Bot, players: dict[str, str]) -> PlayerSet:
    preset = player_preset.get(len(players))
    if preset is None:
        r = f"{min(player_preset)}-{max(player_preset)}"
        raise ValueError(f"玩家人数不符: 应为{r}人, 传入{len(players)}人")

    roles = (
        [Role.狼人] * preset[0]
        + [Role.预言家, Role.女巫, Role.守卫, Role.猎人][: preset[1]]
        + [Role.平民] * preset[2]
    )
    random.shuffle(roles)

    async def selector(target_: Target, b: Bot):
        return target_.self_id == bot.self_id and b is bot

    return PlayerSet(
        Player.new(
            bot,
            Target(
                user_id,
                private=True,
                self_id=bot.self_id,
                selector=selector,
            ),
            players[user_id],
            role,
        )
        for user_id, role in zip(players, roles)
    )


class GameStatus(Enum):
    Good = auto()
    Bad = auto()
    Unset = auto()


@dataclass
class GameState:
    killed: Player | None = None
    shoot: Player | None = None
    protected: Player | None = None
    potion: tuple[Player | None, tuple[bool, bool]] = (None, (False, False))


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
        self.players = init_players(bot, players)
        self.state = GameState()
        self._on_exit = on_exit

    async def send(self, message: str | UniMessage):
        if isinstance(message, str):
            message = UniMessage.text(message)
        return await message.send(self.group, self.bot)

    async def notify_player_role(self) -> None:
        await asyncio.gather(*[p.notify_role() for p in self.players])

    def at_all(self) -> UniMessage:
        msg = UniMessage()
        for p in sorted(self.players, key=lambda p: (p.role.name, p.user_id)):
            msg.at(p.user_id)
        return msg

    def check_game_status(self) -> GameStatus:
        w = self.players.alive().select(Role.狼人)
        if not w.size:
            return GameStatus.Good

        p = self.players.alive().exclude(Role.狼人)
        if w.size >= p.size:
            return GameStatus.Bad

        return GameStatus.Unset

    async def select_killed(self):
        w = self.players.alive().select(Role.狼人)
        try:
            async with asyncio.timeouts.timeout(120):
                await w.interact(self)
        except TimeoutError:
            await w.broadcast("狼人阵营交互时间结束")

        if (s := w.player_selected()).size == 1:
            self.state.killed = s.pop()
            await w.broadcast(f"今晚选择的目标为: {self.state.killed.name}")
        else:
            self.state.killed = None
            await w.broadcast("狼人阵营意见未统一，此晚空刀")

    async def wait_stop(self, players: Player | PlayerSet, timeout: float) -> None:  # noqa: ASYNC109
        if isinstance(players, Player):
            players = PlayerSet([players])

        await players.wait_group_stop(self.group.id, timeout)

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
            .broadcast(f"玩家 {', '.join(p.user_id for p in players)} 加入了死者频道"),
        )

    async def handle_shoot(self, player: Player) -> Player | None:
        if player.role != Role.猎人:
            return None

        await self.send(
            UniMessage.text("猎人 ")
            .at(player.user_id)
            .text(" 死了\n请猎人决定射杀目标...")
        )
        # 猎人发动技能
        await player.interact(self)
        # 猎人射杀
        if shoot := self.state.shoot:
            await self.send(
                UniMessage.text("猎人 ")
                .at(player.user_id)
                .text(" 射杀了玩家 ")
                .at(shoot.user_id)
            )
            shoot.kill()
            await self.handle_new_dead(player)
            return shoot
        else:  # 不是哥们？
            await self.send("猎人选择了取消技能")
            return None

    async def handle_vote(self, player: Player) -> None:
        player.kill()
        await self.handle_new_dead(player)
        await self.send(
            UniMessage.text("玩家 ")
            .at(player.user_id)
            .text(" 被票出, 请发表遗言\n限时1分钟, 发送 “/stop” 结束发言")
        )
        await self.wait_stop(player, 60)

        if shoot := await self.handle_shoot(player):
            await self.send(
                UniMessage.text("玩家 ")
                .at(shoot.user_id)
                .text(" 被猎人射杀, 请发表遗言\n")
                .text("限时1分钟, 发送 “/stop” 结束发言")
            )
            await self.wait_stop(shoot, 60)

    async def run_dead_channel(self) -> None:
        queue: asyncio.Queue[tuple[Player, UniMessage]] = asyncio.Queue()

        async def send():
            while True:
                player, msg = await queue.get()
                msg = f"玩家 {player.name}:\n" + msg
                await self.players.dead().exclude(player).broadcast(msg)

        async def recv(player: Player):
            while True:
                if player.alive:
                    await asyncio.sleep(1)
                    continue
                msg = await player.receive()
                await queue.put((player, msg))

        await asyncio.gather(send(), *[recv(p) for p in self.players])

    async def run(self) -> None:
        # 告知玩家角色信息
        preset = player_preset[len(self.players)]
        await asyncio.gather(
            self.send(
                self.at_all()
                .text("\n正在分配职业，请注意查看私聊消息\n")
                .text(f"当前玩家数: {len(self.players)}\n")
                .text(f"职业分配: 狼人x{preset[0]}, 神职x{preset[1]}, 平民x{preset[2]}")
            ),
            self.notify_player_role(),
        )
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
            async def _interact(players: PlayerSet):
                # 狼人在女巫前交互
                await self.select_killed()

                # 如果女巫存活，正常交互
                if players.include(Role.女巫):
                    await players.select(Role.女巫).interact(self)
                # 否则等待 5-20s
                else:
                    await asyncio.sleep(random.uniform(5, 20))

            await asyncio.gather(
                _interact(players),
                players.select(Role.预言家, Role.守卫).interact(self),
                players.select(Role.女巫).broadcast("请等待狼人决定目标..."),
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
                    killed.kill()
            # 如果女巫使用毒药且守卫未保护，杀死该玩家
            if poison and (potioned is not None) and (potioned is not protected):
                potioned.kill()

            day_count += 1
            msg = UniMessage.text(f"【第{day_count}天】天亮了...\n")
            # 没有玩家死亡，平安夜
            if not (dead := players.dead()):
                await self.send(msg.text("昨晚是平安夜"))
            # 有玩家死亡，执行死亡流程
            else:
                # 公开死者名单
                msg.text("昨晚的死者是:\n")
                for p in dead.sorted():
                    msg.text("\n").at(p.user_id)
                await self.send(msg)

                # 如果死者包含猎人
                if dead.include(Role.猎人):
                    p = dead.select(Role.猎人).pop()
                    # 女巫毒杀无法使用技能
                    if poison and potioned is p:
                        await p.send("你昨晚被女巫毒杀，无法使用猎人技能")
                    else:
                        await self.handle_shoot(p)

            # 判断游戏状态
            if self.check_game_status() != GameStatus.Unset:
                break

            # 死者相关的通知
            await self.handle_new_dead(dead)

            # 第一晚被狼人杀死的玩家发表遗言
            if day_count == 1 and killed is not None and not killed.alive:
                await self.send(
                    UniMessage.text("当前为第一天\n请被狼人杀死的 ")
                    .at(killed.user_id)
                    .text(" 发表遗言\n限时1分钟, 发送 “/stop” 结束发言")
                )
                await self.wait_stop(killed, 60)

            # 选择当前存活玩家
            players = self.players.alive()

            # 开始自由讨论
            await self.send("接下来开始自由讨论\n限时2分钟, 全员发送 “/stop” 结束发言")
            await self.wait_stop(players, 120)
            await self.send("讨论结束, 进入投票环节\n请在私聊中选择投票或弃票")

            # 统计投票结果
            vote_result: dict[Player | None, int] = {}
            vote_reversed: dict[int, list[Player]] = {}
            for p in await asyncio.gather(*[p.vote(players) for p in players]):
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

            # 执行投票结果
            if vote_reversed:
                vs = vote_reversed[max(vote_reversed.keys())]
                # 仅有一名玩家票数最高
                if len(vs) == 1:
                    voted = vs[0]
                    await self.handle_vote(voted)
                # 平票
                else:
                    msg = UniMessage.text("玩家 ")
                    for p in vs:
                        msg.at(p.user_id)
                    msg.text(" 平票, 没有人被票出")
                    await self.send(msg)
            # 全员弃票  # 不是哥们？
            else:
                await self.send("没有人被票出")

        dead_channel.cancel()
        winner = "好人" if self.check_game_status() == GameStatus.Good else "狼人"
        msg = UniMessage.text(f"游戏结束，{winner}获胜\n\n")
        for p in sorted(self.players, key=lambda p: (p.role.name, p.user_id)):
            msg.at(p.user_id).text(f": {p.role.name}\n")
        await self.send(msg)
        self._on_exit()
