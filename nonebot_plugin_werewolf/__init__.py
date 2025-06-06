from importlib.metadata import version

from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_uninfo")
require("nonebot_plugin_waiter")

from . import matchers as matchers
from . import players as players
from .config import Config

try:
    __version__ = version("nonebot-plugin-werewolf")
except Exception:
    __version__ = None

__plugin_meta__ = PluginMetadata(
    name="狼人杀",
    description="适用于 Nonebot2 的狼人杀插件",
    usage="@Bot /狼人杀",
    type="application",
    homepage="https://github.com/wyf7685/nonebot-plugin-werewolf",
    config=Config,
    supported_adapters=inherit_supported_adapters(
        "nonebot_plugin_alconna",
        "nonebot_plugin_uninfo",
        "nonebot_plugin_waiter",
    ),
    extra={
        "author": "wyf7685",
        "version": __version__,
        "bug-tracker": "https://github.com/wyf7685/nonebot-plugin-werewolf/issues",
    },
)
