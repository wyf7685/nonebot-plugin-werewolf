# ruff: noqa: S101

import pytest


@pytest.mark.usefixtures("app")
def test_check_index() -> None:
    from nonebot_plugin_werewolf.utils import check_index

    assert check_index("1", 5) == 1
    assert check_index("5", 5) == 5
    assert check_index("0", 5) is None
    assert check_index("6", 5) is None
    assert check_index("abc", 5) is None
    assert check_index("", 5) is None
    assert check_index(" ", 5) is None
