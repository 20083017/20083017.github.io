---
layout:     post
title:      项目工程化规约：pre-commit 钩子 + 跨平台换行符
subtitle:   把 .pre-commit-config.yaml、CMake 自动安装、.gitattributes EOL 这三件事合并整理
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Git
    - CMake
    - 跨平台
    - 工程化
---

>原本是两篇散记：`git_hooks.md`（pre-commit + CMake 自动安装）与 `跨平台.md`（行尾 EOL 规约）。两边都属于"项目根目录里的全员一致工程化约定"，这次合并到一起，按"pre-commit 钩子 / 跨平台换行符"两大块组织，原文要点和命令保持原样。

## 当前保留内容

### A. pre-commit 钩子

#### A.1 手动配置 pre-commit

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

#### A.2 通过 CMake 自动配置 pre-commit

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

### B. 跨平台换行符（EOL）规约

#### B.1 推荐采用 LF（`\n`）作为 EOL

原因：

- Linux / macOS 默认使用 LF（`\n`）。
- Windows 默认使用 CRLF（`\r\n`），但现代编辑器（VSCode、CLion、Sublime、Notepad++）都能很好地识别 LF。
- GitHub、CI/CD、跨平台工具链都推荐 LF，能减少因 EOL 不一致导致的编译 / 补丁 / 合并冲突等问题。

#### B.2 Git 层面自动处理：`.gitattributes`

在项目根目录添加或修改 `.gitattributes`：

```
*.cpp text eol=lf
*.hpp text eol=lf
*.h   text eol=lf
*.c   text eol=lf
*.inl text eol=lf
*.cmake text eol=lf
```

这样 Git 在提交时会自动把这些文件的 EOL 转换为 LF，拉取时也保持一致。

#### B.3 编辑器设置

- **VSCode**：可设 `"files.eol": "\n"`，并用右下角 EOL 按钮批量转换。
- **CLion / IDEA**：File → Line separators → Unix and OS X (\n)。
- **Notepad++**：编辑 → EOL 转换 → 转为 UNIX 格式。

#### B.4 CMake / 工具链层面

- 一般不需要特殊设置；可以用代码格式化工具（如 `clang-format`）统一行尾。
- 如果有自动代码生成步骤，建议生成脚本里强制用 LF（如 Python 用 `open(..., newline='\n')`）。

#### B.5 总结

- **最佳实践**：用 `.gitattributes` 管控，开发工具用 LF，团队达成共识。
- **不建议**：用 CRLF，除非目标平台仅限 Windows 并且有特殊历史兼容需求。

## 后续可补的方向

### 关于 pre-commit 钩子

- `sudo pip install` 在 CI / 受限环境下会失败，补一份 venv 版本
- 与 `clang-tidy`、`cmake-format`、`commitizen` 等更多钩子组合的配置
- 在 Windows / macOS 下首次安装时常见的报错与解决办法

### 关于跨平台换行符

- `core.autocrlf` 与 `.gitattributes` 的关系，以及历史仓库切换到 LF 的迁移步骤
- 已经混入 CRLF 的文件如何批量纠正（`dos2unix` / `git add --renormalize`）
- 不同语言（Shell、Python、Markdown）EOL 不一致带来的典型问题示例

### 协同点（两块共同的扩展方向）

- 配套一份"新仓库初始化清单"：`.gitattributes` + `.gitignore` + `.pre-commit-config.yaml` + `.editorconfig` 模板
- 把 `clang-format` 与 EOL 规则放到同一份配置生成脚本里，避免互相覆盖
