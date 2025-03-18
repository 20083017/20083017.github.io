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
