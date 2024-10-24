from typing import Any, Literal, overload

from nonebot import get_plugin_config, logger
from nonebot.compat import PYDANTIC_V2
from pydantic import BaseModel, Field
from typing_extensions import Self

from .constant import (
    RolePresetConfig,
    RolePresetDict,
    default_priesthood_proirity,
    default_role_preset,
    default_werewolf_priority,
)
from .models import Role

if PYDANTIC_V2:
    from pydantic import model_validator as model_validator
else:
    from pydantic import root_validator

    @overload
    def model_validator(*, mode: Literal["before"]) -> Any: ...  # noqa: ANN401

    @overload
    def model_validator(*, mode: Literal["after"]) -> Any: ...  # noqa: ANN401

    def model_validator(*, mode: Literal["before", "after"]) -> Any:
        return root_validator(
            pre=mode == "before",  # pyright: ignore[reportArgumentType]
            allow_reuse=True,
        )


class PluginConfig(BaseModel):
    enable_poke: bool = True
    role_preset: RolePresetConfig = default_role_preset.copy()
    werewolf_priority: list[Role] = default_werewolf_priority.copy()
    priesthood_proirity: list[Role] = default_priesthood_proirity.copy()
    joker_probability: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if isinstance(self.role_preset, list):
            for (total, *presets) in self.role_preset:
                if total != sum(presets):
                    raise ValueError(
                        "配置项 `role_preset` 错误: "
                        f"预设总人数为 {total}, 实际总人数为 {sum(presets)} "
                        f"({', '.join(map(str, presets))})"
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

    def get_role_preset(self) -> RolePresetDict:
        if isinstance(self.role_preset, list):
            self.role_preset = {i[0]: i[1:] for i in self.role_preset}
        return self.role_preset


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


config = get_plugin_config(Config).werewolf
logger.debug(f"加载插件配置: {config}")
