# ruff: noqa: FBT001

from typing import Annotated, NoReturn

from nonebot.internal.matcher import current_matcher
from nonebot.params import Depends
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    CommandMeta,
    Subcommand,
    UniMessage,
    on_alconna,
)

from ..config import GameBehavior

game_behavior_cache_key = "GAME_BEHAVIOR_KEY"


def _behavior(state: T_State) -> GameBehavior:
    if game_behavior_cache_key not in state:
        state[game_behavior_cache_key] = GameBehavior.get()
    return state[game_behavior_cache_key]


Behavior = Annotated[GameBehavior, Depends(_behavior)]


async def finish(text: str) -> NoReturn:
    behavior: GameBehavior = current_matcher.get().state[game_behavior_cache_key]
    behavior.save()
    await UniMessage.text(text).finish(reply_to=True)


alc = Alconna(
    "狼人杀配置",
    Subcommand(
        "show_roles",
        Args["enabled#是否启用", bool],
        alias={"显示职业"},
        help_text="设置游戏开始时是否显示职业列表",
    ),
    Subcommand(
        "speak_order",
        Args["enabled#是否启用", bool],
        alias={"发言顺序"},
        help_text="设置是否按顺序发言",
    ),
    Subcommand(
        "dead_chat",
        Args["limit#限制时间", int],
        alias={"死亡聊天"},
        help_text="设置死亡玩家发言每秒限制",
    ),
    Subcommand(
        "timeout",
        Subcommand(
            "prepare",
            Args["time#时间", int],
            help_text="准备阶段超时时间(秒)",
        ),
        Subcommand(
            "speak",
            Args["time#时间", int],
            help_text="发言阶段超时时间(秒)",
        ),
        Subcommand(
            "group_speak",
            Args["time#时间", int],
            help_text="集体发言超时时间(秒)",
        ),
        Subcommand(
            "interact",
            Args["time#时间", int],
            help_text="互动阶段超时时间(秒)",
        ),
        Subcommand(
            "vote",
            Args["time#时间", int],
            help_text="投票阶段超时时间(秒)",
        ),
        Subcommand(
            "werewolf",
            Args["time#时间", int],
            help_text="狼人阶段超时时间(秒)",
        ),
        alias={"超时"},
        help_text="设置各阶段超时时间",
    ),
    meta=CommandMeta(
        description="修改狼人杀游戏配置",
        usage="狼人杀配置 --help",
        example=(
            "狼人杀配置\n"
            "狼人杀配置 显示职业 true\n"
            "狼人杀配置 发言顺序 false\n"
            "狼人杀配置 死亡聊天 30\n"
            "狼人杀配置 超时 准备 300"
        ),
    ),
)

edit_behavior = on_alconna(
    alc,
    permission=SUPERUSER,
    use_cmd_start=True,
)


@edit_behavior.assign("show_roles")
async def set_show_roles(enabled: bool, behavior: Behavior) -> None:
    behavior.show_roles_list_on_start = enabled
    await finish(f"已{'启用' if enabled else '禁用'}游戏开始时显示职业列表")


@edit_behavior.assign("speak_order")
async def set_speak_order(enabled: bool, behavior: Behavior) -> None:
    behavior.speak_in_turn = enabled
    await finish(f"已{'启用' if enabled else '禁用'}按顺序发言")


@edit_behavior.assign("dead_chat")
async def set_dead_chat(limit: int, behavior: Behavior) -> None:
    if not 0 < limit <= 300:  # 最大限制5分钟
        await finish("限制时间必须在 1-300 秒之间")
    behavior.dead_channel_rate_limit = limit
    await finish(f"已设置死亡玩家发言限制为 {limit} 秒")


@edit_behavior.assign("timeout.prepare")
async def set_prepare_timeout(time: int, behavior: Behavior) -> None:
    if not 30 <= time <= 600:  # 30秒到10分钟
        await finish("准备时间必须在 30-600 秒之间")
    behavior.timeout.prepare = time
    await finish(f"已设置准备阶段超时时间为 {time} 秒")


@edit_behavior.assign("timeout.speak")
async def set_speak_timeout(time: int, behavior: Behavior) -> None:
    if not 30 <= time <= 300:  # 30秒到5分钟
        await finish("发言时间必须在 30-300 秒之间")
    behavior.timeout.speak = time
    await finish(f"已设置发言阶段超时时间为 {time} 秒")


@edit_behavior.assign("timeout.group_speak")
async def set_group_speak_timeout(time: int, behavior: Behavior) -> None:
    if not 60 <= time <= 600:  # 1分钟到10分钟
        await finish("集体发言时间必须在 60-600 秒之间")
    behavior.timeout.group_speak = time
    await finish(f"已设置集体发言超时时间为 {time} 秒")


@edit_behavior.assign("timeout.interact")
async def set_interact_timeout(time: int, behavior: Behavior) -> None:
    if not 15 <= time <= 120:  # 15秒到2分钟
        await finish("互动时间必须在 15-120 秒之间")
    behavior.timeout.interact = time
    await finish(f"已设置互动阶段超时时间为 {time} 秒")


@edit_behavior.assign("timeout.vote")
async def set_vote_timeout(time: int, behavior: Behavior) -> None:
    if not 15 <= time <= 120:  # 15秒到2分钟
        await finish("投票时间必须在 15-120 秒之间")
    behavior.timeout.vote = time
    await finish(f"已设置投票阶段超时时间为 {time} 秒")


@edit_behavior.assign("timeout.werewolf")
async def set_werewolf_timeout(time: int, behavior: Behavior) -> None:
    if not 30 <= time <= 180:  # 30秒到3分钟
        await finish("狼人时间必须在 30-180 秒之间")
    behavior.timeout.werewolf = time
    await finish(f"已设置狼人阶段超时时间为 {time} 秒")


@edit_behavior.handle()
async def handle_default(behavior: Behavior) -> None:
    lines = [
        "当前游戏配置:",
        f"游戏开始显示职业列表: {'是' if behavior.show_roles_list_on_start else '否'}",
        f"白天讨论按顺序发言: {'是' if behavior.speak_in_turn else '否'}",
        f"死亡玩家发言转发限制: {behavior.dead_channel_rate_limit} 秒",
        "",
        "超时时间设置:",
        f"准备阶段: {behavior.timeout.prepare} 秒",
        f"发言阶段: {behavior.timeout.speak} 秒",
        f"集体发言: {behavior.timeout.group_speak} 秒",
        f"互动阶段: {behavior.timeout.interact} 秒",
        f"投票阶段: {behavior.timeout.vote} 秒",
        f"狼人阶段: {behavior.timeout.werewolf} 秒",
    ]
    await finish("\n".join(lines))
