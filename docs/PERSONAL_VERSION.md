# 个人定制版存档

保存日期：2026-10-18。此版本保存了 Windows 桌面当前使用的定制代码和素材。

## 已完成并验证

- 精细像素风 Hello Kitty 九状态素材，默认显示尺寸 144。
- 约 6 秒一次、最多 1 像素位移的轻微动画，原地淡出退出。
- 姿势变化等待状态稳定 1.2 秒，减少频繁切换。
- 点击 Kitty 或状态气泡唤起已有 Codex 桌面聊天窗口，拖动移动。
- 状态气泡显示聊天标题、任务处理、等待确认、完成、出错和空闲。
- 多任务优先显示等待确认的任务；右键可关闭气泡，当前设置在重启后恢复显示。
- 本地只读状态监听、用量提示、托盘和 Windows 登录自启动。
- Windows 本地 29 项测试通过，EXE 资源检查通过。

气泡根据本地会话事件推断状态，可能短暂延迟；它不是 Codex 原生实时接口。
点击不会自动批准授权，也不会自动切换到其他聊天中的授权请求。
聊天标题从本地状态索引只读获取，不写入桌宠日志。

## 从 GitHub 恢复 Windows 版本

1. 下载本仓库个人版 Release 中的 `CodexKittyPet-v1.0.0-status-win64.zip`。
2. 解压后双击 `CodexKittyPet.exe`；无需安装 Python。
3. 如需桌面快捷方式与登录自启动，运行发布包的 `install.ps1`。
4. 用户位置、尺寸与日志由应用在本机单独保存，不包含在 Git 仓库中。

源码重新构建沿用 README 和 `build.ps1`。构建脚本会隔离其他工具的 PATH，
避免同名系统 DLL 被误打包。皮肤源图、预览和生成说明都保存在 `assets/pixel/`。

## macOS：后续适配起点

目前仅 Windows 版本可运行，Windows EXE 不能用于 macOS。以下是移植清单，
不是已经完成或验证的 Mac 安装说明：

1. `requirements.txt`：将 `pywin32` 设为仅 Windows 安装的依赖。
2. `codex_pet/activate.py`：把 Win32 窗口操作隔离为 Windows 实现，
   为 macOS 增加通过系统应用激活方式唤起 Codex 的实现。
3. `codex_pet/window.py`：隔离 `win32gui`、`win32process`、
   `ctypes.windll.user32.GetLastInputInfo`；适配前台应用及空闲时间检测。
4. `codex_pet/config.py`：macOS 设置与日志目录使用
   `~/Library/Application Support/CodexKittyPet`，会话目录继续从
   `CODEX_HOME` 或 `~/.codex` 获取。
5. 保留 Qt 界面、像素素材、动画和只读本地索引读取；在 Mac 上验证
   置顶窗口、透明背景、托盘、Retina 缩放、拖动、气泡与多屏边界。
6. 为 Apple Silicon 原生构建 `.app`；如需 Intel 版本，单独构建并验证。
   增加 Mac 安装和登录启动方案，不能复用 Windows PowerShell 安装脚本。
7. 用真实 macOS Codex 会话验证状态路径和索引结构，完成测试后再发布 Mac 包。

在 Mac 上继续时，可以把本仓库交给 Codex，并说明：

> 请基于当前个人定制版适配 macOS，保留精细像素 Kitty、小尺寸、安静动画、
> 聊天状态气泡和点击唤起功能。先阅读 docs/PERSONAL_VERSION.md，
> 隔离 Win32 依赖，然后在本机测试并构建原生 .app。

## 来源

原项目：<https://github.com/eatingwang012/codex-kitty-desktop-pet>。
源代码保留 GPL-3.0。角色素材说明见 `ASSET_LICENSE.md`；这是非官方项目。
