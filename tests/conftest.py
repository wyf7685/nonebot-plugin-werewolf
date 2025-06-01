import os
from collections.abc import AsyncGenerator

import nonebot
import pytest
from nonebot.adapters import onebot
from nonebug import NONEBOT_INIT_KWARGS, App

superuser = 7685000


def pytest_configure(config: pytest.Config) -> None:
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi",
        "log_level": "TRACE",
        "host": "127.0.0.1",
        "port": "8080",
        "superusers": [str(superuser)],
        "alembic_startup_check": False,
    }
    os.environ["PLUGIN_ALCONNA_TESTENV"] = "1"


@pytest.fixture
async def app() -> AsyncGenerator[App]:
    # 加载插件
    nonebot.require("nonebot_plugin_werewolf")

    yield App()  # noqa: PT022


@pytest.fixture(scope="session", autouse=True)
def _load_bot() -> None:
    # 加载适配器
    driver = nonebot.get_driver()
    driver.register_adapter(onebot.v11.Adapter)
