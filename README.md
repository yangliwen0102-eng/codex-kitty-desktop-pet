# Codex Kitty Desktop Pet

一个运行在 Windows 桌面上的透明 Codex 状态宠物。它只读监听本机 Codex
会话，根据任务、权限请求、完成、失败和空闲状态切换动画；鼠标悬停时还会
显示 5 小时与 7 天用量窗口及刷新倒计时。

![九种状态预览](docs/contact-sheet.jpg)

## 功能

- 透明、置顶、可拖动的 Windows 桌宠
- 九种状态：正常、悬停、拖动、工作、无聊、权限、完成、失败、离开
- 只读解析 `%CODEX_HOME%\sessions` 和 `logs_2.sqlite`
- 悬停显示 Codex 5 小时/7 天剩余用量与刷新倒计时
- 系统托盘隐藏、召回和彻底退出
- 当前用户登录自启动
- 单文件 Windows EXE，无需单独安装 Python

## 下载和安装

1. 打开仓库的 **Releases** 页面并下载 `CodexKittyPet-v1.0.0-win64.zip`。
2. 解压 ZIP，双击 `CodexKittyPet.exe` 可直接运行。
3. 需要登录自启动时，右键 PowerShell 运行 `install.ps1`。
4. 卸载时运行 `uninstall.ps1`；加 `-RemoveSettings` 可删除设置和日志。

发布包未做商业代码签名，Windows SmartScreen 可能显示未知发布者。请仅从本仓库
Release 下载，并在运行前核对 Release 页面中的文件来源。

## 运行条件

- Windows 10 或 Windows 11 x64
- 已使用过 Codex Desktop 或 Codex CLI
- 默认读取 `%USERPROFILE%\.codex`；设置了 `CODEX_HOME` 时自动使用该目录

监听不可用时，宠物仍支持正常、悬停、拖动、无聊、关闭和托盘功能。应用不会
上传、保存或展示提示词、回复和工作区文件内容。

## 从源码运行

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_pet.pyw
```

测试：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

## 本地构建

```powershell
python -m pip install -r requirements-dev.txt
.\build.ps1 -Python python -Version 1.0.0
```

构建完成后会生成：

- `dist\CodexKittyPet.exe`
- `release\CodexKittyPet-v1.0.0-win64.zip`

EXE 构建后会自动运行 `--check`，确认打包资源可读取。GitHub Actions 在每个
`v*` 标签上使用全新的 `windows-latest` 环境测试、构建 ZIP 并上传 Release。

## 状态触发

| 状态 | 触发条件 |
| --- | --- |
| idle | 默认轻微呼吸 |
| hover | 鼠标悬停，同时显示用量浮层 |
| dragging | 拖动桌宠 |
| working | Codex 任务开始 |
| bored | 600 秒未使用 Codex |
| permission | 等待权限或用户批准 |
| completed | 任务完成后播放一次 |
| failed | 活动任务明确报错、额度错误，或 15 秒内连续 3 次连接错误 |
| closing | 关闭按钮或托盘退出操作 |

## 数据与隐私

监听器只提取任务生命周期、权限状态、错误类别和限额百分比。它不写入 Codex
目录，也不持久化会话正文。本地设置和轮转日志位于
`%LOCALAPPDATA%\CodexKittyPet`。

## License

源代码使用 [GPL-3.0](LICENSE)。角色素材不包含在该授权中，详见
[ASSET_LICENSE.md](ASSET_LICENSE.md)。这是非官方项目，与 Sanrio 或 OpenAI
均无隶属或背书关系。
