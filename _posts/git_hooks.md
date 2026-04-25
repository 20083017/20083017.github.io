---
layout:     post
title:      用 CMake 自动安装 git pre-commit 钩子
subtitle:   把 clang-format / pre-commit 的手动配置流程包成 CMake 步骤
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Git
    - CMake
    - 工程化
---

>原始笔记是"手动配置 + CMake 自动配置"两段命令拼接而成，没有标题层级。这里按"手动 / 自动"两块拆开，配置文件原样保留。

## 当前保留内容

### 1. 手动配置 pre-commit

`clang-format`、`pre-commit` 都可以通过 `pip` 安装，安装完成后在项目根目录新建 `.pre-commit-config.yaml`：

```
repos:
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.0.1
    hooks:
    -   id: trailing-whitespace
    -   id: check-added-large-files
    -   id: check-merge-conflict
    -   id: end-of-file-fixer

-   repo: https://github.com/pocc/pre-commit-hooks
    rev: v1.3.4
    hooks:
    -   id: clang-format
        args: [--style=File]
```

### 2. 通过 CMake 自动配置 pre-commit

在团队协作中很难要求所有人都手动安装钩子，特别是新人加入时。所以希望工程在初始化时自动安装 `clang-format`、`pre-commit`，并自动执行 `pre-commit install` 把钩子放到每个开发者仓库的 `.git/hooks` 目录下。

```
# Pre-commit hooks
IF (NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/.git/hooks/pre-commit)
    # FIND_PACKAGE(Python3 COMPONENTS Interpreter Development)
    IF (POLICY CMP0094)  # https://cmake.org/cmake/help/latest/policy/CMP0094.html
        CMAKE_POLICY(SET CMP0094 NEW)  # FindPython should return the first matching Python
    ENDIF ()
    # needed on GitHub Actions CI: actions/setup-python does not touch registry/frameworks on Windows/macOS
    # this mirrors PythonInterp behavior which did not consult registry/frameworks first
    IF (NOT DEFINED Python_FIND_REGISTRY)
        SET(Python_FIND_REGISTRY "LAST")
    ENDIF ()
    IF (NOT DEFINED Python_FIND_FRAMEWORK)
        SET(Python_FIND_FRAMEWORK "LAST")
    ENDIF ()
    FIND_PACKAGE(Python REQUIRED COMPONENTS Interpreter)
    MESSAGE(STATUS "Python executable: ${Python_EXECUTABLE}")
    EXECUTE_PROCESS(COMMAND sudo ${Python_EXECUTABLE} -m pip install clang-format pre-commit)
    EXECUTE_PROCESS(COMMAND pre-commit install WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
ENDIF ()
```

## 后续可补的方向

- `sudo pip install` 在 CI / 受限环境下会失败，补一份 venv 版本
- 与 `clang-tidy`、`cmake-format`、`commitizen` 等更多钩子组合的配置
- 在 Windows / macOS 下首次安装时常见的报错与解决办法
