---
layout:     post
title:      采集 dumpsys meminfo 曲线
subtitle:   用 `adb` 和 `gnuplot` 快速观察 Android 进程内存变化
date:       2026-04-24
author:     BY
header-img: img/post-bg-android.jpg
catalog: true
tags:
    - Android
    - adb
    - Memory
    - gnuplot
---

>原始内容是一段随手记下的脚本，这里把它整理成“用途 + 前提 + 原脚本”的形式，方便后续继续复用。

## 用途

这段脚本的目标很简单：

- 定期执行 `adb shell dumpsys meminfo <process>`
- 抽取 `Dalvik Heap` 相关字段
- 用 `gnuplot` 直接画出一条变化曲线

适合做快速观察，不适合替代更正式的长期监控或完整内存分析。

## 使用前提

运行前至少要确认下面几项：

1. 主机侧已经能正常执行 `adb`
2. 设备已连接，目标进程名可被 `dumpsys meminfo` 正确识别
3. 本机已安装 `gnuplot`

原始脚本里默认监控的进程名是：

```bash
com.xiaomi.mi_connect_service
```

如果目标进程不同，先把脚本中的 `process_name` 改掉。

## 原始脚本

```bash
#!/bin/bash

# 要采集的进程名称
process_name="com.xiaomi.mi_connect_service"

# 存储数据的数组
data=()

# 采集次数
iterations=10

# 采集间隔（秒）
interval=3

# 存储时间的数组
timestamps=()

# 采集 meminfo
function collect_meminfo() {
    # 采集当前时间戳
    timestamp=$(date +%s)
    timestamps+=($timestamp)

    free=$(adb shell dumpsys meminfo "$process_name" | grep -i 'Dalvik Heap' | awk '{print $3}')
    echo "free is ${free}"
    data+=($free)
}

# 绘制曲线
function plot_curve() {
    # 生成临时数据文件
    temp_data_file=$(mktemp)
    echo "Generating temporary data file: $temp_data_file"
    echo -e "\n" >> "$temp_data_file"

    # 将数据写入临时文件
    for value in "${data[@]}"; do
        echo "$value" >> "$temp_data_file"
        echo -n "$value " >> "$temp_data_file"
        echo -e "\n" >> "$temp_data_file"
    done

    # 生成绘图命令
    plot_cmd="plot '$temp_data_file' with lines title 'Memory Usage'"
    echo "Generating plot command: $plot_cmd"

    # 执行绘图命令
    gnuplot -persist <<< "$plot_cmd"

    # 删除临时数据文件
    rm "$temp_data_file"
}

# 循环采集数据并绘制曲线
function collect_and_plot() {
    echo "Collecting and plotting memory info for process: $process_name"
    echo "Number of iterations: $iterations"
    echo "Collection interval (seconds): $interval"
    echo "Starting collection..."

    for ((i=1; i<=$iterations; i++)); do
        echo "Iteration $i..."
        collect_meminfo
        for element in "${data[@]}"; do
            echo "$element"
        done
        plot_curve
        sleep "$interval"
    done
}

# 执行主函数
collect_and_plot
```

## 使用时的几个提醒

- 这份脚本当前取的是 `Dalvik Heap` 行里的第 3 列，换 ROM 或 Android 版本后可能需要重新确认字段位置
- `gnuplot -persist` 更适合手工观察；如果想保存图片，可以后续再补输出文件配置
- 如果要做更稳定的趋势分析，建议把时间戳和采样值一起落盘，而不是只依赖临时文件
