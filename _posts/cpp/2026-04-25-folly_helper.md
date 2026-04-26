---
layout:     post
title:      folly 阅读笔记：架构相关的几条记录
subtitle:   crc32 / memcpy / 编译入口与待补的 barrier.h
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - folly
    - C++
    - Performance
---

>原始笔记是几条零散记录，这里只做分节整理，原始信息基本保留。

## crc32 的目标平台

```text
folly 主要针对 aarch64（Android、Linux）和 x86_64 进行优化。
ceph  针对 arm、aarch64、x86_64 优化（见 simd.cmake 文件）。
```

阅读时如果想找 SIMD 相关入口，可以从两边的 `simd.cmake` / 各自 arch 目录下手。

## memcpy / memset 的实现

```text
针对 x86_64 / aarch64 都做了优化：

- x86_64 下用 memcpy.S，hook 了 memcpy。
- aarch64 下用 memcpy_select_aarch64.cpp，hook 了 memcpy。
```

## 编译

folly 推荐用自带的 `getdeps.py` 拉依赖并构建：

```bash
python3 ./build/fbcode_builder/getdeps.py \
    --allow-system-packages \
    --scratch-path /home/ubuntu/folly_install \
    build
```

`--scratch-path` 指定中间产物和依赖落盘位置，方便清理。

## barrier.h

待补：当时只标了文件名，还没整理细节。后续可以围绕 folly 的同步原语（`Barrier`、`Baton`、`SaturatingSemaphore` 等）一起整理。

## 后续可补的方向

- folly 中常用 helper（`Function`、`Optional`、`Expected` 等）的速查
- folly + jemalloc / mimalloc 的搭配建议
- 在自己工程里以源码方式集成 folly 的最小可行 CMake 配置
