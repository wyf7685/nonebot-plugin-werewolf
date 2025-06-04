import json
import warnings
from pathlib import Path
from typing import Any, ClassVar, Final, Literal
from typing_extensions import Self

import nonebot
from nonebot.compat import model_dump, model_validator, type_validate_json
from nonebot_plugin_localstore import get_plugin_data_file
from pydantic import BaseModel, Field

from .constant import (
    DEFAULT_PRIESTHOOD_PRIORITY,
    DEFAULT_ROLE_PRESET,
    DEFAULT_WEREWOLF_PRIORITY,
)
from .models import Role


class ConfigFile(BaseModel):
    _file_: ClassVar[Path]
    _cache_: ClassVar[Self | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init_subclass__(**kwargs)
        if not cls._file_.exists():
            cls().save()

    @classmethod
    def load(cls) -> Self:
        return type_validate_json(cls, cls._file_.read_text())

    @classmethod
    def get(cls, *, use_cache: bool = True) -> Self:
        if cls._cache_ is None or not use_cache:
            cls._cache_ = cls.load()
        return cls._cache_

    def save(self) -> None:
        self._file_.write_text(json.dumps(model_dump(self)))
        type(self)._cache_ = self


class PresetData(ConfigFile):
    _file_: ClassVar[Path] = get_plugin_data_file("preset.json")

    role_preset: dict[int, tuple[int, int, int]] = DEFAULT_ROLE_PRESET.copy()
    werewolf_priority: list[Role] = DEFAULT_WEREWOLF_PRIORITY.copy()
    priesthood_proirity: list[Role] = DEFAULT_PRIESTHOOD_PRIORITY.copy()
    jester_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class _Timeout(BaseModel):
    prepare: int = Field(default=5 * 60, ge=5 * 60)
    speak: int = Field(default=60, ge=60)
    group_speak: int = Field(default=120, ge=120)
    interact: int = Field(default=60, ge=60)
    vote: int = Field(default=60, ge=60)
    werewolf: int = Field(default=120, ge=120)

    @property
    def speak_timeout_prompt(self) -> str:
        return f"限时{self.speak / 60:.1f}分钟, 发送 “{stop_command_prompt}” 结束发言"

    @property
    def group_speak_timeout_prompt(self) -> str:
        return (
            f"限时{self.group_speak / 60:.1f}分钟, "
            f"全员发送 “{stop_command_prompt}” 结束发言"
        )


class GameBehavior(ConfigFile):
    _file_: ClassVar[Path] = get_plugin_data_file("behavior.json")

    show_roles_list_on_start: bool = False
    speak_in_turn: bool = False
    dead_channel_rate_limit: int = 8  # per minute
    werewolf_multi_select: bool = False
    timeout: Final[_Timeout] = _Timeout()


class RequireAtConfig(BaseModel):
    start: bool = True
    terminate: bool = True


class MatcherPriorityConfig(BaseModel):
    start: int = 1
    terminate: int = 1
    preset: int = 1
    behavior: int = 1
    in_game: int = 10
    stop: int = 9

    @model_validator(mode="after")
    @classmethod
    def _validate(cls, model: Self) -> Self:
        if model.in_game <= model.stop:
            model.in_game = model.stop + 1
            warnings.warn(
                "in_game 的优先级必须低于 stop，已自动调整为 stop + 1",
                stacklevel=2,
            )
        return model


class PluginConfig(BaseModel):
    enable_poke: bool = True
    enable_button: bool = False
    stop_command: str | set[str] = "stop"
    require_at: bool | RequireAtConfig = True
    matcher_priority: MatcherPriorityConfig = MatcherPriorityConfig()
    use_cmd_start: bool | None = None

    def get_stop_command(self) -> list[str]:
        return (
            [self.stop_command]
            if isinstance(self.stop_command, str)
            else sorted(self.stop_command, key=len)
        )

    def get_require_at(self, cmd: Literal["start", "terminate"]) -> bool:
        if isinstance(self.require_at, bool):
            return self.require_at
        return getattr(self.require_at, cmd)


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


config = nonebot.get_plugin_config(Config).werewolf
nonebot.logger.debug(f"加载插件配置: {config}")

stop_command_prompt = (
    next(iter(sorted(nonebot.get_driver().config.command_start, key=len)), "")
    + config.get_stop_command()[0]
)
