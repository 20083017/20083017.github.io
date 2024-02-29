

https://www.jianshu.com/p/3a2df9b7c353


关闭tcmalloc

链接  -pthread  -lasan， pthread 在前边。

### leak
```
linux 或者虚拟可以查leak， wsl 查不出来~
```
### address
```
wsl可以查出 use_after_free等问题
```

### android asan

```
 32bit android 13 及以前，需要安装特殊的rom包 [pass]
  小米手机 无32位？！！！  bug了。。
```

### android hwasan

```
64bit  android 14及以后
wrap.sh 不需要，带上之后反而编译不过！！！！
```
