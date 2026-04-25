---
layout:     post
title:      Protobuf 使用笔记整理
subtitle:   代码生成、lite 运行时与链接方式速查
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Protobuf
    - C++
    - Build
---

>把原始笔记里分散的生成命令、`protobuf-lite` 说明和静动态链接注意事项整理到一起，方便后续回看。

## 生成 `pb.cc` / `pb.h`

最基础的生成命令是：

```bash
protoc -I=<proto目录> --cpp_out=<输出目录> <proto文件>
```

例如：

```bash
protoc -I=./proto --cpp_out=./gen demo.proto
```

如果忘了参数，可以先看帮助：

```bash
protoc -h
```

## `-fPIC`

如果最终要把生成代码放进动态库，通常要留意位置无关代码：

```bash
bazel build -c opt --copt '-fPIC' :protobuf_nowkt --enable_bzlmod
```

## `protobuf-lite`

原始笔记里最重要的点是 `optimize_for = LITE_RUNTIME;`。

```proto
option optimize_for = LITE_RUNTIME;
```

可以把三种模式先粗略理解成：

- `SPEED`：默认模式，运行效率优先
- `CODE_SIZE`：更关心体积
- `LITE_RUNTIME`：牺牲反射能力，换更轻的运行时和更小体积

整理后更适合记住下面这几条：

1. `LITE_RUNTIME` 常用于资源更紧张的场景
2. C++ 侧一般链接 `libprotobuf-lite`
3. Java 侧一般使用 lite 版本 jar
4. 如果你依赖完整反射能力，就不要直接切到 lite

## 静态库还是动态库

这部分原始内容比较长，收敛后重点是：

### 更偏向静态链接的场景

- 你的项目本身是动态库，但**公开接口不暴露 protobuf 类型**
- 你想减少跨动态库传递 protobuf 对象的风险

### 必须谨慎动态链接的场景

- 你的公开接口直接暴露 protobuf 符号
- 需要跨 DLL / so 传递 protobuf 对象
- 运行环境里可能存在多个 protobuf 副本

### 主要风险

- 不同动态库里各自带了一份 protobuf 运行时
- 对象在 A 库创建、却在 B 库销毁
- Windows 下还要额外处理 `PROTOBUF_USE_DLLS`、CRT 链接方式等问题

所以更实用的经验是：**只要涉及跨模块边界传递 protobuf 对象，就先把链接模型想清楚，再决定静态还是动态。**

## 一个自动生成脚本示例

下面这段脚本用于在本地重新生成 `.pb.cc/.pb.h`，并只在内容变化时覆盖原文件。

```bash
#!/usr/bin/env bash

ROOT_PATH=$(pwd)/..
echo "ROOT_PATH is ${ROOT_PATH}"

if [ $# -ne 2 ]; then
  echo "Usage: $0 <protoc-relative-path> <protobuf-version-dir>"
  exit 1
fi

PROTOC=${ROOT_PATH}/$1/protoc
echo "PROTOC PATH is ${PROTOC}"
echo "LIB Version is $2"

sed -i "s#set(THIRD_PROTOBUF_PATH \"\${THIRD_PATH}/protobuf-.*\")#set(THIRD_PROTOBUF_PATH \"\${THIRD_PATH}/$2\")#" \
  ${ROOT_PATH}/CMakeLists.txt

declare -a RUNTIME_PROTO_FILES=(
  ${ROOT_PATH}/runtime/services/core/networking/auth/src/auth.proto
  ${ROOT_PATH}/runtime/services/core/networking/proto/networking.proto
)

TMP=$(mktemp -d)
echo "tmp is $TMP"

for PROTO_FILE in "${RUNTIME_PROTO_FILES[@]}"; do
  pathname=$(dirname "$PROTO_FILE")
  basename=$(basename "$PROTO_FILE")
  "$PROTOC" -I="$pathname" --cpp_out="$TMP" "$basename"
done

for PROTO_FILE in "${RUNTIME_PROTO_FILES[@]}"; do
  filename=$(basename "$PROTO_FILE" .proto)
  base_name="${PROTO_FILE%.*}"

  ! diff -q "${base_name}.pb.cc" "$TMP/${filename}.pb.cc" >/dev/null && \
    cp "$TMP/${filename}.pb.cc" "${base_name}.pb.cc"

  ! diff -q "${base_name}.pb.h" "$TMP/${filename}.pb.h" >/dev/null && \
    cp "$TMP/${filename}.pb.h" "${base_name}.pb.h"
done

rm -rf "$TMP"
echo "Generating descriptor protos done..."
```

## CMake 生成示例

如果项目本身用 CMake，可以把 proto 生成动作收口到函数里：

```cmake
function(lyra_protobuf_generate_cpp TARGET_NAME CPP_OUT_PATH H_OUT_PATH PROTO_PATH)
  file(GLOB_RECURSE PROTO_FILES "${PROTO_PATH}/*.proto")

  foreach(FILE ${PROTO_FILES})
    get_filename_component(FILE_WE ${FILE} NAME_WE)

    add_custom_command(
      OUTPUT ${H_OUT_PATH}/${FILE_WE}.pb.h ${CPP_OUT_PATH}/${FILE_WE}.pb.cc
      COMMAND ${PROTOBUF_PROTOC_EXECUTABLE}
              --proto_path=${PROTO_PATH}
              --cpp_out=${CPP_OUT_PATH}
              ${FILE_WE}.proto
      DEPENDS ${FILE}
      WORKING_DIRECTORY ${PROTO_PATH}
    )

    set_source_files_properties(
      ${H_OUT_PATH}/${FILE_WE}.pb.h
      ${CPP_OUT_PATH}/${FILE_WE}.pb.cc
      PROPERTIES GENERATED TRUE)

    target_sources(${TARGET_NAME} PRIVATE ${CPP_OUT_PATH}/${FILE_WE}.pb.cc)
  endforeach()
endfunction()
```

## 整理后的使用建议

- 先决定链接边界，再决定 protobuf 版本与链接方式
- 需要减体积时，再评估 `LITE_RUNTIME`
- 自动生成脚本最好做成“内容不变就不覆盖”
- 如果 proto 生成已经接入 CMake，就尽量不要再维护一套手工命令和一套脚本逻辑
