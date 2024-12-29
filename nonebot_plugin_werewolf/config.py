import json
from typing_extensions import Self

import nonebot
from nonebot.compat import model_dump, type_validate_json
from nonebot_plugin_localstore import get_plugin_data_file
from pydantic import BaseModel, Field

from .constant import (
    default_priesthood_proirity,
    default_role_preset,
    default_werewolf_priority,
)
from .models import Role


class PresetData(BaseModel):
    role_preset: dict[int, tuple[int, int, int]] = default_role_preset.copy()
    werewolf_priority: list[Role] = default_werewolf_priority.copy()
    priesthood_proirity: list[Role] = default_priesthood_proirity.copy()
    joker_probability: float = Field(default=0.0, ge=0.0, le=1.0)

    @classmethod
    def load(cls) -> Self:
        return type_validate_json(cls, PRESET_DATA_FILE.read_text())

    def save(self) -> None:
        PRESET_DATA_FILE.write_text(json.dumps(model_dump(self)))


class PluginConfig(BaseModel):
    enable_poke: bool = True
    enable_button: bool = False


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


PRESET_DATA_FILE = get_plugin_data_file("preset.json")
if not PRESET_DATA_FILE.exists():
    PresetData().save()

config = nonebot.get_plugin_config(Config).werewolf
nonebot.logger.debug(f"加载插件配置: {config}")
