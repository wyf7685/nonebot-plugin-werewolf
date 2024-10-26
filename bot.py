import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OB11Adapter
from nonebot.adapters.satori import Adapter as SatoriAdapter
from nonebot.adapters.telegram import Adapter as TegeragmAdapter


def clean_pycache() -> None:
    from pathlib import Path
    from queue import Queue
    from shutil import rmtree

    que = Queue[Path]()
    (put := que.put)(Path())
    while not que.empty():
        for p in filter(Path.is_dir, que.get().iterdir()):
            (rmtree if p.name == "__pycache__" else put)(p)


nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(OB11Adapter)
driver.register_adapter(SatoriAdapter)
driver.register_adapter(TegeragmAdapter)
nonebot.load_plugin("nonebot_plugin_werewolf")

if __name__ == "__main__":
    try:
        nonebot.run()
    finally:
        clean_pycache()
