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
