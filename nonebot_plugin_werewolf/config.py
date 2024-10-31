import json

import nonebot
from nonebot.compat import model_dump, type_validate_json
from nonebot_plugin_localstore import get_plugin_data_file
from pydantic import BaseModel, Field
from typing_extensions import Self

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
        return type_validate_json(cls, preset_data_file.read_text())

    def save(self) -> None:
        preset_data_file.write_text(json.dumps(model_dump(self)))


class PluginConfig(BaseModel):
    enable_poke: bool = True
    enable_button: bool = False


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


preset_data_file = get_plugin_data_file("preset.json")
if not preset_data_file.exists():
    PresetData().save()

config = nonebot.get_plugin_config(Config).werewolf
nonebot.logger.debug(f"加载插件配置: {config}")
