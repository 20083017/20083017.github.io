---
layout:     post
title:      Bazel 构建备忘
subtitle:   围绕 `bzlmod` 的几个最常用命令
date:       2026-04-25
author:     BY
header-img: img/post-bg-debug.png
catalog: true
tags:
    - Bazel
    - Build
    - C++
---

>原始笔记只留下了几条命令，这里把它整理成一份最小回看版：先构建目标，再看依赖关系，最后补充常见编译选项。

## 1. 先直接构建目标

```bash
bazel build :protoc :protobuf --enable_bzlmod
```

这条命令适合先验证两件事：

- 当前工作区能否正常启用 `bzlmod`
- `protoc` 和 `protobuf` 这两个目标是否能被顺利解析并构建

## 2. 需要看依赖关系时生成依赖图

```bash
bazel mod graph --output graph --enable_bzlmod
```

这一步适合快速回看模块依赖关系，尤其是在下面这些场景里比较有用：

- 怀疑某个模块版本被意外拉进来
- 想确认 `bzlmod` 解析后的依赖结构
- 需要先理解依赖关系，再继续排查构建问题

## 3. 需要优化产物属性时追加编译参数

```bash
bazel build -c opt --copt '-fPIC' :protoc :protobuf --enable_bzlmod
```

这里保留的两个选项分别对应：

- `-c opt`：按优化配置构建
- `--copt '-fPIC'`：给编译阶段追加 `-fPIC`

回看时要优先确认：

- 目标是否真的需要位置无关代码
- 这类 `--copt` 是临时排查用，还是应该沉到更稳定的构建配置里

## 4. 最小使用顺序

如果只是快速回忆，通常按下面顺序就够了：

1. 先跑基础构建，确认目标能不能过
2. 再看 `mod graph`，理解依赖是否符合预期
3. 最后按需要补 `-c opt` 或 `-fPIC` 这类选项
