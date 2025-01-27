import json
from pathlib import Path
from typing import Any, ClassVar
from typing_extensions import Self

import nonebot
from nonebot.compat import model_dump, type_validate_json
from nonebot_plugin_localstore import get_plugin_data_file
from pydantic import BaseModel, Field

from .constant import (
    DEFAULT_PRIESTHOOD_PRIORITY,
    DEFAULT_ROLE_PRESET,
    DEFAULT_WEREWOLF_PRIORITY,
)
from .models import Role


class ConfigFile(BaseModel):
    FILE: ClassVar[Path]

    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init_subclass__(**kwargs)
        if not cls.FILE.exists():
            cls().save()

    @classmethod
    def load(cls) -> Self:
        return type_validate_json(cls, cls.FILE.read_text())

    def save(self) -> None:
        self.FILE.write_text(json.dumps(model_dump(self)))


class PresetData(ConfigFile):
    FILE: ClassVar[Path] = get_plugin_data_file("preset.json")

    role_preset: dict[int, tuple[int, int, int]] = DEFAULT_ROLE_PRESET.copy()
    werewolf_priority: list[Role] = DEFAULT_WEREWOLF_PRIORITY.copy()
    priesthood_proirity: list[Role] = DEFAULT_PRIESTHOOD_PRIORITY.copy()
    jester_probability: float = Field(default=0.0, ge=0.0, le=1.0)


# class GameBehavior(ConfigFile):
#     FILE: ClassVar[Path] = get_plugin_data_file("behavior.json")


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
