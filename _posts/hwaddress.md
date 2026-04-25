---
layout:     post
title:      Android HWASan 使用补充
subtitle:   `strdup` 崩溃与 `wrap.sh` 切换的两条短记录
date:       2026-04-24
author:     BY
header-img: img/post-bg-debug.png
catalog: true
tags:
    - Android
    - HWASan
    - Sanitizer
---

>把原始笔记里仅剩的两条结论整理出来，避免下次排查时只看到零散命令却想不起上下文。

## 1. `strdup` 相关崩溃记录

原始备注里保留的是一条与 `strdup` 相关的 crash 线索：

```text
https://github.com/llvm/llvm-project/issues/5932
```

因此如果在 HWASan / ASan 环境里看到和 `strdup` 接近的异常，可以先把它当作一个排查方向，而不是只盯着业务代码。

原始笔记里还给过一个临时替代写法：

```c
#define MY_STRDUP(s) ({ \
    char *p = malloc(strlen(s) + 1); \
    if (p) strcpy(p, s); \
    p; \
})
```

这个替代方式的意义只是为了快速验证“问题是否和当前 `strdup` 路径有关”，不代表所有场景都应该长期用宏替换标准库接口。

## 2. `wrap.sh` 切换记录

原始命令只记了两行：

```bash
cp hwasan.sh wrap.sh
cp asan.sh wrap.sh
```

可以把它理解为一条很短的实验记录：在不同 sanitizer 方案之间切换时，曾通过替换 `wrap.sh` 的内容来控制启动方式。

整理后保留的使用提醒是：

- 如果当前验证目标是 HWASan，就确认 `wrap.sh` 实际对应的是 `hwasan.sh`
- 如果当前验证目标是 ASan，就确认 `wrap.sh` 没有残留 HWASan 的旧配置
- 遇到启动失败时，优先检查包装脚本和当前构建链路是否一致

## 3. 回看这份笔记时优先确认什么

这篇记录本身很短，真正有用的是提醒自己先核对下面几项：

1. 当前设备与 ABI 是否真的支持目标 sanitizer
2. 崩溃点是不是落在 libc / `strdup` 这类公共接口附近
3. `wrap.sh` 是否和当前准备测试的 sanitizer 类型一致

如果需要更完整的背景，可以结合《Address Sanitizer 使用笔记》一起看。
