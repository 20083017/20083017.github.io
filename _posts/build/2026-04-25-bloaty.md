---
layout:     post
title:      Bloaty 体积分析备忘
subtitle:   从符号、编译单元到运行时映射的最小排查入口
date:       2026-04-25
author:     BY
header-img: img/post-bg-debug.png
catalog: true
tags:
    - Linux
    - ELF
    - Bloaty
---

>把原始几条命令整理成一条最短分析链路：先看符号和编译单元，再结合段大小与进程映射判断体积主要花在哪。

## 1. 先按符号看体积占比

当你想先知道“到底是哪些函数 / 符号最占空间”时，可以直接看 `symbols` 维度：

```bash
bloaty -d symbols -n 0 libmicontinuity.so > 2.txt
```

- `-d symbols`：按符号维度展开
- `-n 0`：不限制输出条数
- `2.txt`：把结果落盘，方便后续排序或对比

## 2. 再按编译单元看体积来源

如果你已经知道问题大概出在某个模块，而不是某个具体符号，更适合切到 `compileunits`：

```bash
bloaty -d compileunits -n 0 libsimple_decoder.so > compileunits.txt
```

这一步适合回答两个问题：

- 哪个源文件 / 编译单元贡献了最多体积
- 是否某个模块整体被意外拉大了

## 3. 看各个段的占比

如果怀疑不是单个函数的问题，而是 `.text`、`.rodata`、`.data`、`.bss` 这类段整体偏大，可以直接看段级统计：

```bash
~/.toolchain/sdk_package_MC01/toolchain/bin/aarch64-openwrt-linux-size -A ./libmicontinuity_sdk.so.1.0.4032716
```

这一步更适合快速判断：

- 代码段是否明显膨胀
- 只读数据是否异常增大
- 某些静态对象是否把数据段撑大了

## 4. 结合 smaps 看运行时占用

二进制文件本身体积和进程实际映射占用不完全是一回事。
如果你要继续确认“进程里到底是哪几个库占得多”，可以再看：

```bash
cat /proc/$pid/smaps
cat /proc/$pid/status
```

更适合关注：

- 各个 so 的映射大小
- RSS / PSS 等运行时占用
- 进程整体内存状态是否和文件体积分析一致

## 5. 参考链接

```text
https://blog.csdn.net/weiwei9363/article/details/121475302
```
