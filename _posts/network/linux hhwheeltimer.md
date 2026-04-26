---
layout:     post
title:      Linux 内核定时器学习入口
subtitle:   先记下从 timer.c 开始读起的位置
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Linux Kernel
    - Timer
    - HHWheelTimer
---

>原始笔记只有一句指引和一张示意图，这里整理成可继续补充的占位版本。

## 当前保留内容

Linux 内核里和定时器相关的核心实现集中在：

```text
kernel/time/timer.c
```

后面再继续整理这块时，可以围绕这一份源码作为入口。

笔记里附的这张示意图保留下来：

![image](https://github.com/user-attachments/assets/010366c1-e6ff-4437-9766-1f924c750389)

## 后续可补的方向

这篇后续如果继续整理，建议至少补下面几类内容：

- 经典的 hashed hierarchical timing wheel 数据结构与原理
- Linux 内核 timer wheel 的层级结构、tick 推进方式
- 内核态 `timer_list`、`hrtimer` 与用户态 `timerfd` / `epoll` 的关系
- `folly::HHWheelTimer` 等用户态实现与内核实现的对比

当前这篇先当作一个待扩充的入口条目。
