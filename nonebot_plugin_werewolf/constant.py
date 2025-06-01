from .models import GameStatus, KillReason, Role, RoleGroup

STOP_COMMAND = "{{stop}}"


ROLE_NAME_CONV: dict[Role | RoleGroup, str] = {
    Role.WEREWOLF: "狼人",
    Role.WOLFKING: "狼王",
    Role.PROPHET: "预言家",
    Role.WITCH: "女巫",
    Role.HUNTER: "猎人",
    Role.GUARD: "守卫",
    Role.IDIOT: "白痴",
    Role.JESTER: "小丑",
    Role.CIVILIAN: "平民",
    RoleGroup.WEREWOLF: "狼人",
    RoleGroup.GOODGUY: "好人",
    RoleGroup.OTHERS: "其他",
}

ROLE_EMOJI: dict[Role, str] = {
    Role.WEREWOLF: "🐺",
    Role.WOLFKING: "🐺👑",
    Role.PROPHET: "🔮",
    Role.WITCH: "🧙‍♀️",
    Role.HUNTER: "🕵️",
    Role.GUARD: "🛡️",
    Role.IDIOT: "👨🏻‍🦲",
    Role.JESTER: "🤡",
    Role.CIVILIAN: "👨🏻‍🌾",
}

GAME_STATUS_CONV: dict[GameStatus, str] = {
    GameStatus.GOODGUY: "好人",
    GameStatus.WEREWOLF: "狼人",
    GameStatus.JESTER: "小丑",
}

REPORT_TEXT: dict[KillReason, tuple[str, str]] = {
    KillReason.WEREWOLF: ("🔪", "刀了"),
    KillReason.POISON: ("🧪", "毒死"),
    KillReason.SHOOT: ("🔫", "射杀"),
    KillReason.VOTE: ("🗳️", "票出"),
}

DEFAULT_ROLE_PRESET: dict[int, tuple[int, int, int]] = {
    # 总人数: (狼, 神, 民)
    6: (1, 2, 3),
    7: (2, 2, 3),
    8: (2, 3, 3),
    9: (2, 4, 3),
    10: (3, 4, 3),
    11: (3, 5, 3),
    12: (4, 5, 3),
}
DEFAULT_WEREWOLF_PRIORITY: list[Role] = [
    Role.WEREWOLF,
    Role.WEREWOLF,
    Role.WOLFKING,
    Role.WEREWOLF,
]
DEFAULT_PRIESTHOOD_PRIORITY: list[Role] = [
    Role.WITCH,
    Role.PROPHET,
    Role.HUNTER,
    Role.GUARD,
    Role.IDIOT,
]
