from ...config import config
from .chronocat_poke import chronocat_poke_enabled
from .ob11_poke import ob11_poke_enabled

checks = [chronocat_poke_enabled, ob11_poke_enabled]


def poke_enabled() -> bool:
    return config.enable_poke and any(check() for check in checks)
