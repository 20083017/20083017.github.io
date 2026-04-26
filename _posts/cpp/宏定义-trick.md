---
layout:     post
title:      C/C++ 宏定义小技巧
subtitle:   用 MARCO_EXPAND 解决 __VA_ARGS__ 嵌套被吞参数的问题
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - Macro
    - Trick
---

>原始笔记只有一行宏定义和一张示意图，这里把背景和用法补出来，方便回看。

## 问题：`__VA_ARGS__` 在嵌套展开时会被当成单个参数

在 MSVC 等部分预处理器实现下，把 `__VA_ARGS__` 直接传给另一个宏时，可能会被整体看作 **一个** 参数，而不是按逗号拆开继续传递，导致下游宏拿到的参数个数和预期不符。

## 一个常见 workaround：再套一层展开

```cpp
#define MARCO_EXPAND(...) __VA_ARGS__
```

把要传给下游宏的 `__VA_ARGS__` 先经过一次 `MARCO_EXPAND(...)`，强制再展开一次，逗号才会重新被识别为参数分隔符。

典型用法形如：

```cpp
#define CALL(macro, args) MARCO_EXPAND(macro args)
```

笔记中附的示意图保留下来：

<img width="700" alt="image" src="https://user-images.githubusercontent.com/8308226/231113335-00264069-85b8-4c14-8c64-0390565be2c8.png">

## 后续可补的方向

- 不同编译器（GCC / Clang / MSVC）对 `__VA_ARGS__` 展开顺序的差异
- 计数宏 `PP_NARG`、`FOR_EACH` 等常见可变参宏的写法
- 使用 `BOOST_PP_*` 替代手写宏的场景
