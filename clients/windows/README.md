# Windows PowerShell Client

## 中文

[SRCGuardClient.ps1](./SRCGuardClient.ps1) 是可直接使用的 Windows 客户端。它支持：

- `event-start`：由 Windows 进程创建事件触发，匹配游戏 exe 后通知 guard。
- `event-stop`：由 Windows 进程退出事件触发，匹配游戏 exe 后立即释放 Windows 客户端锁。
- `start`：开始游玩，通知 guard 关游戏/停 SRC。
- `refresh-if-active`：本地状态仍在 playing 时调用 `start` 续期。
- `stop`：发送 stop。

### 推荐：进程事件计划任务

[Install-ScheduledTasks.ps1](./Install-ScheduledTasks.ps1) 会生成可导入的 Task Scheduler XML，并可直接注册计划任务。Windows 客户端不会启动、注入或修改游戏；它使用 Windows Security 日志里的进程创建/退出事件触发任务。

建议用完整 exe 路径，事件过滤会更精准：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Install-ScheduledTasks.ps1 `
  -GuardUrl "http://<guard-host>:22368" `
  -Token "<token>" `
  -GameProcessPath "C:\Path\To\StarRail.exe" `
  -Duration 360 `
  -RefreshIntervalMinutes 180 `
  -EnableProcessAudit `
  -Force
```

`-Duration` 的单位是分钟。

它会创建：

- `SRC Guard Game Start`：Security 4688 进程创建事件触发。
- `SRC Guard Game Stop`：Security 4689 进程退出事件触发。
- `SRC Guard Refresh`：登录后自动启用，并每 3 小时调用 `start` 续期一次；只有本地状态是 playing 时才会请求 guard。
- `SRC Guard Start`：手动备用，表示开始游玩。
- `SRC Guard Stop`：手动备用，立即停止 Windows 客户端锁。

如果只知道 exe 名称，也可以用 `-GameProcessName "StarRail.exe"`。这会让事件任务在进程创建/退出事件上唤醒，再由客户端脚本过滤 exe 名称：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Install-ScheduledTasks.ps1 `
  -GuardUrl "http://<guard-host>:22368" `
  -Token "<token>" `
  -GameProcessName "StarRail.exe" `
  -EnableProcessAudit `
  -Force
```

`-EnableProcessAudit` 会启用 Windows 的 Process Creation / Process Termination 审计，通常需要管理员 PowerShell。没有这两个审计事件时，计划任务不会收到 exe 启动/退出触发。

可以从任务管理器“详细信息”页查看 exe 名称，也可以运行：

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like "*Star*" } |
  Select-Object Name, ExecutablePath
```

同时会生成 XML 和 `.cmd` 触发脚本：

```text
clients/windows/generated/
```

配置会写入：

```text
%LOCALAPPDATA%\SRCGuardClient\config.json
```

如果你只想生成 XML，然后自己在“任务计划程序”里导入：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Install-ScheduledTasks.ps1 `
  -GuardUrl "http://<guard-host>:22368" `
  -Token "<token>" `
  -GameProcessPath "C:\Path\To\StarRail.exe" `
  -GenerateOnly
```

然后打开“任务计划程序”：

1. 右侧选择“导入任务”。
2. 依次导入 `generated` 里的 XML。
3. 确认任务路径是 `\SRC Guard\`。

### 触发任务

安装脚本会生成这些 `.cmd` 文件：

- `SRC Guard Game Start.cmd`
- `SRC Guard Game Stop.cmd`
- `SRC Guard Start.cmd`
- `SRC Guard Stop.cmd`
- `SRC Guard Refresh.cmd`

通常不用手动运行 start/stop；`SRC Guard Game Start` / `SRC Guard Game Stop` 会由 Windows 事件自动触发。`.cmd` 文件只是备用入口。

也可以直接运行：

```powershell
schtasks /run /tn "\SRC Guard\SRC Guard Start"
schtasks /run /tn "\SRC Guard\SRC Guard Stop"
```

### 手动使用

```powershell
$env:SRC_GUARD_URL = "http://<guard-host>:22368"
$env:SRC_GUARD_TOKEN = "<token>"
```

开始游玩：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SRCGuardClient.ps1 -Action start
```

刷新：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SRCGuardClient.ps1 -Action refresh-if-active
```

停止：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SRCGuardClient.ps1 -Action stop
```

常用做法：

- 手动排障时运行 `start` 或 `stop`。
- 任务计划程序每 3 小时运行 `refresh-if-active`。
- 常规使用依赖进程创建/退出事件自动识别游戏进程。

## English

[SRCGuardClient.ps1](./SRCGuardClient.ps1) is a ready-to-use Windows client. It supports:

- `event-start`: triggered by a Windows process creation event, then notifies the guard if the exe matches.
- `event-stop`: triggered by a Windows process exit event, then releases the Windows client lock if the exe matches.
- `start`: start playing and ask the guard to close games / stop SRC.
- `refresh-if-active`: call `start` to renew while the local state is still playing.
- `stop`: send stop immediately. Windows does not use hold.

### Recommended: Process Event Scheduled Tasks

[Install-ScheduledTasks.ps1](./Install-ScheduledTasks.ps1) generates Task Scheduler XML files and can register the tasks for you. The Windows client does not launch, inject into, or modify the game; it uses process creation/exit events from the Windows Security log.

Prefer the full exe path for precise event filtering:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Install-ScheduledTasks.ps1 `
  -GuardUrl "http://<guard-host>:22368" `
  -Token "<token>" `
  -GameProcessPath "C:\Path\To\StarRail.exe" `
  -Duration 360 `
  -RefreshIntervalMinutes 180 `
  -EnableProcessAudit `
  -Force
```

`-Duration` is measured in minutes.

It creates:

- `SRC Guard Game Start`: triggered by Security 4688 process creation events.
- `SRC Guard Game Stop`: triggered by Security 4689 process exit events.
- `SRC Guard Refresh`: enabled at logon and repeated every 3 hours; it calls `start` only when local state is playing.
- `SRC Guard Start`: manual fallback for start playing.
- `SRC Guard Stop`: manual fallback for immediate stop.

If you only know the exe name, use `-GameProcessName "StarRail.exe"`. The event tasks will wake on process creation/exit events, and the client script filters by exe name:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Install-ScheduledTasks.ps1 `
  -GuardUrl "http://<guard-host>:22368" `
  -Token "<token>" `
  -GameProcessName "StarRail.exe" `
  -EnableProcessAudit `
  -Force
```

`-EnableProcessAudit` enables Windows Process Creation / Process Termination auditing, which usually requires an administrator PowerShell. Without these audit events, Task Scheduler will not receive exe start/exit triggers.

You can find the exe name from Task Manager's Details tab, or run:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like "*Star*" } |
  Select-Object Name, ExecutablePath
```

It also writes XML and `.cmd` helper files to:

```text
clients/windows/generated/
```

Config is written to:

```text
%LOCALAPPDATA%\SRCGuardClient\config.json
```

To only generate XML and import it manually:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Install-ScheduledTasks.ps1 `
  -GuardUrl "http://<guard-host>:22368" `
  -Token "<token>" `
  -GameProcessPath "C:\Path\To\StarRail.exe" `
  -GenerateOnly
```

Then open Task Scheduler:

1. Choose `Import Task`.
2. Import the XML files from `generated`.
3. Confirm the task path is `\SRC Guard\`.

### Trigger Tasks

The installer writes these `.cmd` files:

- `SRC Guard Game Start.cmd`
- `SRC Guard Game Stop.cmd`
- `SRC Guard Start.cmd`
- `SRC Guard Stop.cmd`
- `SRC Guard Refresh.cmd`

Usually you do not need to run start/stop manually; `SRC Guard Game Start` / `SRC Guard Game Stop` are triggered by Windows events. The `.cmd` files are fallback entrypoints.

You can also run:

```powershell
schtasks /run /tn "\SRC Guard\SRC Guard Start"
schtasks /run /tn "\SRC Guard\SRC Guard Stop"
```

### Manual Usage

```powershell
$env:SRC_GUARD_URL = "http://<guard-host>:22368"
$env:SRC_GUARD_TOKEN = "<token>"
```

Start playing:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SRCGuardClient.ps1 -Action start
```

Refresh:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SRCGuardClient.ps1 -Action refresh-if-active
```

Stop:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SRCGuardClient.ps1 -Action stop
```

Typical setup:

- run `start` or `stop` manually for troubleshooting;
- run `refresh-if-active` every 3 hours from Task Scheduler;
- rely on process creation/exit events for normal detection.
