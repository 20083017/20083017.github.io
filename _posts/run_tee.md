---
layout:     post
title:      OP-TEE 运行与构建笔记整理
subtitle:   QEMU 运行、9p 挂载与中国大陆网络环境下的构建脚本
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - OP-TEE
    - QEMU
    - ARM
---

>把原始笔记中的“怎么跑起来”和“一键构建脚本”拆开整理，先保留最有复用价值的路径。

## 先把环境跑起来

原始记录里最短的运行路径是：

```bash
cd optee/build
make run
```

然后另开一个终端连接：

```bash
telnet localhost 54320
```

如果 QEMU 卡在 monitor，需要在 monitor 窗口里执行：

```text
continue
```

## 挂载宿主机目录

原始记录里用的是 9p：

```bash
mkdir -p /mnt/host
mount -t 9p -o trans=virtio host0 /mnt/host
```

挂载后，再跑 `xtest` 看效果。

## 一键构建脚本的目标

这份脚本主要想解决的是：中国大陆网络环境下，尽量稳定地把 OP-TEE 依赖和源码拉起来。

原始脚本里想覆盖的点包括：

- `repo` 工具从清华镜像下载
- manifest 走 GitHub 官方仓库
- 支持断点续传和增量构建
- 自动安装常用依赖
- 修复 multiarch 头文件链接
- 工具链缺失时自动重建

## 脚本里最重要的配置项

```bash
WORK_DIR="$HOME/optee"
BUILD_DIR="$WORK_DIR/build"
TOOLCHAINS_DIR="$WORK_DIR/toolchains"
AARCH64_GCC="$TOOLCHAINS_DIR/aarch64/bin/aarch64-linux-gnu-gcc"
AARCH32_GCC="$TOOLCHAINS_DIR/arm/bin/arm-linux-gnueabihf-gcc"

OPTEE_RELEASE="3.20.0"
MANIFEST_URL="https://github.com/OP-TEE/manifest.git"
MANIFEST_FILE="default.xml"
JOBS=$(nproc)

REPO_BIN_DIR="$HOME/bin"
REPO_URL_TUNA="https://mirrors.tuna.tsinghua.edu.cn/git/git-repo/"
```

## 依赖安装思路

原始脚本里依赖分成两层：

1. 基础构建工具：`git`、交叉编译器、`python3`、`curl` 等
2. OP-TEE 常用依赖：`ninja-build`、`libssl-dev`、`device-tree-compiler`、`python3-pyelftools` 等

这类脚本的核心价值不是命令本身，而是：**把“缺哪个包”这件事一次性列清楚。**

## 一个精简后的主流程

更适合回看的主流程可以概括成：

1. 检测系统环境，区分是否在 WSL
2. 配置 `repo` 走清华镜像
3. `repo init` + `repo sync` 同步 OP-TEE
4. 安装缺失依赖
5. 修复 multiarch 头文件链接
6. 检查交叉工具链是否完整
7. 缺就重建，不缺就复用

## 这篇后续还值得补什么

如果继续整理，建议再补：

- 正式的 `make toolchains` / `make run` 全流程
- `xtest` 常见失败场景
- QEMU 共享目录失效时的排查顺序
- 不同 OP-TEE 版本之间的差异
