---
layout:     post
title:      Templight 使用整理
subtitle:   编译期模板元编程调试的最小准备记录
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - Clang
    - Template
---

>原始笔记只记了几条编译命令和一个常见报错，这里整理成“准备环境 + 编译 + 使用提醒”的最小版本。

## 它是干什么的

Templight 更适合在下面这种场景里使用：

- 模板实例化特别深
- 编译时间异常长
- 你想看清楚到底是哪一段模板元编程把编译器拖慢了

## 编译准备

原始记录里的路径是：

1. 下载 `llvm-project`
2. 进入 `clang/tools` 目录
3. 下载 `templight` 工程
4. 回到 `llvm-project` 根目录开始配置和编译

## 配置命令

```bash
cmake -S llvm -B build -DLLVM_ENABLE_PROJECTS=clang -DCMAKE_BUILD_TYPE=Release
```

如果要显式指定 clang：

```bash
cmake -S llvm -B build \
  -DLLVM_ENABLE_PROJECTS=clang \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/usr/bin/clang \
  -DCMAKE_CXX_COMPILER=/usr/bin/clang++
```

然后进入构建目录：

```bash
cd build
make clang
```

## 一个常见报错

原始记录里保留的典型错误是：

```text
clang: error: unknown argument: '-fno-lifetime-dse'
make[2]: *** [TemplightAction.cpp.o] Error 1
make[1]: *** [obj.clangTemplight.dir/all] Error 2
make: *** [all] Error 2
```

这类问题通常说明：

- 当前编译器版本和工程期望的不一致
- 某些参数只被特定 clang / gcc 版本支持
- 混用了系统编译器和自己想要的工具链

## 原始经验里最值得保留的一点

指定 `ninja` 编译失败后，清理工程，再改回 `make` 重新编译，有时反而更容易过。

也就是说，这篇里真正的经验不是“必须用 make”，而是：**先把工具链和参数版本对齐，再决定生成器。**

## 在线替代入口

如果只是想快速看模板推导或做表达式可视化，有时在线工具更省事：

- <https://cppinsights.io/>

它不能完全替代 Templight，但很适合先做快速观察。
