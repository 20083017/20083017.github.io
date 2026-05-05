---
layout:     post
title:      Windows 下接入 vcpkg 备忘
subtitle:   PATH、toolchain 文件与 Boost 路径的最小记录
date:       2026-04-25
author:     BY
header-img: img/post-bg-os-metro.jpg
catalog: true
tags:
    - Windows
    - vcpkg
    - CMake
---

>原始笔记只记了几条路径，这里把它整理成一份最小接入说明：先让系统能找到 vcpkg，再让 CMake 明确使用它的 toolchain。

## 1. 先让命令行能找到 vcpkg

原始记录保留的是这条思路：

```text
把 D:\project\vcpkg 加到 PATH
```

这样做的目的，是让命令行里能直接调用 `vcpkg`，方便安装或查询包。

## 2. 在 CMake 里指定 toolchain 文件

如果工程本身走 CMake，原始笔记建议直接指定：

```cmake
set(CMAKE_TOOLCHAIN_FILE "D:/project/vcpkg/scripts/buildsystems/vcpkg.cmake")
```

回看时要记住，这一步的重点不是“把路径写进去”本身，而是：

- 告诉 CMake 当前工程依赖 vcpkg 提供的工具链配置
- 让后续 `find_package` 等流程优先走 vcpkg 安装结果

## 3. Boost 相关路径记录

原始笔记里还单独保留了一个 Windows 目录：

```text
D:\project\vcpkg\installed\x64-windows
```

这更像是当时为了 Boost 或其他库做路径确认时留下的备忘。回看时可优先用它来确认：

- 目标 triplet 是否是 `x64-windows`
- 依赖是否真的装在预期目录下
- 工程是不是把库路径指到了别的 triplet

## 4. 最小排查顺序

如果 Windows 工程接不上 vcpkg，可以先按这个顺序看：

1. `vcpkg` 命令本身能不能执行
2. `CMAKE_TOOLCHAIN_FILE` 是否指向正确脚本
3. 依赖库是否真的出现在 `installed/x64-windows` 下
