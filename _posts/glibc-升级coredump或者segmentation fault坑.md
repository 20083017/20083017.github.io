系统环境： CentOS 64位

首先，重要的事情说三遍，哈哈：
千万不要在生产环境中升级glibc！！！
千万不要在生产环境中升级glibc！！！
千万不要在生产环境中升级glibc！！！

但是如果实在不幸，在升级glibc时挂掉了，执行各种命令都提示错误，比如：
Segmentation fault
或者：
error while loading shared libraries: libc.so.6: cannot open shared object file: No such file or directory
这类错误出现千万不要着急退出SSH，执行下面的命令是可以挽救的：

```
# cd /lib64
# LD_PRELOAD=/lib64/libc-2.15.so ln -sf /lib64/libc-2.15.so libc.so.6

```

libc-2.15.so这个文件名根据你系统中的文件而定，如果有多个版本so文件可以逐个尝试

原理分析：
linux调用so的库文件时，搜索路径为当前路径，再是系统lib目录。但是提供了一个LD_PRELOAD系统变量来改变这个顺序。设置LD_PRELOAD了后，库加载的顺序就变成这样了：
LD_PRELOAD —> 当前路径 —> 系统lib目录
