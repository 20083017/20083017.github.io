---
layout:     post
title:      UUID1 时间戳解析
subtitle:   从 UUID 里反推出生成时间的最小 Python 备忘
date:       2026-04-25
author:     BY
header-img: img/post-bg-debug.png
catalog: true
tags:
    - Python
    - UUID
---

>这条笔记主要记录一件事：如果拿到的是 `uuid1`，可以直接从时间字段反推出它的大致生成时间。

## 1. 先生成或读取一个 UUID

```python
import uuid

u = uuid.uuid1()

u = uuid.UUID("2c1af3a6b7f511ed80c21554341098f8")
```

这里要注意，只有 `uuid1` 这类带时间字段的 UUID，才适合继续往下做时间解析。

## 2. 把 UUID 时间字段转换成 datetime

```python
import datetime

timestamp = (u.time - 0x01B21DD213814000) / 1e7
dt = datetime.datetime.fromtimestamp(timestamp)
print(dt)
```

核心点只有两个：

- `u.time` 的单位是 **100ns**
- `0x01B21DD213814000` 是 UUID 时间基准到 Unix 时间基准之间的偏移量

换算完成后，就能得到这个 `uuid1` 对应的大致生成时间。

## 3. 参考链接

```text
https://juejin.cn/post/6923014125652181000#heading-10
```
