---
layout:     post
title:      Ninja 与 CMake 速记
subtitle:   安装 Ninja 后，如何确认工程已切到 Ninja 生成器
date:       2026-04-25
author:     BY
header-img: img/post-bg-unix-linux.jpg
catalog: true
tags:
    - Ninja
    - CMake
    - Linux
---

>原始内容主要想记住一件事：装好 Ninja 之后，用 CMake 配置工程时可以直接生成 `.ninja` 构建文件。

## 1. 先确认关注点

这份笔记不是完整教程，核心只是为了回看时快速想起：

- 环境：Ubuntu
- 编辑器场景：VSCode + clang
- 目标：让 CMake 使用 Ninja，而不是传统 Makefile

## 2. 装好 Ninja 后怎么看是否生效

原始记录里的关键结论是：

>安装完成 Ninja 后，直接用 CMake 配置工程，如果配置正确，`build` 目录下会生成 `.ninja` 相关文件。

也就是说，回看时最重要的不是背命令，而是记住“**生成结果**”：

- 如果构建目录里出现 `build.ninja`
- 说明当前工程已经走到了 Ninja 生成器

## 3. 这篇记录真正想保留什么

当时留下的上下文比较少，但至少可以保留下面三个检查点：

1. 本机已经安装 Ninja
2. CMake 配置阶段没有退回到别的生成器
3. `build` 目录里确实生成了 `.ninja` 文件

## 4. 参考链接

```text
https://zhongpan.tech/2019/06/26/008-cmake-with-ninja/
```

## 5. 环境备注

原始笔记里保留的版本信息是：

```text
cmake 3.24.1
```
