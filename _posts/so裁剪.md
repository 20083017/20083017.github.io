

-ffuntion-sections and --fdata-sections -Wl,--gc-sections

```
-ffunction-sections 和 -fdata-sections 是 GCC (GNU Compiler Collection) 编译器的选项，而 --gc-sections 是链接器（如 GNU ld）的选项。它们通常一起使用，以减小最终生成的可执行文件或共享库的大小。

-ffunction-sections：这个选项告诉编译器将每个函数放入独立的 section（段）中。这样做的好处是，当链接器处理目标文件时，它可以更容易地决定哪些函数实际被使用了，哪些没有。
-fdata-sections：这个选项类似于 -ffunction-sections，但是它针对的是全局和静态变量。它告诉编译器将每个全局或静态变量放入独立的 section 中。
--gc-sections：这个选项告诉链接器执行 "section garbage collection"。链接器会检查每一个 section，如果它发现某个 section 中没有任何引用的符号（函数或变量），那么这个 section 就会被移除。这可以显著减小最终生成的可执行文件或共享库的大小。
```
