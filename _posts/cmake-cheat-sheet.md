---
layout:     post
title:      CMake 速查表
subtitle:   编译选项、ccache/distcc、graphviz、version script 等常用片段
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - CMake
    - 构建
    - C++
---

>原始笔记是若干段零散的 CMake 片段，标题层级混乱、还有一段 ChatGPT 风格的中英混排说明。这里按"编译参数 / ccache / 自定义函数 / 符号导出 / 依赖图 / 强制动态库"分块整理，命令与示例原样保留。

## 当前保留内容

### 1. 并发编译 / 关闭异常与 RTTI

cmake 关闭异常和 RTTI：

```
-fno-exceptions and -fno-rtti
```

下面这种写法实际**未生效**（仅作反例记录，需要确认是否在合适的目标和阶段被读入）：

```
   set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DOS_POSIX -DOS_ANDROID -DOS_LINUX -DMULTITHREADED_BUILD=4")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DOS_POSIX -DOS_ANDROID -DOS_LINUX -DMULTITHREADED_BUILD=4")
```

### 2. 指定编译器

```
cmake .. -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DCMAKE_C_COMPILER=/usr/bin/clang
```

### 3. ccache（Windows）

安装 ccache 后将其添加到环境变量（`ccache` 所在目录），执行 `ccache --help` 自检即可。无需其他设置就已经生效。

![image](https://github.com/20083017/20083017.github.io/assets/8308226/87df41e7-bd29-44ee-871e-4716b397fb81)

![image](https://github.com/20083017/20083017.github.io/assets/8308226/6fe0198f-e1a5-41eb-8c2e-152d8ab5a303)

### 4. ccache + distcc

`distcc` 是分布式编译工具，与 ccache 组合可以"本地缓存命中 + 未命中分发到远端"。

### 5. 自定义按扩展名收集源文件的函数

```
# add only ext(.cpp .cxx .cc etc) files in the path 
# Usage:
#   lyra_aux_source_directory_ex(<PROTO_PATH> <OUT_SRCS>)
function(lyra_aux_source_directory_ex ext PROTO_PATH OUT_SRCS)
  file(GLOB SRC_FILES "${PROTO_PATH}/*${ext}")
  list(APPEND ${OUT_SRCS} ${SRC_FILES})
  set(${OUT_SRCS} ${${OUT_SRCS}} PARENT_SCOPE)
endfunction()
```

### 6. 导出符号表（version script）

参考：<https://tech.meituan.com/2022/06/02/meituans-technical-exploration-and-practice-of-android-so-volume-optimization.html>

全局链接选项：

```
--version-script 全局链接选项
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--version-script=${CMAKE_SOURCE_DIR}/version.map")
```

对某个目标生效：

```
add_library(mylib SHARED mylib.c)
set_target_properties(mylib PROPERTIES LINK_FLAGS "-Wl,--version-script=${CMAKE_SOURCE_DIR}/version.map")
```

> 要在 CMake 中为特定目标启用 version script，可以使用 `set_target_properties` 命令并设置 `LINK_FLAGS` 属性。例如，假设有一个名为 `my_target` 的目标，并且想要使用名为 `my_version_script` 的版本脚本文件，则可以使用以下命令：

```
set_target_properties(my_target PROPERTIES LINK_FLAGS "-Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/my_version_script")
```

> 这将为 `my_target` 目标设置链接标志，以便在链接时使用 `my_version_script` 版本脚本文件。`-Wl` 选项用于将选项传递给链接器。`CMAKE_CURRENT_SOURCE_DIR` 变量包含当前正在处理的 `CMakeLists.txt` 文件的目录路径。

### 7. graphviz：可视化目标依赖

```
cmake --graphviz=foo.dot   # 添加配置项
dot -Tpng foo.dot -o foo.png   # 转 png
```

### 8. 强制使用动态库

```
add_dependencies(${TARGET_NAME} micontinuity)
if(TARGET micontinuity_so)
    add_library(micontinuity_so SHARED IMPORTED)
    message("CMAKE_INSTALL_LIBDIR is "
        "${ROOT_PATH}/cmake-build-script/linux-release/router-rc01/runtime/services/libmicontinuity.so")
    set_target_properties(micontinuity_so PROPERTIES IMPORTED_LOCATION
        "${ROOT_PATH}/cmake-build-script/linux-release/router-rc01/runtime/services/libmicontinuity.so")
endif()
```

## 后续可补的方向

- 整理 `CMAKE_*_FLAGS`、`add_compile_options`、`target_compile_options` 在不同生效范围下的优先级与坑点。
- 给出一个最小可复现的 graphviz 依赖图样例，配合截图说明如何快速找到环依赖。
- 把 ccache + distcc 的一键脚本沉淀下来，记录命中率与远端节点配置经验。
