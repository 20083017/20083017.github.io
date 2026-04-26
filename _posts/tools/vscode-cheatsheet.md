---
layout:     post
title:      VS Code 配置整理
subtitle:   插件清单、clangd / IWYU / lldb / Bash Debug 配置与一份个人 settings.json
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - VSCode
    - clangd
    - lldb
    - C++
---

>原始笔记把插件清单、clangd 参数、各种 launch / settings 片段全部堆在一起。这里按「插件 / C++ 工具链 / 调试 / settings.json」分节整理，原始片段尽量保留。
>
>参考：<https://blog.csdn.net/witton/article/details/130944663>

## 1. 常用插件清单

实际使用中并不是每个插件都同样高频，下面表格里 `frequency` 一栏标的是个人主观强度。

![C9iOkmPCZB](https://github.com/20083017/20083017.github.io/assets/8308226/29e7540d-f683-47bc-bbd8-8a87d75371d2)

|     | 插件                       | frequency | 备注                          |
| :-- | :------------------------ | :-------: | :---------------------------- |
|  1. | Bash Debug                |           |                               |
|  2. | Bazel                     | low       |                               |
|  3. | C/C++ (Microsoft)         | high      |                               |
|  4. | Clang-tidy Linter         | high      |                               |
|  5. | clangd                    |           | 主力 LSP                       |
|  6. | cmake                     | low       |                               |
|  7. | cmake tools               | high      |                               |
|  8. | cmake integration         | high      |                               |
|  9. | cmake-format              |           |                               |
| 10. | CodeLLDB                  | low       |                               |
| 11. | git graph                 | high      |                               |
| 12. | gitlens                   | high      |                               |
| 13. | shell                     |           |                               |
| 14. | makefile Tools            | low       | 需 `compile_commands.json`     |
| 15. | include what you use      |           | 需 `compile_commands.json`     |
| 16. | clang-format              |           | 需 `compile_commands.json`     |
| 17. | todo-tree                 |           |                               |
| 18. | Bracket Pair Colorizer    |           | 新版 VS Code 已内置             |
| 19. | markdownlint              |           |                               |
| 20. | Markdown All in One       |           |                               |

## 2. C++ 工具链相关插件配置

### 2.1 IWYU（include-what-you-use）

```bash
sudo apt install iwyu
```

`settings.json`：

```json
{
  "iwyu.exe": "/usr/bin/iwyu",
  "iwyu.compile_commands": "${workspaceFolder}/build/compile_commands.json"
}
```

### 2.2 makefile Tools

```json
{
  "makefile.compileCommandsPath": ".vscode/compile_commands.json"
}
```

### 2.3 clangd 安装与基础参数

依赖（一次性安装）：

```bash
sudo apt install clang clangd lldb cmake
```

简单说明：

- **clang**：C / C++ / Objective-C 的编译器前端（LLVM 项目的一部分）
- **clangd**：基于 clang 的语言服务器，提供补全、语义分析、跳转、查找引用、重构等
- **lldb**：LLVM 项目的调试器，功能与 GDB 类似
- **cmake**：跨平台开源构建工具

最小可用的 clangd 启动参数：

```text
--compile-commands-dir=${workspaceFolder}
--background-index
--completion-style=detailed
--header-insertion=never
--log=info
```

也可以在「clangd 工具绝对路径」一栏显式指向 `clangd` 二进制：

![image](https://github.com/user-attachments/assets/1d63a602-343c-435a-a9ea-193aa9335bdc)

### 2.4 多工具链跳转配置（`--query-driver`）

如果项目里同时用到本机 clang/gcc 和某个 SDK 的交叉编译器，需要把它们都告诉 clangd：

```text
--query-driver=/usr/bin/clang++,
              /usr/bin/**/clang-*,
              /bin/clang,
              /bin/clang++,
              /usr/bin/gcc,
              /usr/bin/g++,
              /opt/petalinux/2019.2/sysroots/x86_64-petalinux-linux/usr/bin/arm-xilinx-linux/arm-xilinx-linux-gcc,
              /opt/petalinux/2019.2/sysroots/x86_64-petalinux-linux/usr/bin/arm-xilinx-linux/arm-xilinx-linux-g++,
              /opt/petalinux/2021.2/sysroots/x86_64-petalinux-linux/usr/bin/aarch64-xilinx-linux/aarch64-xilinx-linux-gcc,
              /opt/petalinux/2021.2/sysroots/x86_64-petalinux-linux/usr/bin/aarch64-xilinx-linux/aarch64-xilinx-linux-g++
```

> 没列进来的工具链，clangd 会拒绝从对应 `compile_commands.json` 条目里抽参数，导致跳转失败。

`.vscode/settings.json` 完整一条样例：

![image](https://github.com/user-attachments/assets/633352c0-971c-4544-b277-17c49a87e009)

```json
{
  "clangd.arguments": [
    "--compile-commands-dir=/home/build/build",
    "--background-index",
    "--completion-style=detailed",
    "--header-insertion=never",
    "--log=info",
    "--query-driver=/usr/bin/clang++,/usr/bin/**/clang-*,/bin/clang,/bin/clang++,/usr/bin/gcc,/usr/bin/g++,/opt/petalinux/2019.2/sysroots/x86_64-petalinux-linux/usr/bin/arm-xilinx-linux/arm-xilinx-linux-gcc,/opt/petalinux/2019.2/sysroots/x86_64-petalinux-linux/usr/bin/arm-xilinx-linux/arm-xilinx-linux-g++,/opt/petalinux/2021.2/sysroots/x86_64-petalinux-linux/usr/bin/aarch64-xilinx-linux/aarch64-xilinx-linux-gcc,/opt/petalinux/2021.2/sysroots/x86_64-petalinux-linux/usr/bin/aarch64-xilinx-linux/aarch64-xilinx-linux-g++"
  ]
}
```

### 2.5 一份「全开」版的 clangd 参数

适合长期常驻、需要补全 + 静态检查 + 后台索引的工程：

```jsonc
{
  // 开启粘贴 / 输入时的自动格式化
  "editor.formatOnPaste": true,
  "editor.formatOnType": true,

  // 让 Microsoft C/C++ 插件不和 clangd 抢工作
  "C_Cpp.errorSquiggles": "Disabled",
  "C_Cpp.intelliSenseEngineFallback": "Disabled",
  "C_Cpp.intelliSenseEngine": "Disabled",

  "clangd.path": "/usr/bin/clangd",
  "clangd.arguments": [
    "--compile-commands-dir=${workspaceFolder}/build",
    "--log=verbose",
    "--pretty",
    "--all-scopes-completion",
    "--completion-style=bundled",
    "--cross-file-rename",
    "--header-insertion=iwyu",
    "--header-insertion-decorators",
    "--background-index",
    "--clang-tidy",
    "--clang-tidy-checks=cppcoreguidelines-*,performance-*,bugprone-*,portability-*,modernize-*,google-*",
    // "--fallback-style=file",
    "-j=2",
    // pch 优化的位置：memory 占内存但更快；板子上推荐 disk
    "--pch-storage=disk",
    "--function-arg-placeholders=false",
    "--compile-commands-dir=build"
  ]
}
```

也可以使用更精简的版本，明确指定 driver：

```json
{
  "clangd.path": "/usr/bin/clangd-12",
  "clangd.arguments": [
    "--clang-tidy",
    "--clang-tidy-checks=cppcoreguidelines-*,performance-*,bugprone-*,portability-*,modernize-*,google-*",
    "--query-driver=/usr/bin/clang++"
  ]
}
```

> 配 `--query-driver` 时，路径要参考 `which clang++` 的真实路径。

### 2.6 一些工程上的小技巧

- 想以管理员身份打开 VS Code（需要写受保护目录）：
  ```bash
  code --user-data-dir="."
  ```
- 在使用 clangd 时建议**关闭 cmaketools 自动识别 `CMakeLists.txt` 变化**的能力，避免和 clangd 后台索引互相抢资源。
- `cache` 类参数可以提升首次跳转速度，但配不当会导致跳不动；遇到这种情况优先把 cache 清掉重建索引。

## 3. 调试器配置

### 3.1 LLDB（`launch.json`）

```jsonc
{
  "name": "(lldb) 启动",
  "type": "cppdbg",
  "request": "launch",
  "program": "${workspaceFolder}/build/t",
  "args": [],
  "stopAtEntry": false,
  "cwd": "${fileDirname}",
  "environment": [],
  "externalConsole": false,
  "MIMode": "lldb",
  "miDebuggerPath": "/usr/bin/lldb-mi",
  "setupCommands": [
    {
      "description": "为 gdb 启用整齐打印",
      "text": "-enable-pretty-printing",
      "ignoreFailures": true
    },
    {
      "description": "将反汇编风格设置为 Intel",
      "text": "setting set target.x86-disassembly-flavor intel",
      "ignoreFailures": true
    }
  ]
}
```

依赖：

```bash
sudo apt install liblldb-15-dev
```

### 3.2 LLDB 行为类配置（`settings.json`）

```jsonc
{
  // LLDB 指令自动补全
  "lldb.commandCompletions": true,
  // LLDB 指针显示解引用内容
  "lldb.dereferencePointers": true,
  // 鼠标悬停在变量上时预览变量值
  "lldb.evaluateForHovers": true,
  // LLDB 监视表达式的默认类型
  "lldb.launch.expressions": "simple",
  // LLDB 不显示汇编代码
  "lldb.showDisassembly": "never",
  // 生成更详细的日志
  "lldb.verboseLogging": true
}
```

### 3.3 Bash Debug

```jsonc
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "bashdb",
      "request": "launch",
      "name": "Bash-Debug (simplest configuration)",
      "program": "/home/liuquan6/project/test/miconnect/native/build.sh",
      "args": ["-c", "make", "-t", "debug", "-p", "linux", "-a", "camera-pro3", "rebuild"]
    }
  ]
}
```

> 原始笔记里这里漏了几个逗号，整理时已补齐。

## 4. 个人 settings.json 模板

下面是一份长期使用的个人配置，按需挑选。

```jsonc
{
  // 编辑器外观与滚动
  "editor.smoothScrolling": true,
  "editor.cursorBlinking": "expand",
  "editor.cursorSmoothCaretAnimation": "on",
  "editor.hover.above": false,
  "workbench.list.smoothScrolling": true,
  "editor.mouseWheelZoom": true,
  "editor.wordWrap": "on",
  "editor.lineHeight": 1.5,
  "editor.fontSize": 11,
  "editor.fontFamily": "Consolas, '等线', monospace",
  "editor.fastScrollSensitivity": 10,

  // 括号、补全
  "editor.guides.bracketPairs": true,
  "editor.bracketPairColorization.enabled": true,
  "editor.suggest.snippetsPreventQuickSuggestions": false,
  "editor.acceptSuggestionOnEnter": "smart",
  "editor.suggestSelection": "recentlyUsedByPrefix",
  "editor.suggest.insertMode": "replace",

  // 不要把中文标到「非基础 ASCII」黄框里
  "editor.unicodeHighlight.nonBasicASCII": false,

  // 自动闭合
  "editor.autoClosingBrackets": "beforeWhitespace",
  "editor.autoClosingDelete": "always",
  "editor.autoClosingOvertype": "always",
  "editor.autoClosingQuotes": "beforeWhitespace",

  // 缩进
  "editor.detectIndentation": false,
  "editor.tabSize": 4,
  "editor.suggest.preview": true,

  // 代码格式化（按需开启）
  // "editor.formatOnSave": true,
  // "editor.formatOnSaveMode": "modifications",
  // "editor.defaultFormatter": "xaver.clang-format",
  // "clang-format.style": "file",
  // "clang-format.fallbackStyle": "LLVM",

  // 构建系统
  // "cmake.configureOnOpen": true,
  "cmake.generator": "Ninja",

  // 自动保存 / 索引
  "files.autoSave": "onWindowChange",
  "search.followSymlinks": false,

  // 窗口与对话框
  "window.dialogStyle": "custom",
  "window.density.editorTabHeight": "compact",
  "debug.showBreakpointsInOverviewRuler": true,

  // 资源管理器
  "explorer.compactFolders": true,
  "notebook.compactView": true,

  // HTML / 链接编辑
  "editor.linkedEditing": true,
  "html.format.wrapAttributes": "preserve",
  "html.format.wrapLineLength": 80,
  // "editor.rulers": [80],
  "html.format.indentHandlebars": true,

  // 文件
  "files.autoGuessEncoding": true,
  "files.trimTrailingWhitespace": true,

  // 搜索
  "search.searchEditor.singleClickBehaviour": "peekDefinition",
  "editor.stickyScroll.enabled": true,
  "workbench.tree.enableStickyScroll": true,

  // 主题与图标
  "workbench.iconTheme": "material-icon-theme",
  "workbench.list.fastScrollSensitivity": 10,
  "workbench.colorTheme": "Pretty Dark Theme",
  "workbench.activityBar.location": "bottom",
  "editor.foldingImportsByDefault": true,
  "workbench.startupEditor": "none",

  // 内联补全
  "editor.quickSuggestions": {
    "other": true,
    "comments": true,
    "strings": true
  },

  // Live Server
  "liveServer.settings.donotShowInfoMsg": true,
  "liveServer.settings.donotVerifyTags": true,

  // 字符与小地图
  "editor.wordSeparators": "`~!@%^&*()=+[{]}\\|;:'\",.<>/?（），。；：",
  "editor.minimap.enabled": false,
  "editor.foldingStrategy": "indentation",

  // 更新 & 排除
  "update.mode": "manual",
  "search.exclude": {
    "**/build": true,
    "**/build/**": true,
    "**/.*": true,
    "**/.*/**": true,
    "**/.vscode": true,
    "**/.vscode/**": true
  },

  // 大纲
  "notebook.outline.showCodeCellSymbols": false,
  "outline.showArrays": false,
  "outline.showBooleans": false,
  "outline.showConstants": false,
  "outline.showNull": false,
  "outline.showNumbers": false,
  "outline.showObjects": false,
  "outline.showOperators": false,
  "outline.showPackages": false,
  "outline.showStructs": false,
  "outline.showEvents": false,
  "outline.showFields": false,
  "outline.showFiles": false,
  "outline.showProperties": false,
  "outline.showEnumMembers": false,
  "outline.showEnums": false,
  "outline.showInterfaces": false,
  "outline.showKeys": false,
  "outline.showTypeParameters": false
}
```

## 5. 后续可补的方向

- VS Code Remote 系列（Remote-SSH / Remote-Containers / WSL）配置
- 更系统的 clang-tidy 检查项分组与白名单管理
- 配合 `compile_commands.json` 的多工程切换工作流
