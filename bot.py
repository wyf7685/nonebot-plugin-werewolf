import shutil
from pathlib import Path

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OB11Adapter


def clean_pycache(path: Path = Path()):
    for p in path.iterdir():
        if not p.is_dir():
            continue
        if p.name == "__pycache__":
            shutil.rmtree(p)
        else:
            clean_pycache(p)


nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(OB11Adapter)
nonebot.load_plugin("nonebot_plugin_werewolf")

if __name__ == "__main__":
    nonebot.run()
    clean_pycache()
