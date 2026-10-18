# macOS 个人版

保留已有像素皮肤、144 默认尺寸、安静动画、聊天标题与状态气泡、拖动和点击唤起。
macOS 使用 AppKit 激活已经运行的 Codex（com.openai.codex），通过 Quartz 检查输入活动；
不模拟按键、不自动批准授权。Qt 系统托盘对应 macOS 菜单栏，应用不显示 Dock 图标。

## 从源码运行与构建

需要 macOS、Python 3.11 以上、已使用过 Codex 的本机账户。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python run_pet.pyw
# 自动检测当前 Python 架构，先运行测试，再打包和检查资源
.venv/bin/python build_macos.py
open dist/CodexKittyPet.app
```

构建输出 `dist/CodexKittyPet.app` 和 `release/CodexKittyPet-macos-arm64.zip`
（Intel 本机构建时为 x86_64）。构建环境和所有依赖必须支持目标架构。
本机包为 ad-hoc 签名，没有 Apple Developer ID 签名或公证。
Intel 及其他 macOS 版本需另行验证。

可把 .app 拖入“应用程序”。需要登录启动时，在“系统设置 → 通用 → 登录项”中
手动添加该 .app；构建和首次启动不会自动添加登录项。

设置、位置和日志：`~/Library/Application Support/CodexKittyPet`。
会话仍只读访问 `CODEX_HOME` 或 `~/.codex`，标题不写入日志。
退出请使用菜单栏“彻底退出”；删除 .app 即卸载，保留设置方便恢复。

## 验证范围

自动测试覆盖状态、气泡、皮肤、拖动与点击区分、隐藏召回、macOS 原生 API 和资源。
真实桌面还需验证透明背景、Retina 显示、菜单栏可见性、点击后 Codex 前置、跨屏拖动。
气泡从本地事件推断任务状态，可能有延迟；不保证切换到指定聊天。

2026-10-18 本机结果：macOS 15.6.1 / Apple Silicon arm64 / Python 3.12.14，
33 项测试中 31 项通过、2 项 Windows 专用测试跳过；打包资源检查与 codesign
完整性验证通过。通过桌面启动接口启动成功，窗口可见，日志显示真实本机会话事件
与 working 状态切换。终端沙箱内直接启动受系统图形服务限制。
桌面自动化后续交互超时，透明合成、菜单栏交互、点击唤起和多屏效果仍需人工确认。
