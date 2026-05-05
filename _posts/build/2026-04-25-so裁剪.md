---
layout:     post
title:      so 裁剪笔记整理
subtitle:   从编译选项到体积分析的最小排查链路
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - ELF
    - Linker
    - Performance
---

>把原始笔记里的编译选项、静态分析和运行时观察点整理成一条更容易复用的体积排查链路。

## 先做编译期裁剪

最常用的一组组合是：

```bash
-ffunction-sections -fdata-sections -Wl,--gc-sections
```

它们的作用可以这样理解：

- `-ffunction-sections`：每个函数单独放一个 section
- `-fdata-sections`：每个全局或静态变量单独放一个 section
- `-Wl,--gc-sections`：链接时回收没有被引用的 section

如果目标是尽量减小最终可执行文件或共享库体积，这通常是第一步。

## 用 bloaty 看体积主要花在哪

```bash
bloaty -d compileunits -n 0 libmicontinuity.so > 1.txt
```

适合回答两个问题：

1. 哪些编译单元最占体积
2. 优化应该优先从哪里下手

## 用 `size -A` 做静态分析

```bash
~/.toolchain/sdk_package_MC01/toolchain/bin/aarch64-openwrt-linux-size -A ./libmicontinuity_sdk.so.1.0.4032716
```

这一步更适合直接看各段大小，例如：

- `.text`
- `.rodata`
- `.data`
- `.bss`

## 再看运行时映射

如果文件体积和进程占用看起来不一致，再补上运行时观察：

```bash
cat /proc/39625/status
cat /proc/39625/smaps
```

以及：

```bash
pmap <pid>
```

`pmap` 能快速帮你看出进程的内存映射布局，适合和 `smaps` 交叉确认。

## 导出符号控制

如果目标是减小导出符号面，原始笔记里还提到 `version_script.map`：

```map
extern "c++" {
  "class::*";
};
```

另外可以配合：

```bash
nm <binary>
c++filt <mangled_symbol>
```

用途分别是：

- `nm`：先看当前符号表里到底暴露了什么
- `c++filt`：把 C++ 符号反解成人能读的名字

## 一条整理后的排查顺序

更适合回看的顺序是：

1. 先加 section 级裁剪编译选项
2. 用 `bloaty` 看体积热点
3. 用 `size -A` 看段分布
4. 用 `smaps` / `pmap` 看运行时映射
5. 最后再考虑缩减导出符号和 ABI 暴露面
