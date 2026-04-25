---
layout:     post
title:      adb 端口占用排查
subtitle:   针对 5037 端口冲突的最小检查流程
date:       2026-04-24
author:     BY
header-img: img/post-bg-android.jpg
catalog: true
tags:
    - Android
    - adb
    - Troubleshooting
---

>这篇记录只保留最常用的一条链路：先确认 adb server 状态，再定位 5037 端口是谁占了。

## 常见现象

遇到下面这类问题时，优先怀疑 adb server 没起来，或者 5037 端口被别的进程占用：

- `adb devices` 卡住
- `adb start-server` 启动失败
- 提示无法绑定本地端口

## 排查步骤

### 1. 直接以前台方式启动 adb server

```bash
adb nodaemon server
```

这一步的目的，是先看 adb 自身能不能正常启动，以及有没有更直接的报错信息。

### 2. 检查 5037 端口占用

Windows 下可以先看端口：

```bash
netstat -ano | findstr "5037"
```

如果有输出，说明已经有进程占住了 adb 默认端口。

### 3. 根据 PID 反查进程名

```bash
tasklist | findstr "PID"
```

把上一步查到的 PID 替换进去，就能确认是哪个进程在占用端口。

### 4. 结束冲突进程后重试

确认确实不是自己需要保留的进程后，再结束它，然后重新执行：

```bash
adb start-server
adb devices
```

## 处理建议

- 如果是旧 adb 进程残留，结束后重启 adb 即可
- 如果是 Android Studio、模拟器或第三方工具占用，要先确认是否可以关闭对应程序
- 不建议在没确认进程来源前直接批量 kill，避免误伤正在使用的调试工具

## 参考截图

![image](https://github.com/user-attachments/assets/897c2100-7f47-4dcc-94e3-e63b1919c913)
