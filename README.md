<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-werewolf

_✨ 简单的狼人杀插件 ✨_

[![license](https://img.shields.io/github/license/wyf7685/nonebot-plugin-werewolf.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-werewolf?logo=python&logoColor=edb641)](https://pypi.python.org/pypi/nonebot-plugin-exe-code)
[![python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=edb641)](https://www.python.org/)

[![pdm-managed](https://img.shields.io/endpoint?url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fpdm-project%2F.github%2Fbadge.json)](https://pdm-project.org)
[![isort](https://img.shields.io/badge/%20imports-isort-%231674b1)](https://pycqa.github.io/isort/)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pyright](https://img.shields.io/badge/types-pyright-797952.svg?logo=python&logoColor=edb641)](https://github.com/Microsoft/pyright)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

## 📖 介绍

和朋友们来一场紧张刺激的狼人杀游戏

## 💿 安装

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

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

|           配置项            | 必填 | 默认值 |                             说明                              |
| :-------------------------: | :--: | :----: | :-----------------------------------------------------------: |
|   `werewolf__enable_poke`   |  否  | `True` | 是否使用戳一戳简化操作流程<br/>仅在 `OneBot V11` 适配器下生效 |
| `werewolf__override_preset` |  否  |   -    |                    覆写插件内置的职业预设                     |

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

|        指令         | 权限 | 需要@ | 范围 |   说明   |
| :-----------------: | :--: | :---: | :--: | :------: |
| `werewolf`/`狼人杀` | 群员 |  是   | 群聊 | 发起游戏 |

### 游戏内容

> [!note]
>
> 插件的游戏规则参考了网络上的相关资料
>
> 如有疑问欢迎提出

插件中保存了一份 [职业预设](./nonebot_plugin_werewolf/constant.py), 内容如下

| 总人数 | 狼人 | 神职 | 平民 |
| ------ | ---- | ---- | ---- |
| 6      | 1    | 3    | 2    |
| 7      | 2    | 3    | 2    |
| 8      | 2    | 3    | 3    |
| 9      | 2    | 4    | 3    |
| 10     | 3    | 4    | 3    |
| 11     | 3    | 5    | 3    |
| 12     | 4    | 5    | 3    |

职业预设可以通过配置项 `werewolf__override_preset` 修改

<details>
    <summary>配置项 `werewolf__override_preset` 示例</summary>

```env
werewolf__override_preset='
[
    [6, 1, 3, 2],
    [7, 2, 3, 2]
]
'
```

上述配置中，`[6, 1, 3, 2]` 表示当总人数为 6 时，狼人、神职、平民的数量分别为 1、3、2

</details>
<br/>

对于`狼人`和`神职`的职业分配，有如下优先级:

- `狼人`: `狼人`, `狼人`, `狼王`, `狼人`
- `神职`: `预言家`, `女巫`, `猎人`, `守卫`, `白痴`

## 📝 更新日志

<details>
    <summary>更新日志</summary>

- 2024.08.31 v1.0.1

  - 允许通过配置项修改职业预设

- 2024.08.31 v1.0.0

  - 插件开源

</details>

## 鸣谢

- [`nonebot/nonebot2`](https://github.com/nonebot/nonebot2): 跨平台 Python 异步机器人框架
- [`nonebot/plugin-alconna`](https://github.com/nonebot/plugin-alconna): 跨平台的消息处理接口
- [`noneplugin/nonebot-plugin-userinfo`](https://github.com/noneplugin/nonebot-plugin-userinfo): 用户信息获取
- [`RF-Tar-Railt/nonebot-plugin-waiter`](https://github.com/RF-Tar-Railt/nonebot-plugin-waiter): 灵活获取用户输入
