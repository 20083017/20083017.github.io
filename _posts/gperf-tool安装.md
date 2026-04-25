---
layout:     post
title:      gperftools / tcmalloc 安装与使用要点
subtitle:   把版本选择、libunwind、链接方式、编译开关汇总在一处
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - 性能分析
    - tcmalloc
    - C++
---

>原始笔记是若干编号条目混在一起，包含"待确认问题"和"实操配置"两类内容。这里按"待确认 / libunwind / 链接 / 编译 / 使用"五块拆开，原文要点和命令保持原样。

## 当前保留内容

### 1. 待确认的问题

- `gperftools` 选 2.5 还是 1.7？brpc 这边需要哪个版本？
  - 参考：<https://bbs.huaweicloud.com/blogs/192035>
- `tcmalloc` 版本如何选择？
- C++ 版本是否需要 C++17？

### 2. 关于 libunwind

在 64 位 Linux 环境下，gperftools 使用 glibc 内置的 stack-unwinder 可能会引发死锁，因此官方推荐在配置和安装 gperftools 之前，先安装 `libunwind-0.99-beta`，最好就用这个版本，版本太新或太旧都可能会有问题。

即便使用 libunwind，在 64 位系统上还是会有问题，但只影响 heap-checker、heap-profiler 和 cpu-profiler，TCMalloc 不受影响，因此不再赘述，感兴趣的读者可参阅 gperftools 的 INSTALL。

如果不希望安装 libunwind，也可以用 gperftools 内置的 stack unwinder，但需要应用程序、TCMalloc 库、系统库（比如 libc）在编译时开启帧指针（frame pointer）选项。

在 x86-64 下，编译时开启帧指针选项并不是默认行为。因此需要指定 `-fno-omit-frame-pointer` 编译所有应用程序，然后在 configure 时通过 `--enable-frame-pointers` 选项使用内置的 gperftools stack unwinder。

> 关于在 VirtualBox + Ubuntu 上安装的步骤，可参考：<https://blog.csdn.net/qq_36340642/article/details/109253664>

### 3. 链接方式

```
                target_link_libraries(${TARGET_NAME}
                    -ltcmalloc
                    # tcmalloc_and_profiler  #不能同时存在
                )
```

> `tcmalloc` 与 `tcmalloc_and_profiler` 不能同时链接。

### 4. 编译配置

注意：**不能与 `lsan`、`address`（AddressSanitizer）同时使用！**

```
          set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -g -O0  -fno-omit-frame-pointer")
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g -O0  -fno-omit-frame-pointer")
```

### 5. 使用方式（针对程序不能正常退出的情况）

```
#if !defined(NDEBUG)
#include <gperftools/heap-profiler.h>
#endif

#if !defined(NDEBUG)
    HeapProfilerStart("my_program test");
#endif

#if !defined(NDEBUG)
    HeapProfilerDump("end");
#endif
```

## 后续可补的方向

- 上面"待确认"问题的最终结论与所选版本依据
- `pprof` 解析 heap / cpu profile 的常用命令清单
- 与 brpc 内置 profiler、jemalloc 的对比
- 在容器、CI 环境下使用 tcmalloc 的注意事项
