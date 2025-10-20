vscode 配置



https://blog.csdn.net/witton/article/details/130944663


### 插件安装

![C9iOkmPCZB](https://github.com/20083017/20083017.github.io/assets/8308226/29e7540d-f683-47bc-bbd8-8a87d75371d2)


|   | 插件              | frequency | others |
| :--| :---------------- | :------: | ----: |
| 2.| Bash Debug        |      |       |
| 3.| Bazel           |    low  |       |
| 4.| C/C++ Intel   |  high   |       |
| 5.| Clang-tidy Linter |  high   |       |
| 6.| clangd       |      |       |
| 7.| cmake           |    low  |       |
| 8.| cmake tools   |  high   |       |
| 9.| cmake integration |  high   |       |
| 10.| cmake-format        |      |       |
| 11.| CodeLLDB           |    low  |       |
| 12.| git graph   |  high   |       |
| 13.| gitlens |  high   |       |
| 14.| shell        |      |       |
| 15.| makefile Tools |    low  |  compile_commands.json     |
| 16.| include what you use |      |  compile_commands.json     |
| 17.| clang-format |      |  compile_commands.json     |
| 18.| todo-tree |      |       |
| 19.| Bracket Pair Colorizer |      |       |
| 20.| mark down lint |      |       |
| 21.| mark down all in one |      |       |


#### include what you see

```
apt install iwyu
```

```
"iwyu.exe": "/usr/bin/iwyu", 
"iwyu.compile_commands": "${workspaceFolder}/build/compile_commands.json"
```


#### makefile Tools
```
settings.json 配置
"makefile.compileCommandsPath":".vscode/compile_commands.json"
```

### clangd server安装

### clangd 插件配置
```
–compile-commands-dir=${workspaceFolder}
–background-index
–completion-style=detailed
–header-insertion=never
-log=info
```
clangd 工具绝对路径   

![image](https://github.com/user-attachments/assets/1d63a602-343c-435a-a9ea-193aa9335bdc)


### lldb 配置
```
{
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
		},
}

```

sudo apt install liblldb-15-dev


### 安装必要软件依赖
```
apt install clang clangd lldb cmake
clang:Clang是一种用于C、C++和Objective-C编程语言的编译器前端。它被设计为一个快速、高效和高度可定制的编译器，提供出色的诊断和错误信息。Clang是LLVM项目的一部分，LLVM是一个模块化和可重用的编译器和工具链技术集合。
clangd:clangd是一个基于Clang编译器的语言服务器，用于提供C/C++语言的代码补全、语义分析和代码导航等功能。clangd通过解析源代码并构建语法树和语义图来理解代码，并根据用户的输入提供相关的代码建议和信息。它还支持跳转到定义、查找引用、重构等功能，帮助开发人员更高效地编写和维护C/C++代码。
lldb:lldb是一个开源的调试器，用于调试C、C++、Objective-C和Swift等编程语言的应用程序。它是在LLVM项目的基础上开发的，和GDB功能类似。
cmake:CMake是一个跨平台的开源构建工具。
```

### bash debug
注意参数配置   
```
    "version": "0.2.0",
    "configurations": [
        {
            "type": "bashdb",
            "request": "launch",
            "name": "Bash-Debug (simplest configuration)",
            "program": "/home/liuquan6/project/test/miconnect/native/build.sh"
            "args": [ "-c" "make" "-t" "debug" "-p" "linux" "-a" "camera-pro3" "rebuild" ]
        }
    ]
```

### 跳转配置

 "--query-driver=/usr/bin/clang++,/usr/bin/**/clang-*,/bin/clang,/bin/clang++,/usr/bin/gcc,/usr/bin/g++,/opt/petalinux/2019.2/sysroots/x86_64-petalinux-linux/usr/bin/arm-xilinx-linux/arm-xilinx-linux-gcc,/opt/petalinux/2019.2/sysroots/x86_64-petalinux-linux/usr/bin/arm-xilinx-linux/arm-xilinx-linux-g++,/opt/petalinux/2021.2/sysroots/x86_64-petalinux-linux/usr/bin/aarch64-xilinx-linux/aarch64-xilinx-linux-gcc,/opt/petalinux/2021.2/sysroots/x86_64-petalinux-linux/usr/bin/aarch64-xilinx-linux/aarch64-xilinx-linux-g++",

创建.vscode/settings.json
![image](https://github.com/user-attachments/assets/633352c0-971c-4544-b277-17c49a87e009)



### 管理员身份运行
code --user-data-dir="."

### 关闭cmaketools插件，自动识别cmakelists.txt 变化

### 配置.vscode/settings.json

```
{
    "clangd.arguments":[
         "--compile-commands-dir=/home/build/build",
         "--background-index",
         "--completion-style=detailed",
         "--header-insertion=never",
         "--log=info",
          "--query-driver=/usr/bin/clang++,/usr/bin/**/clang-*,/bin/clang,/bin/clang++,/usr/bin/gcc,/usr/bin/g++,/opt/petalinux/2019.2/sysroots/x86_64-petalinux-linux/usr/bin/arm-xilinx-linux/arm-xilinx-linux-gcc,/opt/petalinux/2019.2/sysroots/x86_64-petalinux-linux/usr/bin/arm-xilinx-linux/arm-xilinx-linux-g++,/opt/petalinux/2021.2/sysroots/x86_64-petalinux-linux/usr/bin/aarch64-xilinx-linux/aarch64-xilinx-linux-gcc,/opt/petalinux/2021.2/sysroots/x86_64-petalinux-linux/usr/bin/aarch64-xilinx-linux/aarch64-xilinx-linux-g++",
     ]
}
```

### 配置 cache ？ 提高 索引跳转效率，不跳转？！！！
```
  // 开启粘贴保存自动格式化
  "editor.formatOnPaste": true,
  "editor.formatOnType": true,
  "C_Cpp.errorSquiggles": "Disabled",
  "C_Cpp.intelliSenseEngineFallback": "Disabled",
  "C_Cpp.intelliSenseEngine": "Disabled",
  "clangd.path": "/usr/bin/clangd",
  // Clangd 运行参数(在终端/命令行输入 clangd --help-list-hidden 可查看更多)
  "clangd.arguments": [
    // compile_commands.json 生成文件夹
    "--compile-commands-dir=${workspaceFolder}/build",
    // 让 Clangd 生成更详细的日志
    "--log=verbose",
    // 输出的 JSON 文件更美观
    "--pretty",
    // 全局补全(输入时弹出的建议将会提供 CMakeLists.txt 里配置的所有文件中可能的符号，会自动补充头文件)
    "--all-scopes-completion",
    // 建议风格：打包(重载函数只会给出一个建议）
    // 相反可以设置为detailed
    "--completion-style=bundled",
    // 跨文件重命名变量
    "--cross-file-rename",
    // 允许补充头文件
    "--header-insertion=iwyu",
    // 输入建议中，已包含头文件的项与还未包含头文件的项会以圆点加以区分
    "--header-insertion-decorators",
    // 在后台自动分析文件(基于 complie_commands，我们用CMake生成)
    "--background-index",
    // 启用 Clang-Tidy 以提供「静态检查」
    "--clang-tidy",
    // Clang-Tidy 静态检查的参数，指出按照哪些规则进行静态检查，详情见「与按照官方文档配置好的 VSCode 相比拥有的优势」
    // 参数后部分的*表示通配符
    // 在参数前加入-，如-modernize-use-trailing-return-type，将会禁用某一规则
    "--clang-tidy-checks=cppcoreguidelines-*,performance-*,bugprone-*,portability-*,modernize-*,google-*",
    // 默认格式化风格: 谷歌开源项目代码指南
    // "--fallback-style=file",
    // 同时开启的任务数量
    "-j=2",
    // pch优化的位置(memory 或 disk，选择memory会增加内存开销，但会提升性能) 推荐在板子上使用disk
    "--pch-storage=disk",
    // 启用这项时，补全函数时，将会给参数提供占位符，键入后按 Tab 可以切换到下一占位符，乃至函数末
    // 我选择禁用
    "--function-arg-placeholders=false",
    // compelie_commands.json 文件的目录位置(相对于工作区，由于 CMake 生成的该文件默认在 build 文件夹中，故设置为 build)
    "--compile-commands-dir=build"
  ],

```
```
"clangd.path": "/usr/bin/clangd-12",
"clangd.arguments": [
    "--clang-tidy",
    "--clang-tidy-checks=cppcoreguidelines-*,performance-*,bugprone-*,portability-*,modernize-*,google-*",
  // 告诉clangd用那个clang进行编译，路径参考which clang++的路径
  "--query-driver=/usr/bin/clang++",
]
```

### lldb 配置

```
/********
 
* LLDB *
 
********/
 
// LLDB 指令自动补全
 
"lldb.commandCompletions": true,
 
// LLDB 指针显示解引用内容
 
"lldb.dereferencePointers": true,
 
// LLDB 鼠标悬停在变量上时预览变量值
 
"lldb.evaluateForHovers": true,
 
// LLDB 监视表达式的默认类型
 
"lldb.launch.expressions": "simple",
 
// LLDB 不显示汇编代码
 
"lldb.showDisassembly": "never",
 
// LLDB 生成更详细的日志
 
"lldb.verboseLogging": true,
```

### settings.json

```
{
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
  "editor.guides.bracketPairs": true,
  "editor.bracketPairColorization.enabled": true,
  "editor.suggest.snippetsPreventQuickSuggestions": false,
  "editor.acceptSuggestionOnEnter": "smart",
  "editor.suggestSelection": "recentlyUsedByPrefix",
  "editor.suggest.insertMode": "replace",
  // 禁止中文黄框高亮
  "editor.unicodeHighlight.nonBasicASCII": false,
  // 补全括号选择
  "editor.autoClosingBrackets": "beforeWhitespace",
  "editor.autoClosingDelete": "always",
  "editor.autoClosingOvertype": "always",
  "editor.autoClosingQuotes": "beforeWhitespace",
  // 禁用缩进猜测
  "editor.detectIndentation": false,
  "editor.tabSize": 4,
  "editor.suggest.preview": true,

      // 代码格式化配置 vscode 1.70+ 支持仅修改生效
    // "editor.formatOnSave": true,
    // "editor.formatOnSaveMode": "modifications",
    // "editor.defaultFormatter": "xaver.clang-format",  // 使用Clang-Format
    // "clang-format.style": "file",  // 遵循项目.clang-format文件
    // "clang-format.fallbackStyle": "LLVM",

    // 构建系统集成
    // "cmake.configureOnOpen": true,
    "cmake.generator": "Ninja",  // 推荐与Clang配合使用

    // 增强开发体验
    "files.autoSave": "onWindowChange",  // 自动保存
    "search.followSymlinks": false,  // 避免索引系统头文件
  "window.dialogStyle": "custom",
  // Tab 高度紧凑模式
  "window.density.editorTabHeight": "compact",
  "debug.showBreakpointsInOverviewRuler": true,
  // 文件夹紧凑模式
  "explorer.compactFolders": true,
  "notebook.compactView": true,
  // 自动补齐`HTML`尖括号
  "editor.linkedEditing": true,
  "html.format.wrapAttributes": "preserve",
  "html.format.wrapLineLength": 80,
  // "editor.rulers": [80],
  "html.format.indentHandlebars": true,

  "files.autoGuessEncoding": true,
  // 保存自动删除末尾空格
  "files.trimTrailingWhitespace": true,
  // 搜索吸附目录
  "search.searchEditor.singleClickBehaviour": "peekDefinition",
  "editor.stickyScroll.enabled": true,
  "workbench.tree.enableStickyScroll": true,

  "workbench.iconTheme": "material-icon-theme",
  "workbench.list.fastScrollSensitivity": 10,
  "workbench.colorTheme": "Pretty Dark Theme",
  "workbench.activityBar.location": "bottom",
  "editor.foldingImportsByDefault": true,

  "workbench.startupEditor": "none",
  // 行内样式代码补全
  "editor.quickSuggestions": {
    "other": true,
    "comments": true,
    "strings": true
  },
  "liveServer.settings.donotShowInfoMsg": true,
  "editor.wordSeparators": "`~!@%^&*()=+[{]}\\|;:'\",.<>/?（），。；：",
  "editor.minimap.enabled": false,
  "editor.foldingStrategy": "indentation",
  "liveServer.settings.donotVerifyTags": true,
  "update.mode": "manual",
  "search.exclude": {
    "**/build":true,
    "**/build/**":true,
    "**/.*":true,
    "**/.*/**":true,
    "**/.vscode":true,
    "**/.vscode/**":true,
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
  "outline.showTypeParameters": false,
}
```

