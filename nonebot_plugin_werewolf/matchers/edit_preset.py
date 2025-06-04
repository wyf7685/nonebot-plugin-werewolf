from typing import Any, NoReturn

import nonebot_plugin_waiter.unimsg as waiter
from arclet.alconna import AllParam
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    CommandMeta,
    Match,
    Subcommand,
    UniMessage,
    on_alconna,
)

from ..config import PresetData, config
from ..models import Role

alc = Alconna(
    "狼人杀预设",
    Subcommand(
        "role",
        Args["total#总人数", int],
        Args["werewolf#狼人数量", int],
        Args["priesthood#神职数量", int],
        Args["civilian#平民数量", int],
        alias={"职业"},
        help_text="设置总人数为 <total> 的职业分配预设",
    ),
    Subcommand(
        "del",
        Args["total#总人数", int],
        alias={"删除"},
        help_text="删除总人数为 <total> 的职业分配预设",
    ),
    Subcommand(
        "werewolf",
        Args["roles?#职业", AllParam],
        alias={"狼人"},
        help_text="设置狼人优先级",
    ),
    Subcommand(
        "priesthood",
        Args["roles?#职业", AllParam],
        alias={"神职"},
        help_text="设置神职优先级",
    ),
    Subcommand(
        "jester",
        Args["probability?#概率(百分比)", float],
        alias={"小丑"},
        help_text="设置小丑概率",
    ),
    Subcommand("reset", alias={"重置"}, help_text="重置为默认预设"),
    meta=CommandMeta(
        description="编辑狼人杀游戏预设",
        usage="狼人杀预设 --help",
        example=(
            "狼人杀预设\n"
            "狼人杀预设 职业 6 1 2 3\n"
            "狼人杀预设 删除 6\n"
            "狼人杀预设 狼人 狼 狼 狼王 狼 狼\n"
            "狼人杀预设 神职 巫 预 猎 守卫 白痴\n"
            "狼人杀预设 小丑 15\n"
            "狼人杀预设 重置"
        ),
        author="wyf7685",
    ),
)

edit_preset = on_alconna(
    alc,
    permission=SUPERUSER,
    use_cmd_start=config.use_cmd_start,
    priority=config.matcher_priority.preset,
)


async def finish(text: str) -> NoReturn:
    await UniMessage.text(text).finish(reply_to=True)


def display_roles(roles: list[Role]) -> str:
    return ", ".join(role.display for role in roles)


@edit_preset.assign("role")
async def assign_role(
    total: Match[int],
    werewolf: Match[int],
    priesthood: Match[int],
    civilian: Match[int],
) -> None:
    preset = (
        werewolf.result,
        priesthood.result,
        civilian.result,
    )
    if sum(preset) != total.result:
        await finish("总人数与职业数量不匹配")

    data = PresetData.load()
    if werewolf.result > len(data.werewolf_priority):
        await finish("狼人数量超出优先级列表长度，请先设置足够多的狼人预设")
    if priesthood.result > len(data.priesthood_proirity):
        await finish("神职数量超出优先级列表长度，请先设置足够多的神职预设")

    data.role_preset[total.result] = preset
    data.save()
    await finish(
        f"设置成功\n{total.result} 人: "
        f"狼人x{werewolf.result}, 神职x{priesthood.result}, 平民x{civilian.result}"
    )


@edit_preset.assign("del")
async def delete_role(total: Match[int]) -> None:
    data = PresetData.load()
    if total.result not in data.role_preset:
        await finish("未找到对应预设")
    del data.role_preset[total.result]
    data.save()
    await finish("删除成功")


@edit_preset.assign("werewolf")
async def handle_werewolf_input_roles(roles: Match[Any], state: T_State) -> None:
    if roles.available:
        state["roles"] = UniMessage(roles.result).extract_plain_text().split(" ")
        return

    result = await waiter.prompt(
        "请发送狼人优先级列表，以空格隔开\n发送 “取消” 取消操作"
    )
    if result is None:
        await finish("发送超时，已自动取消")

    text = result.extract_plain_text()
    if text == "取消":
        await finish("已取消操作")

    state["roles"] = text.split(" ")


@edit_preset.assign("werewolf")
async def assign_werewolf(state: T_State) -> None:
    roles: list[str] = state["roles"]
    result: list[Role] = []

    for role in roles:
        match role:
            case "狼人" | "狼":
                result.append(Role.WEREWOLF)
            case "狼王":
                result.append(Role.WOLFKING)
            case x:
                await finish(f"未知职业: {x}")

    data = PresetData.load()
    min_length = max(w for w, _, _ in data.role_preset.values())
    if len(result) < min_length:
        await finish(f"狼人数量不足，至少需要 {min_length} 个狼人")

    data.werewolf_priority = result
    data.save()
    await finish(f"设置成功: {display_roles(result)}")


@edit_preset.assign("priesthood")
async def handle_priesthood_input_roles(roles: Match[Any], state: T_State) -> None:
    if roles.available:
        state["roles"] = UniMessage(roles.result).extract_plain_text().split(" ")
        return

    result = await waiter.prompt(
        "请发送神职优先级列表，以空格隔开\n发送 “取消” 取消操作"
    )
    if result is None:
        await finish("发送超时，已自动取消")

    text = result.extract_plain_text()
    if text == "取消":
        await finish("已取消操作")

    state["roles"] = text.split(" ")


@edit_preset.assign("priesthood")
async def assign_priesthood(state: T_State) -> None:
    roles: list[str] = state["roles"]
    result: list[Role] = []

    for role in roles:
        match role:
            case "预言家" | "预言" | "预":
                result.append(Role.PROPHET)
            case "女巫" | "巫":
                result.append(Role.WITCH)
            case "猎人" | "猎":
                result.append(Role.HUNTER)
            case "守卫":
                result.append(Role.GUARD)
            case "白痴":
                result.append(Role.IDIOT)
            case x:
                await finish(f"未知职业: {x}")

    data = PresetData.load()
    min_length = max(p for _, p, _ in data.role_preset.values())
    if len(result) < min_length:
        await finish(f"神职数量不足，至少需要 {min_length} 个神职")

    data.priesthood_proirity = result
    data.save()
    await finish(f"设置成功: {display_roles(result)}")


@edit_preset.assign("jester")
async def assign_jester(probability: Match[float]) -> None:
    if not probability.available:
        result = await waiter.prompt_until(
            message="请发送小丑概率，范围 0-100\n发送 “取消” 取消操作",
            checker=lambda m: (s := m.extract_plain_text()).isdigit() or s == "取消",
            retry_prompt="输入错误，请重新输入一个正确的数字。\n剩余次数：{count}",
        )
        if result is None:
            await finish("发送超时，已自动取消")
        text = result.extract_plain_text()
        if text == "取消":
            await finish("已取消操作")
        probability.result = float(text)

    if not 0 <= probability.result <= 100:
        await finish("输入错误，概率应在 0 到 100 之间")

    data = PresetData.load()
    data.jester_probability = probability.result / 100
    data.save()
    await finish(f"设置成功: 小丑概率 {probability.result:.1f}%")


@edit_preset.assign("reset")
async def reset_preset() -> None:
    PresetData().save()
    await finish("已重置为默认预设")


@edit_preset.handle()
async def handle_default() -> None:
    data = PresetData.load()

    lines = ["当前游戏预设:\n"]
    lines.extend(
        f"{total} 人: 狼人x{w}, 神职x{p}, 平民x{c}"
        for total, (w, p, c) in data.role_preset.items()
    )
    lines.append(
        f"\n狼人优先级: {display_roles(data.werewolf_priority)}"
        f"\n神职优先级: {display_roles(data.priesthood_proirity)}"
        f"\n小丑概率: {data.jester_probability:.0%}"
    )

    await finish("\n".join(lines))
