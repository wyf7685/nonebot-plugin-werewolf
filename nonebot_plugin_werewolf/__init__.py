from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_userinfo")
require("nonebot_plugin_waiter")

from . import matchers as matchers
from .config import Config

__version__ = "1.0.1"
__plugin_meta__ = PluginMetadata(
    name="狼人杀",
    description="适用于 Nonebot2 的狼人杀插件",
    usage="@Bot /狼人杀",
    type="application",
    homepage="https://github.com/wyf7685/nonebot-plugin-werewolf",
    config=Config,
    supported_adapters=inherit_supported_adapters(
        "nonebot_plugin_alconna",
        "nonebot_plugin_userinfo",
        "nonebot_plugin_waiter",
    ),
    extra={"author": "wyf7685"},
)
