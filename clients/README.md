# SRC Guard Clients

## 中文

这里放的是可以直接使用的客户端脚本。

- [Android Tasker](./android-tasker/)：推荐给 Android 手机和平板。
- [iOS 快捷指令](./ios-shortcuts/)：安装共享快捷指令，用 App 自动化在星铁打开/关闭时触发。
- [Windows PowerShell](./windows/)：包含可导入的 Task Scheduler XML 生成/安装脚本。

客户端有保护： 自动化发现游戏离开前台后，先等一段时间再发送 stop，防止短暂切后台误触发。

## English

This directory contains ready-to-use client scripts.

- [Android Tasker](./android-tasker/): recommended for Android phones and tablets.
- [iOS Shortcuts](./ios-shortcuts/): install the shared shortcut and trigger it from App automation when Star Rail opens/closes.
- [Windows PowerShell](./windows/): includes importable Task Scheduler setup.

Clients use local protection: after automation detects that the game left the foreground, wait before sending stop to avoid short background switches;
