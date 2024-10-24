import nonebot

from .models import Role, RoleGroup

COMMAND_START = next(
    iter(sorted(nonebot.get_driver().config.command_start, key=len)), ""
)
STOP_COMMAND_PROMPT = f"{COMMAND_START}stop"
STOP_COMMAND = "{{stop}}"


role_name_conv: dict[Role | RoleGroup, str] = {
    Role.Werewolf: "狼人",
    Role.WolfKing: "狼王",
    Role.Prophet: "预言家",
    Role.Witch: "女巫",
    Role.Hunter: "猎人",
    Role.Guard: "守卫",
    Role.Idiot: "白痴",
    Role.Joker: "小丑",
    Role.Civilian: "平民",
    RoleGroup.Werewolf: "狼人",
    RoleGroup.GoodGuy: "好人",
    RoleGroup.Others: "其他",
}

role_emoji: dict[Role, str] = {
    Role.Werewolf: "🐺",
    Role.WolfKing: "🐺👑",
    Role.Prophet: "🔮",
    Role.Witch: "🧙‍♀️",
    Role.Hunter: "🕵️",
    Role.Guard: "🛡️",
    Role.Idiot: "👨🏻‍🦲",
    Role.Joker: "🤡",
    Role.Civilian: "👨🏻‍🌾",
}

RolePresetDict = dict[int, tuple[int, int, int]]
RolePresetConfig = RolePresetDict | list[tuple[int, int, int, int]]

default_role_preset: RolePresetDict = {
    # 总人数: (狼, 神, 民)
    6: (1, 2, 3),
    7: (2, 2, 3),
    8: (2, 3, 3),
    9: (2, 4, 3),
    10: (3, 4, 3),
    11: (3, 5, 3),
    12: (4, 5, 3),
}

default_werewolf_priority: list[Role] = [
    Role.Werewolf,
    Role.Werewolf,
    Role.WolfKing,
    Role.Werewolf,
]
default_priesthood_proirity: list[Role] = [
    Role.Witch,
    Role.Prophet,
    Role.Hunter,
    Role.Guard,
    Role.Idiot,
]
