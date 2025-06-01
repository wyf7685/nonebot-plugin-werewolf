from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_uninfo")
require("nonebot_plugin_waiter")

from . import matchers as matchers
from . import players as players
from .config import Config

__version__ = "1.1.12"
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
        "Author": "wyf7685",
        "Version": __version__,
        "Bug Tracker": "https://github.com/wyf7685/nonebot-plugin-werewolf/issues",
    },
)
