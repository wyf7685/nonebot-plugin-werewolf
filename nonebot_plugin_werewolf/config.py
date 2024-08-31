from nonebot import get_plugin_config
from pydantic import BaseModel


class PluginConfig(BaseModel):
    enable_poke: bool = True
    override_preset: list[tuple[int, int, int, int]] | None = None


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


config = get_plugin_config(Config).werewolf
