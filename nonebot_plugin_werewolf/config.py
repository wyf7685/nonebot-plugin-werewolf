from typing import Literal, overload

from nonebot import get_plugin_config, logger
from nonebot.compat import PYDANTIC_V2
from pydantic import BaseModel, Field
from typing_extensions import Self

from .constant import (
    Role,
    default_priesthood_proirity,
    default_role_preset,
    default_werewolf_priority,
)

if PYDANTIC_V2:
    from pydantic import model_validator as model_validator
else:
    from pydantic import root_validator

    @overload
    def model_validator(*, mode: Literal["before"]): ...  # noqa: ANN201

    @overload
    def model_validator(*, mode: Literal["after"]): ...  # noqa: ANN201

    def model_validator(*, mode: Literal["before", "after"]):
        return root_validator(
            pre=mode == "before",  # pyright: ignore[reportArgumentType]
            allow_reuse=True,
        )


class PluginConfig(BaseModel):
    enable_poke: bool = Field(default=True)
    role_preset: list[tuple[int, int, int, int]] | dict[int, tuple[int, int, int]] = (
        Field(default_factory=default_role_preset.copy)
    )
    werewolf_priority: list[Role] = Field(
        default_factory=default_werewolf_priority.copy
    )
    priesthood_proirity: list[Role] = Field(
        default_factory=default_priesthood_proirity.copy
    )
    joker_probability: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if isinstance(self.role_preset, list):
            for preset in self.role_preset:
                if preset[0] != sum(preset[1:]):
                    raise ValueError(
                        "配置项 `role_preset` 错误: "
                        f"预设总人数为 {preset[0]}, 实际总人数为 {sum(preset[1:])} "
                        f"({', '.join(map(str, preset[1:]))})"
                    )
            self.role_preset = default_role_preset | {
                i[0]: i[1:] for i in self.role_preset
            }
            logger.debug(f"覆写配置 role_preset: {self.role_preset}")

        min_length = max(i[0] for i in self.role_preset.values())
        if len(self.werewolf_priority) < min_length:
            raise ValueError(
                f"配置项 `werewolf_priority` 错误: 应至少为 {min_length} 项"
            )

        min_length = max(i[1] for i in self.role_preset.values())
        if len(self.priesthood_proirity) < min_length:
            raise ValueError(
                f"配置项 `priesthood_proirity` 错误: 应至少为 {min_length} 项"
            )

        return self

    def get_role_preset(self) -> dict[int, tuple[int, int, int]]:
        if isinstance(self.role_preset, list):
            self.role_preset = {i[0]: i[1:] for i in self.role_preset}
        return self.role_preset


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


config = get_plugin_config(Config).werewolf
logger.debug(f"加载插件配置: {config}")
