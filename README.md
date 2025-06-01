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
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![wakatime](https://wakatime.com/badge/user/b097681b-c224-44ec-8e04-e1cf71744655/project/70a7f68d-5625-4989-9476-be6877408332.svg)](https://wakatime.com/badge/user/b097681b-c224-44ec-8e04-e1cf71744655/project/70a7f68d-5625-4989-9476-be6877408332)
[![pre-commit](https://results.pre-commit.ci/badge/github/wyf7685/nonebot-plugin-werewolf/master.svg)](https://results.pre-commit.ci/latest/github/wyf7685/nonebot-plugin-werewolf/master)
[![lint](https://github.com/wyf7685/nonebot-plugin-werewolf/actions/workflows/lint.yml/badge.svg?branch=master&event=push)](https://github.com/wyf7685/nonebot-plugin-werewolf/actions/workflows/lint.yml)

<!-- ref: https://github.com/lgc2333/nonebot-registry-badge -->

[![NoneBot Registry](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin%2Fnonebot-plugin-werewolf)](https://registry.nonebot.dev/plugin/nonebot-plugin-werewolf:nonebot_plugin_werewolf)
[![Supported Adapters](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin-adapters%2Fnonebot-plugin-werewolf)](https://registry.nonebot.dev/plugin/nonebot-plugin-werewolf:nonebot_plugin_werewolf)

</div>

## 📖 介绍

和朋友们来一场紧张刺激的狼人杀游戏

<!-- ref: https://github.com/KomoriDev/Starify -->

> [!IMPORTANT]
> **收藏项目**，你将从 GitHub 上无延迟地接收所有发布通知～⭐️

<img width="100%" src="https://starify.komoridevs.icu/api/starify?owner=wyf7685&repo=nonebot-plugin-werewolf" alt="starify" />

<details>
  <summary><kbd>Star History</kbd></summary>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=wyf7685/nonebot-plugin-werewolf&theme=dark&type=Date" />
    <img width="100%" src="https://star-history.com/#wyf7685/nonebot-plugin-werewolf&Date" />
  </picture>
</details>

## 💿 安装

> [!note]
>
> 请确保 [NoneBot2](https://nonebot.dev/) 使用的 Python 解释器版本 >=3.10

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-werewolf

</details>

<details>
<summary>使用包管理器安装</summary>
<!-- 会用包管理器的用户真的需要这节吗 -->

在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details open>
<summary>uv</summary>

    uv add nonebot-plugin-werewolf

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
<details>
<summary>pip</summary>

    pip install nonebot-plugin-werewolf

</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_werewolf"]

</details>

## ⚙️ 配置

在 nonebot2 项目的 `.env` 文件中添加如下配置:

|            配置项            | 必填 | 默认值  |           类型            |              说明              |
| :--------------------------: | :--: | :-----: | :-----------------------: | :----------------------------: |
|   `werewolf__enable_poke`    |  否  | `True`  |          `bool`           |   是否使用戳一戳简化操作流程   |
|  `werewolf__enable_button`   |  否  | `False` |          `bool`           |      是否在交互中添加按钮      |
|   `werewolf__stop_command`   |  否  | `stop`  |     `str \| set[str]`     |  修改游戏进程中的 `stop` 命令  |
|    `werewolf__require_at`    |  否  | `True`  | `bool \| RequireAtConfig` | 部分命令是否需要 at 机器人触发 |
| `werewolf__matcher_priority` |  否  |    -    |  `MatcherPriorityConfig`  | 配置插件 matcher 注册的优先级  |

`werewolf__enable_poke` 仅在 `OneBot V11` 适配器 / `Satori/chronocat` 下生效

`werewolf__enable_button` 仅在 `Telegram` 适配器下通过测试，不保证在其他适配器的可用性，如有疑问欢迎提出。

<details>
<summary> werewolf__require_at 示例 </summary>

```ini
# 所有命令均需 at 触发
werewolf__require_at=true

# 所有命令均不需 at 触发
werewolf__require_at=false

# 狼人杀命令需要 at, 中止游戏命令不需要 at
werewolf__require_at='{"start": true, "terminate": false}'
```

</details>

`werewolf__matcher_priority` 的 matcher 优先级参考 [官方文档](https://nonebot.dev/docs/advanced/matcher#%E5%93%8D%E5%BA%94%E4%BC%98%E5%85%88%E7%BA%A7)

- 一般情况下不需要修改此配置, 插件的默认优先级可以参考 [这里](./nonebot_plugin_werewolf/config.py) 的 `MatcherPriorityConfig`
- 如果遇到与其他插件的命令冲突, 可考虑修改此处的优先级配置
- 配置应填入 JSON 对象, 可用键: `start` `terminate` `preset` `behavior` `in_game` `stop`

## 🚀 使用

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

在使用本插件前，应当确保机器人可以正常向玩家发送私聊消息。~~即保证机器人与玩家为好友关系~~

</details>

### 📋 指令表

|        指令         |        权限         | 需要@ |       范围        |             说明             |
| :-----------------: | :-----------------: | :---: | :---------------: | :--------------------------: |
| `werewolf`/`狼人杀` |        群员         |  是   |  群聊 _[游戏外]_  |   发起游戏 (进入准备阶段)    |
|     `开始游戏`      |     游戏发起者      |  否   | 群聊 _[准备阶段]_ |      游戏发起者开始游戏      |
|     `结束游戏`      | 游戏发起者/超级用户 |  否   | 群聊 _[准备阶段]_ | 游戏发起者/超级用户 结束游戏 |
|     `当前玩家`      |        群员         |  否   | 群聊 _[准备阶段]_ |    列出参与游戏的玩家列表    |
|     `加入游戏`      |        群员         |  否   | 群聊 _[准备阶段]_ |         玩家加入游戏         |
|     `退出游戏`      |        群员         |  否   | 群聊 _[准备阶段]_ |         玩家退出游戏         |
|     `中止游戏`      |      超级用户       |  是   |  群聊 _[游戏内]_  |     超级用户强制中止游戏     |
|    `狼人杀预设`     |      超级用户       |  否   |  任意 _[游戏外]_  |     超级用户编辑游戏预设     |
|    `狼人杀配置`     |      超级用户       |  否   |  任意 _[游戏外]_  |     超级用户编辑游戏配置     |

- `超级用户` 为 nonebot2 配置项中的 `SUPERUSERS`, 配置说明参考 [官方文档](https://nonebot.dev/docs/appendices/config#superusers)

- 发起游戏时添加 `restart`/`重开`, 可加载上一次游戏的玩家列表, 快速发起游戏。例: `werewolf restart`/`狼人杀 重开`

- `狼人杀预设` 命令用法可通过 `狼人杀预设 --help` 获取，或参考 [游戏内容](#游戏内容) 部分的介绍

- `狼人杀配置` 命令用法可通过 `狼人杀预设 --help` 获取

- 对于 `OneBot V11` 适配器和 `Satori` 适配器的 `chronocat`, 启用配置项 `werewolf__enable_poke` 后, 可以使用戳一戳代替 _准备阶段_ 的 `加入游戏` 操作 和 游戏内的 `stop` 命令

- _其他交互参考游戏内提示_

### 🎭 游戏内容

> [!note]
>
> 插件的游戏规则参考了网络上的相关资料
>
> 如有疑问欢迎提出

插件中保存了一份 [职业预设](./nonebot_plugin_werewolf/constant.py), 内容如下

| 总人数 | 狼人 | 神职 | 平民 |
| :----: | :--: | :--: | :--: |
|   6    |  1   |  2   |  3   |
|   7    |  2   |  2   |  3   |
|   8    |  2   |  3   |  3   |
|   9    |  2   |  4   |  3   |
|   10   |  3   |  4   |  3   |
|   11   |  3   |  5   |  3   |
|   12   |  4   |  5   |  3   |

职业预设可以通过命令 `狼人杀预设 职业 ...` 修改

<details>
<summary>示例</summary>

- 命令: `狼人杀预设 职业 6 1 3 2`

- 上述命令指定当总人数为 6 时，狼人、神职、平民的数量分别为 1、3、2

</details>
<br/>

对于`狼人`和`神职`的职业分配，默认有如下优先级:

- `狼人`: `狼人`, `狼人`, `狼王`, `狼人`
- `神职`: `女巫`, `预言家`, `猎人`, `守卫`, `白痴`

职业分配优先级可以通过命令 `狼人杀预设 狼人/神职` 修改

<details>
<summary>示例</summary>

#### 命令 `狼人杀预设 狼人`

- 命令: `狼人杀预设 狼人 狼 狼王 狼 狼`

- 上述命令指定狼人的职业优先级为 `狼人`, `狼王`, `狼人`, `狼人`

#### 命令 `狼人杀预设 神职`

- 命令: `狼人杀预设 神职 预言家 女巫 猎人 守卫 白痴`

- 上述命令指定神职的职业优先级为 `预言家`, `女巫`, `猎人`, `守卫`, `白痴`

> [!note]
>
> 以上两条命令均支持交互式输入 ~~waiter 真好用~~
>
> 例：向机器人发送命令 `狼人杀预设 狼人`，在接下来的一条消息中发送 `狼人 狼王 狼人 狼人`
>
> 其效果等同于以上描述中的单条命令 `狼人杀预设 狼人 狼人 狼王 狼人 狼人`

</details>

对于 `小丑` 职业，当预设中的平民数量大于或等于 2 时，将有 _一定概率_ 将其中一个平民替换为小丑。

小丑属于第三方阵营，胜利条件为在投票阶段被票出，在预言家查验及游戏进程判断时视作平民。

小丑生成概率可以通过命令 `狼人杀预设 小丑 <概率>` 设置，默认值为 0 (不生成小丑)。

### 🔧 已知问题

<details>
    <summary>已知问题</summary>

- 截止 chronocat [v0.2.19](https://github.com/chrononeko/chronocat/tree/v0.2.19), 调用 [`guild.member.get`](https://github.com/chrononeko/chronocat/blob/8558ad9ff4319395d86abbfda22136939bf66780/packages/engine-chronocat-api/src/api/guild/member/get.ts) / [`user.get`](https://github.com/chrononeko/chronocat/blob/8558ad9ff4319395d86abbfda22136939bf66780/packages/engine-chronocat-api/src/api/user/get.ts) 均无法获取用户名，这将导致在交互过程中的玩家名显示为用户 ID

- v1.1.6 添加的按钮操作在 `discord` 适配器中不可用, 已在 v1.1.12 禁用 (2e31d43)

</details>

## 📝 更新日志

<details>
    <summary>更新日志</summary>

<!-- CHANGELOG -->

- 2025.06.01 v1.1.12

  - 禁用 `discord` 适配器中的按钮操作 ~~以后会写适配的...吗?~~

- 2025.04.20 v1.1.11

  - 添加配置项 `werewolf__require_at`, 用于配置命令是否需要 at 机器人触发
  - 添加配置项 `werewolf__matcher_priority`, 用于配置插件 matcher 注册优先级

- 2025.04.17 v1.1.10

  - 添加狼人多选目标配置项显示
  - 在游戏开始时打乱并固定轮流发言模式的发言顺序 (#20)

- 2025.04.15 v1.1.9

  - 添加游戏行为配置 `werewolf_multi_select`
  - 重构玩家类
  - 添加轮流发言模式缺失的 at 消息段 (#19)

- 2025.02.13 v1.1.8

  - 优化交互按钮
  - 新增命令 `狼人杀配置` 用于调整游戏行为
  - 新增配置项 `werewolf__stop_command`

- 2024.10.31 v1.1.7

  - _Bug fix_

- 2024.10.31 v1.1.6

  - 新增超级用户中止游戏 (#7)
  - 新增快速发起上次游戏 (#8)
  - 准备阶段添加可选的交互按钮
  - 新增超级用户修改游戏预设 (#9)

- 2024.10.23 v1.1.5

  - 添加对 chronocat:poke 的支持
  - 游戏内 stop 命令使用 COMMAND_START
  - 使用 `anyio` 重写并发逻辑

- 2024.10.06 v1.1.3

  - 使用 `RF-Tar-Railt/nonebot-plugin-uninfo` 获取用户数据
  - 优化交互文本

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

## 🎉 鸣谢

- [`nonebot/nonebot2`](https://github.com/nonebot/nonebot2): 跨平台 Python 异步机器人框架
- [`nonebot/plugin-alconna`](https://github.com/nonebot/plugin-alconna): 跨平台的消息处理接口
- [`RF-Tar-Railt/nonebot-plugin-uninfo`](https://github.com/RF-Tar-Railt/nonebot-plugin-uninfo): 用户信息获取
- [`RF-Tar-Railt/nonebot-plugin-waiter`](https://github.com/RF-Tar-Railt/nonebot-plugin-waiter): 灵活获取用户输入
- `热心群友`: 协助测试插件
