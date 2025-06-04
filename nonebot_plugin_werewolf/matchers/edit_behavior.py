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

from ..config import GameBehavior, config

GAME_BEHAVIOR_CACHE_KEY = "GAME_BEHAVIOR_CACHE_KEY"


def _behavior(state: T_State) -> GameBehavior:
    if GAME_BEHAVIOR_CACHE_KEY not in state:
        state[GAME_BEHAVIOR_CACHE_KEY] = GameBehavior.get()
    return state[GAME_BEHAVIOR_CACHE_KEY]


Behavior = Annotated[GameBehavior, Depends(_behavior)]


async def finish(text: str) -> NoReturn:
    behavior: GameBehavior = current_matcher.get().state[GAME_BEHAVIOR_CACHE_KEY]
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
        "speak_in_turn",
        Args["enabled#是否启用", bool],
        alias={"发言顺序"},
        help_text="设置是否按顺序发言",
    ),
    Subcommand(
        "dead_chat",
        Args["limit#每分钟限制次数", int],
        alias={"死亡聊天"},
        help_text="设置死亡玩家发言频率限制",
    ),
    Subcommand(
        "werewolf_multi_select",
        Args["enabled#是否启用", bool],
        alias={"狼人多选"},
        help_text="设置狼人多选时是否从已选玩家中随机选择目标, 为否时将视为空刀",
    ),
    Subcommand(
        "timeout",
        Subcommand(
            "prepare",
            Args["time#时间", int],
            alias={"准备阶段"},
            help_text="准备阶段超时时间(秒)",
        ),
        Subcommand(
            "speak",
            Args["time#时间", int],
            alias={"个人发言"},
            help_text="个人发言超时时间(秒)",
        ),
        Subcommand(
            "group_speak",
            Args["time#时间", int],
            alias={"集体发言"},
            help_text="集体发言超时时间(秒)",
        ),
        Subcommand(
            "interact",
            Args["time#时间", int],
            alias={"交互阶段"},
            help_text="交互阶段超时时间(秒)",
        ),
        Subcommand(
            "vote",
            Args["time#时间", int],
            alias={"投票阶段"},
            help_text="投票阶段超时时间(秒)",
        ),
        Subcommand(
            "werewolf",
            Args["time#时间", int],
            alias={"狼人交互"},
            help_text="狼人交互超时时间(秒)",
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
    use_cmd_start=config.use_cmd_start,
    priority=config.matcher_priority.behavior,
)


@edit_behavior.assign("show_roles")
async def set_show_roles(behavior: Behavior, enabled: bool) -> None:
    behavior.show_roles_list_on_start = enabled
    await finish(f"已{'启用' if enabled else '禁用'}游戏开始时显示职业列表")


@edit_behavior.assign("speak_in_turn")
async def set_speak_order(behavior: Behavior, enabled: bool) -> None:
    behavior.speak_in_turn = enabled
    await finish(f"已{'启用' if enabled else '禁用'}按顺序发言")


@edit_behavior.assign("dead_chat")
async def set_dead_chat(behavior: Behavior, limit: int) -> None:
    if limit < 0:
        await finish("限制次数必须大于零")
    behavior.dead_channel_rate_limit = limit
    await finish(f"已设置死亡玩家发言限制为 {limit} 次/分钟")


@edit_behavior.assign("werewolf_multi_select")
async def set_werewolf_multi_select(behavior: Behavior, enabled: bool) -> None:
    behavior.werewolf_multi_select = enabled
    await finish(
        f"已{'启用' if enabled else '禁用'}狼人多选\n"
        "注: 狼人意见未统一时随机选择已选玩家"
    )


@edit_behavior.assign("timeout.prepare")
async def set_prepare_timeout(behavior: Behavior, time: int) -> None:
    if time < 300:
        await finish("准备时间必须大于 300 秒")
    behavior.timeout.prepare = time
    await finish(f"已设置准备阶段超时时间为 {time} 秒")


@edit_behavior.assign("timeout.speak")
async def set_speak_timeout(behavior: Behavior, time: int) -> None:
    if time < 60:
        await finish("发言时间必须大于 60 秒")
    behavior.timeout.speak = time
    await finish(f"已设置发言阶段超时时间为 {time} 秒")


@edit_behavior.assign("timeout.group_speak")
async def set_group_speak_timeout(behavior: Behavior, time: int) -> None:
    if time < 120:
        await finish("集体发言时间必须大于 120 秒")
    behavior.timeout.group_speak = time
    await finish(f"已设置集体发言超时时间为 {time} 秒")


@edit_behavior.assign("timeout.interact")
async def set_interact_timeout(behavior: Behavior, time: int) -> None:
    if time < 60:
        await finish("交互时间必须大于 60 秒")
    behavior.timeout.interact = time
    await finish(f"已设置交互阶段超时时间为 {time} 秒")


@edit_behavior.assign("timeout.vote")
async def set_vote_timeout(behavior: Behavior, time: int) -> None:
    if time < 60:
        await finish("投票时间必须大于 60 秒")
    behavior.timeout.vote = time
    await finish(f"已设置投票阶段超时时间为 {time} 秒")


@edit_behavior.assign("timeout.werewolf")
async def set_werewolf_timeout(behavior: Behavior, time: int) -> None:
    if time < 120:
        await finish("狼人交互时间必须大于 120 秒")
    behavior.timeout.werewolf = time
    await finish(f"已设置狼人交互阶段超时时间为 {time} 秒")


@edit_behavior.handle()
async def handle_default(behavior: Behavior) -> None:
    timeout = behavior.timeout
    lines = [
        "当前游戏配置:",
        "",
        f"游戏开始发送职业列表: {'是' if behavior.show_roles_list_on_start else '否'}",
        f"白天讨论按顺序发言: {'是' if behavior.speak_in_turn else '否'}",
        f"死亡玩家发言转发限制: {behavior.dead_channel_rate_limit} 次/分钟",
        f"狼人多选(意见未统一时随机选择已选玩家): {'是' if behavior.werewolf_multi_select else '否'}",  # noqa: E501
        "",
        "超时时间设置:",
        f"准备阶段: {timeout.prepare} 秒",
        f"个人发言: {timeout.speak} 秒",
        f"集体发言: {timeout.group_speak} 秒",
        f"投票阶段: {timeout.vote} 秒",
        f"交互阶段: {timeout.interact} 秒",
        f"狼人交互: {timeout.werewolf} 秒",
    ]
    await finish("\n".join(lines))
