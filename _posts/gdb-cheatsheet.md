---
layout:     post
title:      GDB 指令整理
subtitle:   core dump、内存问题、线程栈、so 调试与 .gdbinit 模板
date:       2022-09-12
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - GDB
    - C++
    - Debug
    - Linux
---

>原始笔记把 core dump、内存越界、线程栈、so 调试和 `.gdbinit` 配置混在一起，这里按使用场景分节整理，原始命令基本保留。

## 1. 打开 core dump 文件

### 1.1 当前目录无法生成 core 文件

可以临时调整 core 文件命名规则：

```bash
echo core.%e.%p > /proc/sys/kernel/core_pattern
```

这只是临时修改，重启后失效。

要长期生效，更稳妥的方式是：

```bash
sudo /sbin/sysctl -w kernel.core_pattern=core.%e.%p
```

或者写入 `/etc/sysctl.d/*.conf` 后再 `sysctl --system`。生产环境不建议无脑全局打开 `ulimit -c unlimited`，否则连续崩溃可能写满磁盘。

### 1.2 修改 ulimit 后还是 `not a core dump`

确认两件事：

1. `ulimit -c unlimited` 已经在当前 shell 生效。
2. 当前可执行文件**不要放在与 Windows 共享的目录里**（例如 WSL 下挂载的 `/mnt/c/...`）。
   实践中遇到过这种情况：core 文件大小始终为 0，把可执行文件移到 Linux 原生目录（例如 `/home/user/...`）下再跑，core 文件就能正常生成。

## 2. 排查内存越界 / 重叠 / 重复释放

适合排查 `double allocate`、智能指针 `make_shared` 误用、字符串容量异常等问题：

```gdb
# 让 GDB 不裁剪长容器/字符串内容
set print elements 0
set print pretty on

# 启动 gdb
gdb binfile
set args --conf=../conf/**.conf

# 添加源码搜索路径，否则 list 不会显示源代码
directory src_code_dir
```

`src_code_dir` 既可以是绝对路径，也可以是相对路径，但**要求源文件路径与二进制文件中记录的路径一致**，否则 `list` 找不到源文件。

可以先确认二进制里记录的源文件路径是相对还是绝对：

```bash
readelf -p .debug_str <exe_or_so>
```

设置断点时使用：

```gdb
b filename:linenum
```

观察 `std::string` 内部容量（用于排查 SSO / 容量异常）：

```gdb
print ((size_t*)quit_command._M_dataplus)[-3]
```

## 3. 查看线程堆栈

把 GDB attach 到运行中的进程并把所有线程堆栈写到日志：

```bash
gdb -p <pid>
```

进入 GDB 后：

```gdb
set logging file mylog.txt
set logging on
thread apply all bt    # 输出全部线程堆栈，最准确
```

## 4. 程序 hang 住时

不要只盯着 `gdb`，先组合几条更便宜的命令：

```bash
pstack <pid>
strace -p <pid>
cat /proc/<pid>/stack    # 当前内核栈
cat /proc/<pid>/wchan    # 当前等待的内核函数（hang 在哪）
```

`strace` 是最后一道依据：能直接看到程序卡在哪个系统调用上。

## 5. 进程 / 线程状态

```gdb
info threads             # 查看所有线程
thread <id>              # 切换到 info threads 列出的某个线程
```

## 6. 查看变量

```gdb
info variables           # 全局/静态变量；可能很多，慎用
info locals              # 当前 stack frame 的局部变量
info args                # 当前 stack frame 的参数
```

## 7. 调试动态库 (so) 时无法加载源码

测试可用的步骤如下：

```gdb
(gdb) file <你的可执行文件>
(gdb) load <你的 so>             # 可选
(gdb) dir  <so 的源码目录>
(gdb) sharedlibrary <你的 so>    # 把 so 的符号读进来
(gdb) break <so 中的某个位置>
(gdb) run
```

常见原因可以按下面四类排查：

1. **源代码位置**：用 `dir` 把源码目录加入 GDB 搜索路径。
2. **so 符号**：用 `sharedlibrary` 显式加载 so 的符号。
3. **so 加载**：必要时用 `load` 把 so 装入内存。
4. **编译选项**：so 编译时要加 `-g`，否则 GDB 拿不到调试信息。

## 8. `.gdbinit` 常用模板

放在 `~/.gdbinit` 中，启动 GDB 时自动生效：

```gdb
echo \nReading ~/.gdbinit...\n\n

set print asm-demangle on
set print pretty on
set print object on
# set print static-members on   # 打印对象太啰嗦，关掉
set print static-members off
set print vtbl on
set print demangle on
set demangle-style gnu-v3
# set demangle-style none

# 让 emacs / 部分前端能跟上 gdb 的位置
set annotate 1

set history size 9999999
set history filename ~/.gdbhistory
set history save on

define gdbkill
    kill
end

define gdbquit
    quit
end

set script-extension soft

# 调试时如果不希望其它线程同时跑，可以打开下面这条
# set scheduler-locking on

# 让 eshell 自己处理分页
set height 0

# 习惯性 alias
alias -a exit = quit

source ~/etc/gdb/nopify.py
```

## 9. 参考

- strace 详解：<https://www.cnblogs.com/machangwei-8/p/10388883.html>
- 查看被优化掉的变量值：<https://www.qdcto.com/archives/1002#_%E6%9F%A5%E7%9C%8B%E8%A2%AB%E4%BC%98%E5%8C%96%E5%90%8E%E7%9A%84%E5%8F%98%E9%87%8F%E5%80%BC>

更系统的 core dump 排查流程见同目录 `core-dump调试技巧.md`。
