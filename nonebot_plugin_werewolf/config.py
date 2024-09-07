from typing import Literal, overload

from nonebot import get_plugin_config, logger
from nonebot.compat import PYDANTIC_V2
from pydantic import BaseModel, Field

from .constant import Role, priesthood_proirity, role_preset, werewolf_priority

if PYDANTIC_V2:
    from pydantic import model_validator as model_validator
else:
    from pydantic import root_validator

    @overload
    def model_validator(*, mode: Literal["before"]): ...

    @overload
    def model_validator(*, mode: Literal["after"]): ...

    def model_validator(*, mode: Literal["before", "after"]):
        return root_validator(
            pre=mode == "before",  # pyright:ignore[reportArgumentType]
            allow_reuse=True,
        )


class PluginConfig(BaseModel):
    enable_poke: bool = True
    role_preset: list[tuple[int, int, int, int]] | None = None
    werewolf_priority: list[Role] = Field(default_factory=werewolf_priority.copy)
    priesthood_proirity: list[Role] = Field(default_factory=priesthood_proirity.copy)

    @model_validator(mode="after")
    def _validate(self):
        if self.role_preset is not None:
            for preset in self.role_preset:
                if preset[0] != sum(preset[1:]):
                    raise RuntimeError(
                        "配置项 `role_preset` 错误: "
                        f"预设总人数为 {preset[0]}, 实际总人数为 {sum(preset[1:])}"
                    )
            role_preset.update({i[0]: i[1:] for i in self.role_preset})
            logger.debug(f"覆写配置 role_preset: {role_preset}")

        if (priority := self.werewolf_priority) is not None:
            min_length = max(i[0] for i in role_preset.values())
            if len(priority) < min_length:
                raise RuntimeError(
                    f"配置项 `werewolf_priority` 错误: 应至少为 {min_length} 项"
                )
            if priority != werewolf_priority:
                werewolf_priority[:] = priority
                logger.debug(f"覆写配置 werewolf_priority: {werewolf_priority}")

        if (priority := self.priesthood_proirity) is not None:
            min_length = max(i[1] for i in role_preset.values())
            if len(priority) < min_length:
                raise RuntimeError(
                    f"配置项 `priesthood_proirity` 错误: 应至少为 {min_length} 项"
                )
            if priority != priesthood_proirity:
                priesthood_proirity[:] = priority
                logger.debug(f"覆写配置 priesthood_proirity: {priesthood_proirity}")

        return self


class Config(BaseModel):
    werewolf: PluginConfig = PluginConfig()


config = get_plugin_config(Config).werewolf
