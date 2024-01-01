simpleperf 使用

### 采集数据

build.gradle 增加

```
    buildTypes {
        debug{
            debuggable true
        }
    }
```


将merged_native_libs 下含有symbol table的so push到手机中

执行命令

simpleperf --help
simpleperf record --help

simpleperf record -p 20510 --duration 10

--symfs  带符号表so位置
simpleperf record -g -p 20510 --duration 30 --symfs /sdcard/

###  显示图形
perl version 5

perl stackcollapse-perf.pl perf_script_output_file.txt | perl flamegraph.pl > a.html
