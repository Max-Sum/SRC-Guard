# iOS Shortcuts Client

## 中文

这个客户端使用一个共享的 iOS 快捷指令来通知 SRC Guard。安装后，用 iOS 个人自动化在《崩坏：星穹铁道》或《云·星穹铁道》打开/关闭时触发它。

### 安装快捷指令

在 iPhone 或 iPad 上打开：

[添加 SRC Guard 快捷指令](https://www.icloud.com/shortcuts/0f757b99882d41fcb5907818ca7df217)

添加后，打开快捷指令，直接在快捷指令内容里修改：

- URL，例如 `http://192.168.1.10:22368`
- token，也就是 `SRC_GUARD_TOKEN`

### 添加自动化

在“快捷指令”App 里进入“自动化”，添加 App 自动化：

1. 选择 App。
2. 选择《崩坏：星穹铁道》和/或《云·星穹铁道》。
3. 勾选“打开”和“关闭”。
4. 选择“立即运行”。
5. 关闭“运行时通知”。
6. 动作选择“运行快捷指令”，选择刚添加的 SRC Guard 快捷指令。

如果你的 iOS 版本仍显示“运行前询问”，请关闭“运行前询问”，并确认“不询问”。

### 行为

- 游戏打开时：快捷指令调用 `POST /webhook/play/start`，guard 会阻止 SRC 抢占登录。
- 游戏关闭时：快捷指令会延迟发送 stop；如果你只是短暂切后台，又回到游戏，pending stop 会被取消。
- 长时间游玩：再次调用 start 即可续期。（可以通过每隔一段时间调用自动化实现）

## English

This client uses a shared iOS Shortcut to notify SRC Guard. After installing it, use iOS Personal Automation to trigger it when Honkai: Star Rail or Cloud Honkai: Star Rail opens/closes.

### Install Shortcut

Open this on your iPhone or iPad:

[Add the SRC Guard Shortcut](https://www.icloud.com/shortcuts/0f757b99882d41fcb5907818ca7df217)

After adding it, open the shortcut and edit these values inside the shortcut:

- URL, for example `http://192.168.1.10:22368`
- token, meaning `SRC_GUARD_TOKEN`

### Add Automation

In the Shortcuts app, open Automation and create an App automation:

1. Choose App.
2. Select Honkai: Star Rail and/or Cloud Honkai: Star Rail.
3. Select both “Is Opened” and “Is Closed”.
4. Select “Run Immediately”.
5. Turn off “Notify When Run”.
6. Add “Run Shortcut” and choose the SRC Guard shortcut.

If your iOS version still shows “Ask Before Running”, turn it off and confirm “Don’t Ask”.

### Behavior

- When the game opens: the shortcut calls `POST /webhook/play/start`, so the guard prevents SRC from taking over the login.
- When the game closes: the shortcut delays stop; if you briefly background the game and return, the pending stop is cancelled.
- For long sessions: call start again to renew. (Add another automation to trigger periodically if necessary)
