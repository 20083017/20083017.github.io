

#### 并发编译

```
   set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DOS_POSIX -DOS_ANDROID -DOS_LINUX -DMULTITHREADED_BUILD=4")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DOS_POSIX -DOS_ANDROID -DOS_LINUX -DMULTITHREADED_BUILD=4")
```

### ccache  windows 
安装ccache后添加到环境变量
ccache path 目录

ccache --help 
未做其他设置，已生效

![image](https://github.com/20083017/20083017.github.io/assets/8308226/87df41e7-bd29-44ee-871e-4716b397fb81)

![image](https://github.com/20083017/20083017.github.io/assets/8308226/6fe0198f-e1a5-41eb-8c2e-152d8ab5a303)


### ccache + distcc
distcc 分布式编译工具

