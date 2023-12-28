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
```
double allocate（智能指针--make_shared使用。）

  GDB watch std::string size
print ((size_t*)quit_command._M_dataplus)[-3]  

set print elements 0   
set print pretty on   

gdb  binfile   
set args --conf=../conf/**.conf   
directory src_code_dir   
src_code_dir 有2种情况 绝对路径 相对路径
```
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

#  gdb 调试sdk so
测试可用
```
在使用GDB调试动态库（.so文件）时，如果无法加载源代码，可能是由于以下原因123：

源代码的位置：GDB需要知道源代码的位置才能加载它。你可以使用dir命令将源代码的目录添加到GDB的搜索路径中1。

动态库的符号：为了在GDB中找到变量和函数名，你需要使用sharedlibrary命令将动态库的符号读入GDB1。

动态库的加载：你可能需要在GDB中使用load命令将动态库加载到内存中1。

编译选项：确保在编译动态库时启用了调试信息。这通常通过在编译命令中添加-g选项来实现4。

以下是一个使用GDB调试动态库的基本步骤1：

(gdb) file <你的exe>
(gdb) load <你的so> # 这条命令是可选的
(gdb) dir <so的源码目录>
(gdb) sharedlibrary <你的so>
(gdb) breakpoint <你的so中的某个位置>
(gdb) run


```

