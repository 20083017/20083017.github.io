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


```
1.安装perl:网址：https://www.perl.org/get.html，下载速度可能有点慢，因为是外网，不要着急。
2.安装两个包：FlameGraph-master.zip、simpleperf-master.tar.gz，FlameGraph可以在网址https://github.com/brendangregg/FlameGraph上下载。
如果要抓手机的，还需要下一个文件push到手机里：simpleperf。
二、使用
以vivo手机为例
1.将simpleperf下载到手机里。
adb push simpleperf的绝对路径 手机里的路径。eg:
adb push F:/simpleperf /data/simpleperf

2.adb shell setenforce 0
3.将文件设置为可编辑的
adb shell chmod 777 /data/simpleperf
4.进入手机里面，开始获取拍照火焰图。
adb shell
使用top -H -O pid 线程号 -d 1 来获取想要的了解的线程，
知道线程n后，使用命令simpleperf命令来抓perf.data数据。
simperperf record -g -p n --duration 20 -f 12500 --call-graph fp -o /data/perf.data
5.退出手机
exit
6.把perf.data数据拉到电脑中分析
adb pull /data/perf.data
7.使用FlameGraph-master.zip、simpleperf-master.tar.gz两个包来生成火焰图。
首先将刚刚生成的perf.data文件放入到simpleperf-master文件夹中，执行：python report_sample.py >out.perf获得out.perf文件。
8.将out.perf文件放到FlameGraph文件夹中，使用下面两个命令：
perl stackcollapse-perf.pl out.perf >out.folded

perl flamegraph.pl out.folded > graph.svg
————————————————
版权声明：本文为CSDN博主「zuimman」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
原文链接：https://blog.csdn.net/zuimman/article/details/120510910
```
