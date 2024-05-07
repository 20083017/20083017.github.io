

1、gperftool 2.5或者1.7？？ brpc

https://bbs.huaweicloud.com/blogs/192035

tcmalloc 版本选择？？

2、  c++版本 c++17?



在64位Linux环境下，gperftools使用glibc内置的stack-unwinder可能会引发死锁，因此官方推荐在配置和安装gperftools之前，先安装libunwind-0.99-beta，最好就用这个版本，版本太新或太旧都可能会有问题。

即便使用libunwind，在64位系统上还是会有问题，但只影响heap-checker、heap-profiler和cpu-profiler，TCMalloc不受影响，因此不再赘述，感兴趣的读者可参阅gperftools的INSTALL。

如果不希望安装libunwind，也可以用gperftools内置的stack unwinder，但需要应用程序、TCMalloc库、系统库（比如libc）在编译时开启帧指针（frame pointer）选项。

在x86-64下，编译时开启帧指针选项并不是默认行为。因此需要指定-fno-omit-frame-pointer编译所有应用程序，然后在configure时通过--enable-frame-pointers选项使用内置的gperftools stack unwinder。




3、virtualbox ubuntu安装
https://blog.csdn.net/qq_36340642/article/details/109253664


4、链接方式   
```
                target_link_libraries(${TARGET_NAME}
                    -ltcmalloc
                    # tcmalloc_and_profiler  #不能同时存在
                )
```

5、编译配置
    不能与 lsan，address 同时使用！！！   
```
          set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -g -O0  -fno-omit-frame-pointer")
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g -O0  -fno-omit-frame-pointer")
```

6、 使用方式   
针对程序不能正常退出的情况   
```
#if !defined(NDEBUG)
#include <gperftools/heap-profiler.h>
#endif

#if !defined(NDEBUG)
    HeapProfilerStart("my_program test");
#endif

#if !defined(NDEBUG)
    HeapProfilerDump("end");
#endif
```
