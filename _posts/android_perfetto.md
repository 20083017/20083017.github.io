---
layout:     post
title:      Android Perfetto 堆分析记录
subtitle:   heapprofd 与 java_hprof 采集时的环境要求和配置片段
date:       2026-04-24
author:     BY
header-img: img/post-bg-android.jpg
catalog: true
tags:
    - Android
    - Perfetto
    - Profiling
---

>把原先零散命令整理成“环境前提 + 采集步骤 + 配置片段”的形式，方便后续直接复用。

## 使用前提

当前记录主要针对 Linux / macOS 主机侧执行，设备侧结论如下：

- Android 13：在 `user root` 类环境里可行
- Android 14：兼容性不稳定，部分设备需要先在开发者选项里打开“系统跟踪”之类的开关

如果设备权限、ROM 类型或系统版本不满足，后面的命令即使执行成功，也可能抓不到有效数据。

## 采集前准备

### 1. 打开 traced 与 libc hook

```bash
adb shell setprop persist.traced.enable 1
adb shell setprop libc.debug.hooks.enable 1
```

### 2. 放宽 SELinux（仅限确认环境可控时）

```bash
adb shell su root setenforce 0
```

这一步只适合调试环境，不应默认带到正式设备配置里。

## heapprofd 采集命令

原始笔记里的示例命令如下，输出目录为本地的 `wifi_data_release/`：

```bash
python3 heap_profile.py \
  -n com.xiaomi.mi_connect_service:continuity \
  -c 3000 \
  -i 1024 \
  -o ./wifi_data_release/
```

可以重点关注三个参数：

- `-n`：目标进程名
- `-c`：采样次数 / 总量相关控制
- `-i`：采样间隔

## 直接使用 perfetto 命令时的注意点

曾尝试直接执行：

```bash
./perfetto -c 1.perfetto.config --txt --out /data/misc/1
```

原始结果备注为“无数据”。遇到这种情况，通常优先检查：

1. 目标进程名是否写对
2. 设备是否真的支持对应 data source
3. traced / hook / 开发者选项是否已经开启
4. buffer 是否过小，导致 UI 解析或采集结果异常

## 配置片段示例

下面保留一份原始配置思路，核心用途是记录 heapprofd 与 java hprof 的字段结构。

```text
buffers: {
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
                dump_phase_ms: 10000
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
                dump_phase_ms: 10000
                dump_interval_ms: 2000
            }
        }
    }
}
duration_ms: 30000
```

其中原始经验里有一条值得保留：

>buffer 太小的时候，Perfetto UI 可能解析失败，因此当数据量较大时需要主动放大。

## 参考方向

原始笔记里顺手记过几篇外部资料，后续如果要继续深入看 Perfetto 配置或内存采样，可以沿着这些关键词继续搜：

- `Perfetto heapprofd`
- `Perfetto java_hprof`
- `heap_profile.py`
