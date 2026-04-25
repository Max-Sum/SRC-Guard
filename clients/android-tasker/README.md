# Android Tasker Client

## 中文

这个客户端给 Tasker + Termux:Tasker 使用。它已经处理好了：

- 游戏进入前台时调用 `start`；
- 游玩中定时调用 `refresh-if-active`，它会通过 `start` webhook 续期；
- 游戏离开前台时调用 `hold-stop`，先等待 `HOLD_SECONDS`，如果期间游戏又回到前台就取消 stop；
- `HOLD_SECONDS` 到期后才真正向 guard 发送 stop。

### 安装

在 Termux 里运行：

```sh
pkg install curl
mkdir -p ~/.termux/tasker ~/.config
cp clients/android-tasker/src-guard-tasker.sh ~/.termux/tasker/
cp clients/android-tasker/src-guard-tasker.env.example ~/.config/src-guard-tasker.env
chmod +x ~/.termux/tasker/src-guard-tasker.sh
```

编辑配置：

```sh
nano ~/.config/src-guard-tasker.env
```

至少修改：

```sh
GUARD_URL="http://<guard-host>:22368"
TOKEN="<token>"
```

### Tasker 任务

安装 Tasker 和 Termux:Tasker 插件后，创建 3 个 Task。

`SRC Guard Start`：

- Action: Plugin -> Termux:Tasker
- Executable: `src-guard-tasker.sh`
- Arguments: `start`

`SRC Guard Refresh`：

- Action: Plugin -> Termux:Tasker
- Executable: `src-guard-tasker.sh`
- Arguments: `refresh-if-active`

`SRC Guard Hold Stop`：

- Action: Plugin -> Termux:Tasker
- Executable: `src-guard-tasker.sh`
- Arguments: `hold-stop`

### Tasker Profile

Profile 1：

- Context: Application
- App: 《崩坏：星穹铁道》或《云·星穹铁道》
- Enter Task: `SRC Guard Start`
- Exit Task: `SRC Guard Hold Stop`

Profile 2：

- Context: Time
- Repeat: 每 3 小时一次，间隔要小于 `DURATION`
- Task: `SRC Guard Refresh`

### 参数

在 `~/.config/src-guard-tasker.env` 里改：

- `DURATION`：guard 锁的游玩时长，单位为分钟，客户端会通过 `start` 续期。
- `HOLD_SECONDS`：客户端本地 hold 时间。游戏短暂切后台时，stop 会被延后。

### 手动测试

```sh
~/.termux/tasker/src-guard-tasker.sh start
~/.termux/tasker/src-guard-tasker.sh refresh-if-active
~/.termux/tasker/src-guard-tasker.sh hold-stop
~/.termux/tasker/src-guard-tasker.sh status
```

## English

This client is for Tasker + Termux:Tasker. It handles:

- `start` when the game enters the foreground;
- periodic `refresh-if-active` while playing; it renews through the `start` webhook;
- `hold-stop` when the game leaves the foreground, waiting `HOLD_SECONDS` before stop and cancelling it if the game comes back;
- the real stop request is sent to the guard only after `HOLD_SECONDS` expires.

### Install

Run in Termux:

```sh
pkg install curl
mkdir -p ~/.termux/tasker ~/.config
cp clients/android-tasker/src-guard-tasker.sh ~/.termux/tasker/
cp clients/android-tasker/src-guard-tasker.env.example ~/.config/src-guard-tasker.env
chmod +x ~/.termux/tasker/src-guard-tasker.sh
```

Edit config:

```sh
nano ~/.config/src-guard-tasker.env
```

At minimum, change:

```sh
GUARD_URL="http://<guard-host>:22368"
TOKEN="<token>"
```

### Tasker Tasks

After installing Tasker and the Termux:Tasker plugin, create 3 tasks.

`SRC Guard Start`:

- Action: Plugin -> Termux:Tasker
- Executable: `src-guard-tasker.sh`
- Arguments: `start`

`SRC Guard Refresh`:

- Action: Plugin -> Termux:Tasker
- Executable: `src-guard-tasker.sh`
- Arguments: `refresh-if-active`

`SRC Guard Hold Stop`:

- Action: Plugin -> Termux:Tasker
- Executable: `src-guard-tasker.sh`
- Arguments: `hold-stop`

### Tasker Profiles

Profile 1:

- Context: Application
- App: Honkai: Star Rail or Cloud Honkai: Star Rail
- Enter Task: `SRC Guard Start`
- Exit Task: `SRC Guard Hold Stop`

Profile 2:

- Context: Time
- Repeat: every 3 hours, shorter than `DURATION`
- Task: `SRC Guard Refresh`

### Parameters

Edit `~/.config/src-guard-tasker.env`:

- `DURATION`: guard lock duration in minutes; the client renews it through `start`.
- `HOLD_SECONDS`: local client hold time before sending stop.

### Manual Test

```sh
~/.termux/tasker/src-guard-tasker.sh start
~/.termux/tasker/src-guard-tasker.sh refresh-if-active
~/.termux/tasker/src-guard-tasker.sh hold-stop
~/.termux/tasker/src-guard-tasker.sh status
```
