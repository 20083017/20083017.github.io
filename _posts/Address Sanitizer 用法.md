

https://www.jianshu.com/p/3a2df9b7c353


关闭tcmalloc

链接  -pthread  -lasan， pthread 在前边。


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
