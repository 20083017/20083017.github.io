---
layout:     post
title:      C++ 开发遇到的坑
subtitle:   原始字符串、std::thread 崩溃、链接错误、循环依赖与静态对象初始化顺序
date:       2022-09-08
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - Linker
    - Thread
    - Pitfalls
---

>原始笔记里把几条 C++ 踩坑记录散乱地堆在一起，这里按「语法 / 线程 / 链接 / 生命周期 / 初始化顺序」分节整理，原文结论尽量保留。

参考：

- <https://coolshell.cn/articles/11466.html>

## 1. 原始字符串字面量 `R"()"`

```cpp
const char* json = R"({ "key": "value with \"quote\"" })";
```

括号里可以放任意格式的内容，**括号本身是必须的**。
适合写正则、JSON、SQL 等需要大量转义的字符串字面量。

## 2. `std::thread` 构造函数崩溃

可能的原因：

- so 库版本不一致，导致 `std::thread` 实现 ABI 不匹配
- 同一个 `std::thread` 对象被重复赋值
- `move` 之后又被重新使用，或者在还没 join 时就被赋新值

经验做法：

- 在赋新线程之前先 `join()` 旧线程
- **不要在线程自己里 `join()` 自己**，会立即抛异常

参考问题：<https://stackoverflow.com/questions/52369320/creating-new-thread-causing-exception>

## 3. `undefined reference` 链接错误

按下面顺序排查通常更快：

1. 用 `nm` + `c++filt` 看符号是否真的存在、是不是被 mangling 成预期形式：

   ```bash
   nm libfoo.a | c++filt
   ```

2. 是不是 cmake / Makefile 漏链了某个 `.o` / `.a`。
3. 是不是头文件循环包含 / 编译单元里没看到完整定义。
4. 模板代码：定义是不是没放在头文件里，或没显式实例化。

## 4. placement new 的释放方式

`placement new` 在已分配好的内存上构造对象，析构必须**显式调用析构函数**，再释放原始内存：

```cpp
char* x = (char*)malloc(10 * sizeof(char*));
new (x) LogData();
// ... use x ...
x->~LogData();    // 显式调用析构
free(x);          // 释放原始内存
```

不要忘记析构，否则资源不会释放。

## 5. 构造 / 析构顺序的「四层境界」

>整理自 CSDN 博主 NXGG（CC 4.0 BY-SA）：<https://blog.csdn.net/norman_irsa/article/details/114754944>

总原则一句：**构造与析构的顺序相反。**

理解上可以分四层：

1. **类内成员**：成员的构造顺序 = 在类中声明的顺序，与初始化列表里的顺序无关。
2. **基类与派生类**：先基类再派生类构造，析构顺序相反。
3. **函数内局部变量**：按声明顺序构造，按相反顺序析构。
4. **静态变量**：
   - **全局静态**：跨编译单元顺序由编译器决定（一种实现是按字母）。如果有依赖关系，按依赖关系决定。
   - **局部静态**：构造时机是「执行流第一次到达定义处」。编译器通常用一个全局静态标志保证「只构造一次」，并把析构函数指针压入一个由 `doexit` 维护的栈，进程结束时按栈相反顺序析构。

### 5.1 为什么这是个坑

局部静态变量的实际构造顺序取决于运行时执行路径：

- 多线程 / 消息驱动模型下，路径不可预测
- 它们分散在代码各处，彼此之间常被忽略而存在隐含依赖

### 5.2 应对思路

- 尽量**避免使用局部静态变量**，让生命周期由开发者显式控制。
- 如果一定要用，确保它们之间**互不依赖**，可以按任意顺序构造和析构。

## 6. undefined symbol / cpp 文件生成顺序

```text
linux 命名空间问题，可能的原因：cmake cpp 文件生成顺序、循环引用？
-Wl,--whole-archive 可能会导致重定义
```

- `--whole-archive` 会把静态库里所有 `.o` 都强制链入，方便注册类工厂等场景，但容易引发同名符号重定义。
- cmake 里 `target_sources` / 静态库依赖顺序错位时，也会出现「明明声明了却 undefined」。
- 排查时先用 `nm`、`readelf -s` 确认符号实际是从哪个目标文件来的。

## 7. C++ 头文件循环依赖

C++ 头文件是历史遗留问题，常见自律守则：

0. 头文件做好 include guard，例如 `#pragma once`。
1. 尽量使用前向声明（forward declaration）：
   - namespace 中的 class 都可以前向声明
   - 模板也可以前向声明，例如：
     ```cpp
     class Foo;
     using FooPtr = std::shared_ptr<Foo>;
     ```
   - 但 nested class 无法前向声明。
2. 保证每个对外接口的头文件**独立可用**。`class A` 的 cpp 文件第一个 include 应该是 `class A` 自己的头文件。
3. 头文件 / cpp 文件配对，文件名与类名一致（模板除外）。
4. include 时使用**从 VCS 根目录开始的绝对路径**，而不是相对当前文件的路径。
5. include 按一定原则分组（本项目 / 公司库 / 第三方 C++ 库 / C++ 标准库 / 第三方 C 库 / libc），每组内按字母顺序排列。
6. 做到第 3 点之后，可以用脚本 / Doxygen 自动画出头文件依赖图，循环依赖一目了然。
7. **不要在头文件里埋雷**：不要修改 struct 默认对齐方式、不要修改编译器优化等级或警告等级。

> 这里说的「VCS 根目录」是指代码库（repository）的根目录。从根目录开始用绝对路径，可以保证不同环境下都能正确解析头文件位置。

## 8. 单例模式与静态变量初始化顺序

参考 ISO/IEC 14882-1998 §3.6.2 *Initialization of nonlocal objects*：

- **同一个编译单元内**：静态变量初始化顺序就是定义顺序。
- **跨编译单元**：未定义，具体顺序取决于编译器实现。

跨 so 的单例初始化最容易踩坑。常见做法：

- 把初始化封装成一个接口，让所有依赖方走同一个入口
- 把相关的静态变量集中到**同一个 so** 内初始化
- 优先使用动态加载（`dlopen`）+ 显式调用初始化符号的方式，让顺序由调用方掌控

![image](https://github.com/20083017/20083017.github.io/assets/8308226/a6ef22eb-7316-4114-ae24-88641fa5c124)

## 9. 后续可补的方向

- 各类「构造 / 析构顺序」实战 case，每条配最小复现
- 单例 + 共享 so 的几种典型实现对比（Meyers / call_once / dlopen）
- ABI 兼容相关坑：`std::string` SSO、libstdc++ dual ABI、`std::regex`
