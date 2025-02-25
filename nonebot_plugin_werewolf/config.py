import json
from pathlib import Path
from typing import Any, ClassVar, Final
from typing_extensions import Self

import nonebot
from nonebot.compat import model_dump, type_validate_json
from nonebot_plugin_localstore import get_plugin_data_file
from pydantic import BaseModel, Field

from .constant import (
    DEFAULT_PRIESTHOOD_PRIORITY,
    DEFAULT_ROLE_PRESET,
    DEFAULT_WEREWOLF_PRIORITY,
    stop_command_prompt,
)
from .models import Role


class ConfigFile(BaseModel):
    FILE: ClassVar[Path]
    _cache: ClassVar[Self | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init_subclass__(**kwargs)
        if not cls.FILE.exists():
            cls().save()

    @classmethod
    def load(cls) -> Self:
        return type_validate_json(cls, cls.FILE.read_text())

    @classmethod
    def get(cls, *, use_cache: bool = True) -> Self:
        if cls._cache is None or not use_cache:
            cls._cache = cls.load()
        return cls._cache

    def save(self) -> None:
        self.FILE.write_text(json.dumps(model_dump(self)))
        type(self)._cache = self  # noqa: SLF001


class PresetData(ConfigFile):
    FILE: ClassVar[Path] = get_plugin_data_file("preset.json")

    role_preset: dict[int, tuple[int, int, int]] = DEFAULT_ROLE_PRESET.copy()
    werewolf_priority: list[Role] = DEFAULT_WEREWOLF_PRIORITY.copy()
    priesthood_proirity: list[Role] = DEFAULT_PRIESTHOOD_PRIORITY.copy()
    jester_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class GameBehavior(ConfigFile):
    FILE: ClassVar[Path] = get_plugin_data_file("behavior.json")

    show_roles_list_on_start: bool = False
    speak_in_turn: bool = False
    dead_channel_rate_limit: int = 8  # per minute
    werewolf_multi_select: bool = False

    class _Timeout(BaseModel):
        prepare: int = Field(default=5 * 60, ge=5 * 60)
        speak: int = Field(default=60, ge=60)
        group_speak: int = Field(default=120, ge=120)
        interact: int = Field(default=60, ge=60)
        vote: int = Field(default=60, ge=60)
        werewolf: int = Field(default=120, ge=120)

        @property
        def speak_timeout_prompt(self) -> str:
            return (
                f"限时{self.speak / 60:.1f}分钟, "
                f"发送 “{stop_command_prompt()}” 结束发言"
            )

        @property
        def group_speak_timeout_prompt(self) -> str:
            return (
                f"限时{self.group_speak / 60:.1f}分钟, "
                f"全员发送 “{stop_command_prompt()}” 结束发言"
            )

    timeout: Final[_Timeout] = _Timeout()


class PluginConfig(BaseModel):
    enable_poke: bool = True
    enable_button: bool = False
    stop_command: str | set[str] = "stop"

    def get_stop_command(self) -> list[str]:
        return (
            [self.stop_command]
            if isinstance(self.stop_command, str)
            else sorted(self.stop_command, key=len)
        )


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


config = nonebot.get_plugin_config(Config).werewolf
nonebot.logger.debug(f"加载插件配置: {config}")
