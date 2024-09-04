from nonebot import get_plugin_config
from pydantic import BaseModel

from .constant import Role


class PluginConfig(BaseModel):
    enable_poke: bool = True
    role_preset: list[tuple[int, int, int, int]] | None = None
    werewolf_priority: list[Role] | None = None
    priesthood_proirity: list[Role] | None = None


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


config = get_plugin_config(Config).werewolf
