

#### 并发编译

未生效
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


### 导出符号表
```
https://tech.meituan.com/2022/06/02/meituans-technical-exploration-and-practice-of-android-so-volume-optimization.html

--version-script 全局链接选项
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--version-script=${CMAKE_SOURCE_DIR}/version.map")

对某个目标生效
add_library(mylib SHARED mylib.c)
set_target_properties(mylib PROPERTIES LINK_FLAGS "-Wl,--version-script=${CMAKE_SOURCE_DIR}/version.map")


```

### graphviz
 cmake 
 --graphviz=foo.dot  ## 添加配置项

 foo.dot 转换为png
 dot -Tpng foo.dot -o foo.png

 ### version_script

 ``
要在CMake中为特定目标启用version script，可以使用`set_target_properties`命令并设置`LINK_FLAGS`属性。例如，假设您有一个名为`my_target`的目标，并且您想要使用名为`my_version_script`的版本脚本文件，则可以使用以下命令：

```
set_target_properties(my_target PROPERTIES LINK_FLAGS "-Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/my_version_script")
```

这将为`my_target`目标设置链接标志，以便在链接时使用`my_version_script`版本脚本文件。请注意，`-Wl`选项用于将选项传递给链接器。`CMAKE_CURRENT_SOURCE_DIR`变量包含当前正在处理的CMakeLists.txt文件的目录路径。`
```

###  强制动态库
```
add_dependencies(${TARGET_NAME} micontinuity)
if(TARGET micontinuity_so)
    add_library(micontinuity_so SHARED IMPORTED)
    message("CMAKE_INSTALL_LIBDIR is "
        "${ROOT_PATH}/cmake-build-script/linux-release/router-rc01/runtime/services/libmicontinuity.so")
    set_target_properties(micontinuity_so PROPERTIES IMPORTED_LOCATION
        "${ROOT_PATH}/cmake-build-script/linux-release/router-rc01/runtime/services/libmicontinuity.so")
endif()
```
