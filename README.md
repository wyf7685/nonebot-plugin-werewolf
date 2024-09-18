<div align="center">
  <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/wyf7685/wyf7685/main/assets/NoneBotPlugin.svg" width="300" alt="logo">
  </a>
</div>

<div align="center">

# nonebot-plugin-werewolf

_✨ 简单的狼人杀插件 ✨_

[![license](https://img.shields.io/github/license/wyf7685/nonebot-plugin-werewolf.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-werewolf?logo=python&logoColor=edb641)](https://pypi.python.org/pypi/nonebot-plugin-werewolf)
[![python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=edb641)](https://www.python.org/)

[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![isort](https://img.shields.io/badge/%20imports-isort-%231674b1)](https://pycqa.github.io/isort/)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pyright](https://img.shields.io/badge/types-pyright-797952.svg?logo=python&logoColor=edb641)](https://github.com/Microsoft/pyright)

[![wakatime](https://wakatime.com/badge/user/b097681b-c224-44ec-8e04-e1cf71744655/project/70a7f68d-5625-4989-9476-be6877408332.svg)](https://wakatime.com/badge/user/b097681b-c224-44ec-8e04-e1cf71744655/project/70a7f68d-5625-4989-9476-be6877408332)
[![pre-commit](https://results.pre-commit.ci/badge/github/wyf7685/nonebot-plugin-werewolf/master.svg)](https://results.pre-commit.ci/latest/github/wyf7685/nonebot-plugin-werewolf/master)
[![pyright](https://github.com/wyf7685/nonebot-plugin-werewolf/actions/workflows/pyright.yml/badge.svg?branch=master&event=push)](https://github.com/wyf7685/nonebot-plugin-werewolf/actions/workflows/pyright.yml)
[![publish](https://github.com/wyf7685/nonebot-plugin-werewolf/actions/workflows/pypi-publish.yml/badge.svg)](https://github.com/wyf7685/nonebot-plugin-werewolf/actions/workflows/pypi-publish.yml)

[![NoneBot Registry](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin%2Fnonebot-plugin-werewolf)](https://registry.nonebot.dev/plugin/nonebot-plugin-werewolf:nonebot_plugin_werewolf)
[![Supported Adapters](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin-adapters%2Fnonebot-plugin-werewolf)](https://registry.nonebot.dev/plugin/nonebot-plugin-werewolf:nonebot_plugin_werewolf)

</div>

## 📖 介绍

和朋友们来一场紧张刺激的狼人杀游戏

## 💿 安装

> [!note]
> 
> 请确保 NoneBot2 使用的 Python 解释器版本 >=3.10

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-werewolf

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-werewolf

</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-werewolf

</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-werewolf

</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-werewolf

</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_werewolf"]

</details>

## ⚙️ 配置

在 nonebot2 项目的 `.env` 文件中添加如下配置

|             配置项              | 必填 | 默认值 |                             说明                              |
| :-----------------------------: | :--: | :----: | :-----------------------------------------------------------: |
|     `werewolf__enable_poke`     |  否  | `True` | 是否使用戳一戳简化操作流程<br/>仅在 `OneBot V11` 适配器下生效 |
|     `werewolf__role_preset`     |  否  |   -    |                    覆写插件内置的职业预设                     |
|  `werewolf__werewolf_priority`  |  否  |   -    |                     自定义狼人职业优先级                      |
| `werewolf__priesthood_proirity` |  否  |   -    |                     自定义神职职业优先级                      |
|  `werewolf__joker_probability`  |  否  | `0.0`  |              小丑职业替换平民的概率, 范围`[0,1]`              |

`werewolf__role_preset`, `werewolf__werewolf_priority`, `werewolf__priesthood_proirity` 的配置格式请参考 [`游戏内容`](#游戏内容) 部分

## 🎉 使用

> [!note]
>
> 插件通过群聊+私聊进行游戏交互
>
> 使用前请确保机器人有权限发起相应对话。

<details>
<summary>举例</summary>

~~众所周知，~~ QQ 官方机器人对主动消息有次数限制 ([参考](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html))

因此，本插件~~可能~~无法在 `adapter-qq` 下正常运行

而对于野生机器人，现有协议端通常不支持或不建议使用临时私聊消息。

在使用本插件前，应当确保机器人可以正常向玩家发送私聊消息。

</details>

### 指令表

|        指令         |    权限    | 需要@ | 范围 |                说明                 |
| :-----------------: | :--------: | :---: | :--: | :---------------------------------: |
| `werewolf`/`狼人杀` |    群员    |  是   | 群聊 |       发起游戏 (进入准备阶段)       |
|     `开始游戏`      | 游戏发起者 |  是   | 群聊 |   _[准备阶段]_ 游戏发起者开始游戏   |
|     `结束游戏`      | 游戏发起者 |  是   | 群聊 |   _[准备阶段]_ 游戏发起者结束游戏   |
|     `当前玩家`      |    群员    |  是   | 群聊 | _[准备阶段]_ 列出参与游戏的玩家列表 |
|     `加入游戏`      |    群员    |  是   | 群聊 |      _[准备阶段]_ 玩家加入游戏      |
|     `退出游戏`      |    群员    |  是   | 群聊 |      _[准备阶段]_ 玩家退出游戏      |

_其他交互参考游戏内提示_

对于 `OneBot V11` 适配器, 启用配置项 `werewolf__enable_poke` 后, 可以使用戳一戳代替 _准备阶段_ 的 `加入游戏` 操作 和 游戏内的 `/stop` 命令

### 游戏内容

> [!note]
>
> 插件的游戏规则参考了网络上的相关资料
>
> 如有疑问欢迎提出

插件中保存了一份 [职业预设](./nonebot_plugin_werewolf/constant.py), 内容如下

| 总人数 | 狼人 | 神职 | 平民 |
| ------ | ---- | ---- | ---- |
| 6      | 1    | 2    | 3    |
| 7      | 2    | 2    | 3    |
| 8      | 2    | 3    | 3    |
| 9      | 2    | 4    | 3    |
| 10     | 3    | 4    | 3    |
| 11     | 3    | 5    | 3    |
| 12     | 4    | 5    | 3    |

职业预设可以通过配置项 `werewolf__role_preset` 修改

<details>
<summary>示例</summary>

配置项 `werewolf__role_preset`

```env
werewolf__role_preset='
[
    [6, 1, 3, 2],
    [7, 2, 3, 2]
]
'
```

上述配置中，`[6, 1, 3, 2]` 表示当总人数为 6 时，狼人、神职、平民的数量分别为 1、3、2

</details>
<br/>

对于`狼人`和`神职`的职业分配，默认有如下优先级:

- `狼人`: `狼人`, `狼人`, `狼王`, `狼人`
- `神职`: `女巫`, `预言家`, `猎人`, `守卫`, `白痴`

职业分配优先级可以通过配置项 `werewolf__werewolf_priority` 和 `werewolf__priesthood_proirity` 修改

<details>
<summary>示例</summary>

#### 配置项 `werewolf__werewolf_priority`

```env
werewolf__werewolf_priority=[1, 2, 1, 1]
```

上述配置中，`[1, 2, 1, 1]` 表示狼人的职业优先级为 `狼人`, `狼王`, `狼人`, `狼人`

#### 配置项 `werewolf__priesthood_proirity`

```env
werewolf__priesthood_proirity=[11, 12, 13, 14, 15]
```

上述配置中，`[11, 12, 13, 14, 15]` 表示神职的职业优先级为 `预言家`, `女巫`, `猎人`, `守卫`, `白痴`

#### 职业与数字的对应关系

上述配置示例中有大量~~意义不明的~~数字, 其对应的是 [`这里`](./nonebot_plugin_werewolf/constant.py) 的枚举类 `Role` 的值

以下列出目前的枚举值供参考

| 职业     | 枚举值 |
| -------- | ------ |
| `狼人`   | `1`    |
| `狼王`   | `2`    |
| `预言家` | `11`   |
| `女巫`   | `12`   |
| `猎人`   | `13`   |
| `守卫`   | `14`   |
| `白痴`   | `15`   |
| `平民`   | `0`    |

</details>

## 📝 更新日志

<details>
    <summary>更新日志</summary>

<!-- CHANGELOG -->

- 2024.09.18 v1.1.2

  - 修改 Python 需求为 `>=3.10`

- 2024.09.11 v1.1.1

  - 修改 Python 需求为 `>=3.11`
  - 优化交互结果处理 ~~_可以在一局游戏中加入多个女巫了_~~

- 2024.09.09 v1.1.0

  - 新增职业 `小丑`
  - 修复守卫无法保护自己的 bug
  - 添加部分特殊职业的说明
  - 添加游戏过程中的日志输出

- 2024.09.04 v1.0.7

  - 优先使用群名片作为玩家名
  - 支持通过配置项修改职业分配优先级

- 2024.09.03 v1.0.6

  - 修复预言家查验狼王返回好人的 bug

- 2024.09.03 v1.0.5

  - 优化玩家交互体验
  - 添加游戏结束后死亡报告

- 2024.08.31 v1.0.1

  - 支持通过配置项修改职业预设

- 2024.08.31 v1.0.0

  - 插件开源

</details>

## 鸣谢

- [`nonebot/nonebot2`](https://github.com/nonebot/nonebot2): 跨平台 Python 异步机器人框架
- [`nonebot/plugin-alconna`](https://github.com/nonebot/plugin-alconna): 跨平台的消息处理接口
- [`noneplugin/nonebot-plugin-userinfo`](https://github.com/noneplugin/nonebot-plugin-userinfo): 用户信息获取
- [`RF-Tar-Railt/nonebot-plugin-waiter`](https://github.com/RF-Tar-Railt/nonebot-plugin-waiter): 灵活获取用户输入
- `热心群友`: 协助测试插件
