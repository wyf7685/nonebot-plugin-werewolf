from nonebot import get_plugin_config
from pydantic import BaseModel, Field

from .constant import Role


class PluginConfig(BaseModel):
    enable_poke: bool = True
    role_preset: list[tuple[int, int, int, int]] | None = None
    werewolf_priority: list[Role] | None = None
    priesthood_proirity: list[Role] | None = None
    joker_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


config = get_plugin_config(Config).werewolf
