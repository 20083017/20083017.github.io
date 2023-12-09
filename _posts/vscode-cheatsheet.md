


![C9iOkmPCZB](https://github.com/20083017/20083017.github.io/assets/8308226/29e7540d-f683-47bc-bbd8-8a87d75371d2)


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
