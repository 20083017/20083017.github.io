### perfetto 命令
暂时支持linux\mac 

```
可行 android 13，rom为user root版本。
android 14 暂不支持
android 14, 好像 在开发者选项内打开 系统跟踪开关，才能正常捕获~   
1.允许 perfetto，允许hook
adb shell setprop persist.traced.enable 1
adb shell setprop libc.debug.hooks.enable 1

2.设置
adb shell su root setenforce 0

3.使用命令
wifi_data_release为文件夹
python3 heap_profile.py -n com.xiaomi.mi_connect_service:continuity -c 3000 -i 1024 -o ./wifi_data_release/

```

链接
https://github.com/RT-Thread-packages/mbedtls/blob/master/docs/footprint-optimization-guide.md   

https://blog.csdn.net/xiaowanbiao123/article/details/132026753   
http://www.luzexi.com/static-page/Perfetto/Index/Perfetto%E5%86%85%E5%AD%98%E5%B7%A5%E5%85%B7%E5%88%86%E6%9E%90.html   



 命令    
  ./perfetto -c 1.perfetto.config --txt --out /data/misc/1   
  无数据  
```

buffers: {
    ## 将buffer增大1000倍，否则出现Perfetto ui解析出错
    size_kb: 63488000
    fill_policy: DISCARD
}
buffers: {
    size_kb: 63488000
    fill_policy: DISCARD
}
data_sources: {
    config {
        name: "android.packages_list"
        target_buffer: 1
    }
}
data_sources: {
    config {
        name: "android.heapprofd"
        target_buffer: 0
        heapprofd_config {
            sampling_interval_bytes: 4096
            process_cmdline: "com.xiaomi.mi_connect_service:idm"
            shmem_size_bytes: 8388608
            heaps: "com.android.art"
            continuous_dump_config {
                ## 10s之后，才开始第一次dump
                dump_phase_ms: 10000
                ## 每隔2s，dump一次
                dump_interval_ms: 2000
            }
        }
    }
}

data_sources: {
    config {
        name: "android.java_hprof"
        target_buffer: 0
        java_hprof_config {
            process_cmdline: "com.xiaomi.mi_connect_service:idm"
            continuous_dump_config {
                ## 10s后，才开始第一次dump
                dump_phase_ms: 10000
                ## 每隔2s,dump一次
                dump_interval_ms: 2000
            }
        }
    }
}
## 总时间变成 30s
duration_ms: 30000
```
