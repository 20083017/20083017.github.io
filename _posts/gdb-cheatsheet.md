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


# Gdb 内存越界、内存重叠、重复释放、double allocate

double allocate（智能指针--make_shared使用。）

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


# 查看线程堆栈
```
首先，将gdb attach到调试线程

gdb -p pro_pid
然后，在GDB中设置调试文件路径，并开启日志选项

set logging file mylog.txt
set logging on
最后,输出所有线程堆栈到指定文件

thread apply all bt   // 最准确
```

# 程序hang住


strace的最后依据。

pstack + strace 
cat /proc/pid/stack
cat /proc/pid/wchan   // hang 住的信号

# 进程、线程状态

info threads
thread id (info threads 前面的id)

# 查看全局和静态变量
info variables（尽量不要用，可能会有很多）
info locals(stack frame 局部变量)
info args(查看当前stack frame参数)


# strace 详解
https://www.cnblogs.com/machangwei-8/p/10388883.html

