---
layout:     post
title:      Address Sanitizer 使用笔记
subtitle:   Linux、WSL 与 Android 场景下的快速排查记录
date:       2026-04-24
author:     BY
header-img: img/post-bg-debug.png
catalog: true
tags:
    - Sanitizer
    - C++
    - Android
---

>保留原始结论，并把零散备注整理成便于回看的排查清单。

## 基本链接方式

使用 ASan 时，链接参数里需要带上线程库和 ASan 库，原始记录里特别提到：

```bash
-pthread -lasan
```

`-pthread` 建议放在前面，避免某些环境里链接顺序导致的问题。

## LeakSanitizer

```text
Linux 或虚拟机环境通常可以直接查 leak；
WSL 下泄漏结果不一定稳定，可能看不到预期输出。
```

因此如果主要目的是确认内存泄漏，优先在原生 Linux 环境复现。

## AddressSanitizer

```text
WSL 更适合查 use-after-free、越界访问这类地址问题。
```

也就是说：

- 查地址非法访问：WSL 可以先快速验证
- 查内存泄漏：更建议回到原生 Linux

## Android ASan

原始记录里的结论是：

```text
32 位 Android 13 及以前，通常需要配合专门的 ROM 或调试环境；
部分机型本身就不再提供 32 位支持，需要先确认设备能力。
```

整理后建议先确认三件事：

1. 目标进程是 32 位还是 64 位
2. 设备系统是否允许加载对应的 sanitizer 运行时
3. ROM / root / 调试权限是否满足注入要求

## Android HWASan

原始备注：

```text
64 位 Android 14 及以后更适合走 HWASan；
某些场景不需要 `wrap.sh`，强行带上反而可能导致编译或启动失败。
```

因此实际排查时不要默认照搬旧资料里的 `wrap.sh` 配置，先以当前 NDK、ROM 和构建链路验证为准。

## 建议的使用顺序

如果只是想尽快定位问题，可以按下面顺序尝试：

1. Linux / WSL 先复现基础内存问题
2. Linux 环境确认 leak
3. Android 侧再区分 ASan 还是 HWASan
4. 最后再补设备、ROM、ABI 兼容性验证
