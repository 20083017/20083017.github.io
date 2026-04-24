---
layout:     post
title:      Android simpleperf 使用记录
subtitle:   从设备采样到生成火焰图的最小流程
date:       2026-04-24
author:     BY
header-img: img/post-bg-android.jpg
catalog: true
tags:
    - Android
    - simpleperf
    - Profiling
---

>把原始笔记中的命令、前提和出图步骤重新整理成一条完整链路。

## 环境结论

原始记录里的经验是：

- `userdebug` ROM 上 profiler 不一定稳定
- 某些 `user` 版本的 profiler 反而更容易直接工作，原笔记里的表述是“profiler build for user_build”

因此在开始抓数据前，先确认目标设备的 ROM 类型和 simpleperf 二进制是否匹配。

## 构建前提

如果要分析自己的 App，先保证目标构建可调试：

```gradle
buildTypes {
    debug {
        debuggable true
    }
}
```

另外，符号化分析时需要准备带符号表的 so。原始笔记提到，可以把 `merged_native_libs` 下包含 symbol table 的 so 一并放到用于解析的目录中。

## 先看帮助

```bash
simpleperf --help
simpleperf record --help
```

## 直接抓进程

最小采样命令：

```bash
simpleperf record -p 20510 --duration 10
```

如果需要调用栈和符号目录：

```bash
simpleperf record -g -p 20510 --duration 30 --symfs /sdcard/
```

其中 `--symfs` 用来指定带符号 so 的位置。

## 生成火焰图

主机侧需要 Perl 环境，然后可以按下面方式折叠并出图：

```bash
perl stackcollapse-perf.pl perf_script_output_file.txt | perl flamegraph.pl > a.html
```

如果本机还没准备环境，原始记录里提到至少要先准备：

1. Perl 5
2. `FlameGraph`
3. `simpleperf` 对应分析脚本目录

## 进程采样示例

原始记录里保留的一条常用命令如下：

```bash
simpleperf record -g -p 20510 --duration 30 -f 12500 --call-graph fp -o perf.data
```

适合已经知道目标进程 PID、并希望直接拿到 `perf.data` 的场景。

## 线程级采样流程

如果要抓单个线程，可以按这条链路走：

### 1. 把 simpleperf 推到设备

```bash
adb push /absolute/path/to/simpleperf /data/simpleperf
adb shell chmod 777 /data/simpleperf
```

原始示例里使用的是类似下面的 Windows 路径：

```bash
adb push F:/simpleperf /data/simpleperf
```

### 2. 必要时放宽 SELinux（仅调试环境）

```bash
adb shell setenforce 0
```

### 3. 在设备上找线程

```bash
adb shell
top -H -O pid -d 1
```

原始笔记这里是“以 vivo 手机为例”，核心动作不变：先进入 shell，再用 `top -H -O pid -d 1` 找到想看的线程。

找到目标线程后，使用对应 PID / TID 采样。

### 4. 在设备侧记录数据

```bash
simpleperf record -g -p n --duration 20 -f 12500 --call-graph fp -o /data/perf.data
```

把 `n` 替换成目标线程或进程标识。

### 5. 拉回主机分析

```bash
adb pull /data/perf.data
python report_sample.py > out.perf
perl stackcollapse-perf.pl out.perf > out.folded
perl flamegraph.pl out.folded > graph.svg
```

如果是按设备内交互流程操作，原始步骤里还包含：

```bash
exit
adb pull /data/perf.data
```

其中：

- `out.perf`：`report_sample.py` 转换后的文本结果
- `out.folded`：供 FlameGraph 使用的折叠栈数据
- `graph.svg`：最终生成的火焰图

## 使用时的几个提醒

- 设备侧抓得到数据，不代表主机侧一定能正确符号化；带符号 so 要提前准备好
- `setenforce 0` 只适合调试机
- 如果调用栈不完整，优先检查 `--call-graph fp` 是否适合当前编译方式

## 原始来源备注

原始笔记末尾引用过一篇 CSDN 文章，这里保留来源信息，便于后续回查：

- 原文链接：`https://blog.csdn.net/zuimman/article/details/120510910`
