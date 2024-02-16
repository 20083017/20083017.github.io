

### strdup
```
crash
https://github.com/llvm/llvm-project/issues/5932   
```

```
可以使用以下宏来替换`strdup`：

#define MY_STRDUP(s) ({ \
    char *p = malloc(strlen(s) + 1); \
    if (p) strcpy(p, s); \
    p; \
})

这个宏使用了一个`({ ... })`语句块，这是GNU C扩展中的一种语法，可以让宏返回一个值。这个宏使用`malloc`分配了足够的内存来存储输入字符串`s`，并使用`strcpy`将`s`复制到新分配的内存中。如果`malloc`失败，则返回`NULL`。注意，这个宏使用了一个临时变量`p`来存储分配的内存地址，因此不需要使用全局变量。
```
