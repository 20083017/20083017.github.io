---
layout:     post
title:      Python 逐行读取文件并执行命令
subtitle:   把"读一行 / 跑一行 shell"的小脚本固化成模板
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Python
    - 脚本
---

>原始笔记只有一段未加说明的脚本代码。这里补上用途和注意事项，脚本本身保持原样。

## 当前保留内容

### 用途

读取一个外部文本文件（这里是 `shell_sql.txt`），把里面每一行当成一条 shell 命令逐行 `os.system` 执行——典型场景是批量执行预先生成好的命令清单，例如批量导入 SQL、批量调用工具脚本。

### 模板代码

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

> 注释里的几行是早期把每行解析成 `int` 加进 `uid_list` 的旧思路，留作演进记录。

## 后续可补的方向

- 用 `with open(...)` + `for line in f` 改成更地道的写法
- 命令失败时如何判断退出码（`subprocess.run(check=True)`）
- 行内变量替换、跳过空行 / 注释行等常见增强
- 大批量命令时的并发执行版本（`concurrent.futures`）
