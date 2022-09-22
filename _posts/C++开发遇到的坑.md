
---
layout:     post
title:      c++开发遇到的坑
subtitle:   不适合阅读的整理的一些个人常用的 c++语法
date:       2022-09-08
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
---

>随便整理的一些自用的Linux指令

# 
  
  od -tx1 -tc -Ax binFile

# 

#### 整数溢出
  cat 2.log | awk -F" " '{print $1" " $2" " $3" " $4}'  | sort -t' ' -k4 -rn
#### awk-2 统计log行数
	grep '2022-07-25 10:' service.log.2022072510 | awk -F' ' '{print $6}' | sort | uniq -c
 
 
 
#### 参考链接
https://coolshell.cn/articles/11466.html
