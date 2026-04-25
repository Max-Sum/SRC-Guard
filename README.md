# SRC Guard

## 中文

SRC Guard 是一个小型 webhook 守卫服务，适合把 [StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot) 作为长期运行的 Docker 服务时使用。当你想在其他设备上登录并游玩时，它可以临时阻止 SRC 自动启动。

SRC Guard 会做三件事：

- 记录某个外部客户端正在游玩，并设置过期时间；
- 通过 ADB 关闭 Android 设备上的《崩坏：星穹铁道》；
- 只在安全时停止或启动配置好的 SRC Docker 容器。

这不是 SRC 官方部署方式。SRC 上游主要文档面向 Windows 自动安装包和手动 `python gui.py` 启动；本项目面向需要外部游玩锁的自托管/Docker 用户。

### 需求

- Docker Engine 或 Docker Desktop。
- SRC 在 Docker 中运行
- SRC 容器名稳定，例如 `starrailcopilot-src-1`。

### 快速开始

编辑 [docker-compose.yml](./docker-compose.yml)：

```yaml
SRC_GUARD_TOKEN: "change-me-to-a-long-random-token"
SRC_GUARD_SRC_CONTAINER: "starrailcopilot-src-1"
```

启动服务：

```bash
docker compose up -d
```

如果想从源码本地构建镜像，可以把 compose 里的 `image` 改成：

```yaml
build: .
```

默认监听端口是 `22368`。

### Webhook

所有受保护接口都接受下面任意一种鉴权 header：

```text
Authorization: Bearer <token>
X-SRC-Guard-Token: <token>
```

在其他设备开始游玩：

```bash
curl -X POST "http://<guard-host>:22368/webhook/play/start" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"client":"ipad","duration":360}'
```

`duration` 表示本次锁定时长，单位是分钟。

`start` 会设置或刷新同一个 `client` 的锁，并关游戏、停 SRC

```bash
curl -X POST "http://<guard-host>:22368/webhook/play/start" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"client":"ipad","duration":360}'
```

该设备停止游玩：

```bash
curl -X POST "http://<guard-host>:22368/webhook/play/stop" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"client":"ipad"}'
```

查看当前状态：

```bash
curl "http://<guard-host>:22368/status" \
  -H "Authorization: Bearer <token>"
```

### 客户端

推荐直接使用 [clients](./clients/) 里的客户端脚本：

- [Android Tasker 客户端](./clients/android-tasker/)
- [iOS 快捷指令客户端](./clients/ios-shortcuts/)
- [Windows PowerShell 客户端](./clients/windows/)

### 调度器集成

在 cron、调度器或更新脚本启动 SRC 前，先调用 `/allow-start`：

```bash
if curl -fsS -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:22368/allow-start" >/dev/null; then
  docker start <src-container>
fi
```

仍有其他客户端活跃时，`/allow-start` 返回 `423 Locked`。所有客户端停止或过期后，返回 `200 OK`。

### 配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SRC_GUARD_TOKEN` | 必填 | Webhook 共享密钥。 |
| `SRC_GUARD_SRC_CONTAINER` | `starrailcopilot-src-1` | guard 控制的 SRC Docker 容器。 |
| `SRC_GUARD_DEFAULT_DURATION` | `360` | 请求未传 `duration` 时的默认锁定时间，单位为分钟。 |
| `SRC_GUARD_MAX_DURATION` | `720` | 允许的最长锁定时间，单位为分钟。 |
| `SRC_GUARD_AUTO_RESUME` | `true` | 最后一个客户端停止后是否自动启动 SRC。 |

### 本地测试

使用 Miniforge/conda 测试环境：

```bash
mamba env create -f environment.yml
mamba run -n src-guard-test pytest -q
```

如果环境已经存在：

```bash
mamba env update -f environment.yml --prune
mamba run -n src-guard-test pytest -q
```

## English

SRC Guard is a small webhook guard for people who run [StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot) as a long-running Docker service. When you want to log in and play on another device, it can temporarily prevent SRC from starting automatically.

SRC Guard does three things:

- records that another client is currently playing, with an expiry time;
- closes Honkai: Star Rail on the Android device through ADB;
- stops or starts the configured SRC Docker container only when it is safe.

This is not an official SRC deployment method. The upstream SRC project primarily documents the Windows installer and manual Python startup with `python gui.py`; this guard is for self-hosted/Docker setups that need an external lock.

### Requirements

- Docker Engine or Docker Desktop.
- A StarRailCopilot process running in a Docker container.
- A stable container name for SRC, for example `starrailcopilot-src-1`.

### Quick Start

Edit [docker-compose.yml](./docker-compose.yml):

```yaml
SRC_GUARD_TOKEN: "change-me-to-a-long-random-token"
SRC_GUARD_SRC_CONTAINER: "starrailcopilot-src-1"
```

Then start the guard:

```bash
docker compose up -d
```

If you want to build the image locally from source, replace `image` in the compose file with:

```yaml
build: .
```

The service listens on `22368` by default.

### Webhooks

All protected endpoints accept either header:

```text
Authorization: Bearer <token>
X-SRC-Guard-Token: <token>
```

Start playing on another device:

```bash
curl -X POST "http://<guard-host>:22368/webhook/play/start" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"client":"ipad","duration":360}'
```

`duration` is the lock duration in minutes.

`start` sets or refreshes the same `client` lock. It closes the game and stops SRC:

```bash
curl -X POST "http://<guard-host>:22368/webhook/play/start" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"client":"ipad","duration":360}'
```

Stop playing on that device:

```bash
curl -X POST "http://<guard-host>:22368/webhook/play/stop" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"client":"ipad"}'
```

Check current lock state:

```bash
curl "http://<guard-host>:22368/status" \
  -H "Authorization: Bearer <token>"
```

### Clients

Prefer the ready-to-use scripts in [clients](./clients/):

- [Android Tasker client](./clients/android-tasker/)
- [iOS Shortcuts client](./clients/ios-shortcuts/)
- [Windows PowerShell client](./clients/windows/)

Android and iOS clients should hold locally before sending stop: after detecting that the game left the foreground, delay the stop request; if the game returns during that window, cancel the pending stop.

### Scheduler Integration

Use `/allow-start` before any cron, scheduler, or update job starts SRC:

```bash
if curl -fsS -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:22368/allow-start" >/dev/null; then
  docker start <src-container>
fi
```

When another client is still active, `/allow-start` returns `423 Locked`. When all clients have stopped or expired, it returns `200 OK`.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SRC_GUARD_TOKEN` | required | Shared secret for webhook calls. |
| `SRC_GUARD_SRC_CONTAINER` | `starrailcopilot-src-1` | Docker container controlled by the guard. |
| `SRC_GUARD_DEFAULT_DURATION` | `360` | Default lock duration, in minutes, when `duration` is omitted. |
| `SRC_GUARD_MAX_DURATION` | `720` | Maximum accepted lock duration, in minutes. |
| `SRC_GUARD_AUTO_RESUME` | `true` | Start SRC automatically when the last active client stops. |

### Local Tests

Use the Miniforge/conda test environment:

```bash
mamba env create -f environment.yml
mamba run -n src-guard-test pytest -q
```

If the environment already exists:

```bash
mamba env update -f environment.yml --prune
mamba run -n src-guard-test pytest -q
```