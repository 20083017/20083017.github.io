---
layout:     post
title:      ROS2 Navigation 中文文档环境笔记
subtitle:   只保留一条把 reST 转成 PDF 的依赖安装命令
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - ROS2
    - Navigation
    - Documentation
---

>原始笔记里只有一条命令，这里整理成可继续补充的最小占位版本。

## 当前保留内容

如果只是想把 ROS2 Navigation 的中文 reStructuredText 文档导出成 PDF，可以先准备好转换工具：

```bash
pip install rst2pdf
```

然后再用 `rst2pdf input.rst -o output.pdf` 之类的方式把单篇文档导出。

## 后续可补的方向

这篇后续如果继续整理，建议至少补下面几类内容：

- ROS2 Navigation 中文文档的来源与版本对应关系
- 整套文档的本地构建方式（Sphinx + 主题）
- Nav2 各组件（planner / controller / behavior tree）的简要说明与阅读顺序
- 常见示例工程（`nav2_bringup` 等）的入口

当前这篇先当作一个待扩充的占位条目。
