from typing_extensions import override

from nonebot_plugin_alconna import UniMessage

from ..config import stop_command_prompt
from ..models import Role, RoleGroup
from ..player import InteractProvider, Player
from ..utils import as_player_set


class WitchInteractProvider(InteractProvider["Witch"]):
    antidote = InteractProvider.proxy(bool)
    poison = InteractProvider.proxy(bool)

    @override
    async def before(self) -> None:
        await self.p.send("ℹ️请等待狼人决定目标...")
        await self.game.context.werewolf_finished.wait()

    async def handle_killed(self) -> bool:
        if (killed := self.game.context.killed) is None:
            await self.p.send("ℹ️今晚没有人被刀")
            return False

        msg = UniMessage.text(f"🔪今晚 {killed.name} 被刀了\n\n")

        if not self.antidote:
            await self.p.send(msg.text("⚙️你已经用过解药了"))
            return False

        msg.text(f"✏️使用解药请发送 “1”\n❌不使用解药请发送 “{stop_command_prompt}”")
        await self.p.send(
            msg,
            stop_btn_label="不使用解药",
            select_players=as_player_set(killed),
        )

        if not await self.p.select_player(
            as_player_set(killed),
            on_stop=f"ℹ️你选择不对 {killed.name} 使用解药",
            on_index_error=f"⚠️输入错误: 请输入 “1” 或 “{stop_command_prompt}”",
            stop_btn_label="不使用解药",
        ):
            return False

        self.antidote = False
        self.selected = killed
        self.game.context.antidote.add(killed)
        await self.p.send(f"✅你对 {killed.name} 使用了解药，回合结束")
        return True

    @override
    async def interact(self) -> None:
        if await self.handle_killed():
            return

        if not self.poison:
            await self.p.send("⚙️你没有可以使用的药水，回合结束")
            return

        players = self.game.players.alive()
        await self.p.send(
            "💫你有一瓶毒药\n"
            "玩家列表:\n"
            f"{players.show()}\n\n"
            "🧪发送玩家编号使用毒药\n"
            f"❌发送 “{stop_command_prompt}” 结束回合(不使用药水)",
            stop_btn_label="结束回合",
            select_players=players,
        )

        if selected := await self.p.select_player(
            players,
            on_stop="ℹ️你选择不使用毒药，回合结束",
            stop_btn_label="结束回合",
        ):
            self.poison = False
            self.selected = selected
            self.game.context.poison.add(self.p)
            await self.p.send(
                f"✅当前回合选择对玩家 {selected.name} 使用毒药\n回合结束"
            )


class Witch(Player):
    role = Role.WITCH
    role_group = RoleGroup.GOODGUY
    interact_provider = WitchInteractProvider

    antidote: bool = True
    poison: bool = True
