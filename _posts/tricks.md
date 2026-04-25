---
layout:     post
title:      日常使用小技巧
subtitle:   暂时只记录强制 Chrome 进入 Dark Mode 的命令
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Tricks
    - macOS
    - Chrome
---

>原始笔记只有一条命令，这里整理成可继续补充的最小占位版本。

## 当前保留内容

### macOS 下强制 Chrome 使用 Dark Mode

如果系统主题没切换、但希望 Chrome 自身界面以暗色显示，可以在终端里用启动参数打开：

```bash
open -a Google\ Chrome --args --force-dark-mode
```

注意这只是强制 Chrome 自身 UI 走暗色，不会改变网页内容的渲染配色。

## 后续可补的方向

这篇后续如果继续整理，建议至少补下面几类内容：

- 其它常用浏览器/编辑器的暗色模式开关
- macOS 上常用的 `open` / `defaults` 命令片段
- Windows / Linux 上对应的小技巧

当前这篇先当作一个待扩充的零碎技巧合集占位。
