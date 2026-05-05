---
layout:     post
title:      Python 常用代码片段速查
subtitle:   后台运行、读 txt、dict 初始化/打印/排序、按行执行 shell
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Python
    - 速查
    - 脚本
---

>原始笔记是若干个 `## 标题` 加代码块的并列条目，开头还有一行散落的 nohup 命令。这里按"后台运行 / 读文件 / dict 操作 / 按行执行 shell"四块整理，命令和脚本本身保持原样。

## 当前保留内容

### 1. 远程后台执行 Python 脚本并写文件

`nohup` + `tee -a` 同时落到日志文件并维持后台运行：

```
nohup python3 run.py |tee -a 1.log &
```

### 2. 读 txt 文件

逐行读 `employeeUid.txt`、去掉首尾空白后转 int 收集到列表：

```
f = open("employeeUid.txt")

line = f.readline()

uid_list = []

while line:
    line = line.rstrip()
    line = line.lstrip()
    if line is not None:
        uid_list.append(int(line))
        #print(int(line))
    line = f.readline()
    #print(int(line))
f.close()
```

### 3. dict 操作

#### 3.1 dict 初始化

用 `dict.fromkeys` 给一组 key 批量建 dict（默认值 None）：

```
m = range(2048)
mp1 = dict.fromkeys(m)
```

#### 3.2 打印 dict

```
for v in mp:
    print(str(v) + " " + str(mp[v]))
```

#### 3.3 dict 排序

按值排序：

```
    print(sorted(key_value.items(), key = lambda kv:(kv[1], kv[0]))) 
```

按 key 排序：

```
    # 字典按键排序
    for i in sorted (key_value) : 
        print ((i, key_value[i]), end =" ")
```

### 4. 按行执行 shell 命令

把 `shell_sql.txt` 中每一行作为一条 shell 命令依次执行：

```
#!/usr/bin/python3

import os
import re


f = open("shell_sql.txt")

line = f.readline()

uid_list = []

while line:
    #line = line.rstrip()
    #line = line.lstrip()
    #if line is not None:
    #    uid_list.append(int(line))
        #print(int(line))
    #line = f.readline()
    #print(int(line))
    os.system(line)
    line = f.readline()
f.close()
```

## 后续可补的方向

- "读 txt"用 `with open(...) as f:` 上下文管理器重写一份更安全的版本
- "按行执行 shell"用 `subprocess.run` 替代 `os.system`，处理返回码与异常
