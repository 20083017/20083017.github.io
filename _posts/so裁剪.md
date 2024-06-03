

-ffuntion-sections and --fdata-sections -Wl,--gc-sections

```
-ffunction-sections 和 -fdata-sections 是 GCC (GNU Compiler Collection) 编译器的选项，而 --gc-sections 是链接器（如 GNU ld）的选项。它们通常一起使用，以减小最终生成的可执行文件或共享库的大小。

-ffunction-sections：这个选项告诉编译器将每个函数放入独立的 section（段）中。这样做的好处是，当链接器处理目标文件时，它可以更容易地决定哪些函数实际被使用了，哪些没有。
-fdata-sections：这个选项类似于 -ffunction-sections，但是它针对的是全局和静态变量。它告诉编译器将每个全局或静态变量放入独立的 section 中。
--gc-sections：这个选项告诉链接器执行 "section garbage collection"。链接器会检查每一个 section，如果它发现某个 section 中没有任何引用的符号（函数或变量），那么这个 section 就会被移除。这可以显著减小最终生成的可执行文件或共享库的大小。
```


### bloaty  命令 查看文件可裁剪文件

```
bloaty -d compileunits -n 0 libmicontinuity.so  > 1.txt
```


static 静态分析 代码段
```
~/.toolchain/sdk_package_MC01/toolchain/bin/aarch64-openwrt-linux-size -A ./libmicontinuity_sdk.so.1.0.4032716
```

运行时分析 smaps
```
 cat /proc/39625/status
 cat /proc/39625/smaps
```

pmap

```
你可以使用 `pmap` 命令来查看进程的内存映射情况，包括哪些内存区域是通过 `mmap` 分配的。具体命令如下：

```
pmap <pid>
```

其中 `<pid>` 是进程的 ID。该命令会输出进程的内存映射情况，包括每个内存区域的起始地址、大小、权限等信息。如果某个内存区域是通过 `mmap` 分配的，那么它的权限信息中会包含 `r-xp`、`r--p`、`rw-p` 等标志，其中 `p` 表示该内存区域是通过 `mmap` 分配的。
```

version_script.map 导出方式
```
extern "c++"{

 c++filt 对debug 符号的解析结果，需要添加""
 class::*; 不要加""

};

nm debug的 符号
```




