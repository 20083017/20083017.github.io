---
layout:     post
title:      Gdb指令整理
subtitle:   不适合阅读的整理的一些个人常用的 Gdb 指令
date:       2022-09-12
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Gdb
---

>随便整理的一些自用的Gdb指令


# Gdb 内存越界、内存重叠、重复释放、

  GDB watch std::string size
print ((size_t*)quit_command._M_dataplus)[-3]  

set print elements 0
set print pretty on

gdb  binfile
set args --conf=../conf/**.conf
directory src_code_dir
src_code_dir 有2种情况 绝对路径 相对路径
否则 list 不会列出 源文件信息，所以 要求 源文件路径 与 二进制文件中路径一致
查看二进制文件路径 
readelf -p .debug_str exe_or_so_file  查看源文件是否为相对路径
b filename:linenum   设置断点 
