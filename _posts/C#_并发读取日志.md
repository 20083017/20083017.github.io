---
layout:     post
title:      C# 并发读取日志（未调通版本）
subtitle:   一个基于 ConcurrentBag + Parallel.ForEach 的多线程日志切分 Demo
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C#
    - 多线程
    - 日志
---

>原始笔记是一段未做任何拆分的 C# 代码块，开头还有一句"C# 9.0 未调通"的备注。这里按"目标 / 数据结构 / 处理类 / 待修复点"四块整理，代码内容原样保留，方便后续在 .NET 环境里直接调试。

## 当前保留内容

### 1. 目标与状态

- 目标：在多线程下并发读取一份较大的日志文件，按 `[ERROR]` / `[INFO]` / `[DEBUG]` 三类拆分进各自的 `ConcurrentBag`。
- 当前状态：基于 C# 9.0，**尚未调通**，下面的代码仅作为思路骨架使用。

### 2. 三类日志条目

```
public class ErrorLogEntry
    {
        public DateTime Timestamp { get; set; }
        public int ErrorCode { get; set; }
        public string Severity { get; set; }
        public string Message { get; set; }
    }

    public class InfoLogEntry
    {
        public DateTime Timestamp { get; set; }
        public string Source { get; set; }
        public string Operation { get; set; }
        public string Details { get; set; }
    }

    public class DebugLogEntry
    {
        public DateTime Timestamp { get; set; }
        public string ThreadId { get; set; }
        public string StackTrace { get; set; }
    }
```

### 3. 处理类 LogProcessor

并发读取主体：将文件按 `maxThreads` 切成若干 chunk，使用 `Parallel.ForEach` 各自打开文件流读取自己负责的区间。

```
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;

    public class LogProcessor
    {
        private readonly ConcurrentBag<ErrorLogEntry> _errors = new();
        private readonly ConcurrentBag<InfoLogEntry> _infos = new();
        private readonly ConcurrentBag<DebugLogEntry> _debugs = new();

        public (List<ErrorLogEntry>, List<InfoLogEntry>, List<DebugLogEntry>) ProcessLogFile(string filePath, int maxThreads)
        {
            var chunks = SplitFileIntoChunks(filePath, maxThreads).ToList();

            Parallel.ForEach(chunks, new ParallelOptions { MaxDegreeOfParallelism = maxThreads }, chunk =>
            {
                using var fs = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read);
                using var reader = new StreamReader(fs);
                fs.Seek(chunk.Start, SeekOrigin.Begin);

                string line;
                while (fs.Position < chunk.End && (line = reader.ReadLine()) != null)
                {
                    var entry = ParseLogLine(line);
                    if (entry is ErrorLogEntry error) _errors.Add(error);
                    else if (entry is InfoLogEntry info) _infos.Add(info);
                    else if (entry is DebugLogEntry debug) _debugs.Add(debug);
                }
            });

            return (_errors.ToList(), _infos.ToList(), _debugs.ToList());
        }

        public IEnumerable<(long Start, long End)> SplitFileIntoChunks(string filePath, int chunkCount)
        {
            var fileInfo = new FileInfo(filePath);
            long chunkSize = fileInfo.Length / chunkCount;
            long position = 0;

            for (int i = 0; i < chunkCount; i++)
            {
                long end = (i == chunkCount - 1) ? fileInfo.Length : position + chunkSize;

                // 确保块结束在换行符处，避免截断行
                using var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read);
                stream.Seek(end, SeekOrigin.Begin);
                using var reader = new StreamReader(stream);
                while (!reader.EndOfStream && reader.Read() != '\n') { }
                end = stream.Position;

                yield return (position, end);
                position = end;
            }
        }

        private object ParseLogLine(string line)
        {
            if (string.IsNullOrEmpty(line)) return null;

            // 按分隔符拆分字段（假设使用竖线分隔）
            var parts = line.Split('|', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 2) return null;

            if (line.StartsWith("[ERROR]"))
            {
                return new ErrorLogEntry
                {
                    Timestamp = DateTime.Parse(parts[1]),
                    ErrorCode = int.Parse(parts[2]),
                    Severity = parts[3],
                    Message = string.Join('|', parts.Skip(4)) // 合并剩余部分作为消息
                };
            }
            else if (line.StartsWith("[INFO]"))
            {
                return new InfoLogEntry
                {
                    Timestamp = DateTime.Parse(parts[1]),
                    Source = parts[2],
                    Operation = parts[3],
                    Details = string.Join('|', parts.Skip(4)) // 合并剩余部分作为详情
                };
            }
            else if (line.StartsWith("[DEBUG]"))
            {
                return new DebugLogEntry
                {
                    Timestamp = DateTime.Parse(parts[1]),
                    ThreadId = parts[2],
                    StackTrace = string.Join('|', parts.Skip(3)) // 合并剩余部分作为堆栈跟踪
                };
            }

            return null; // 忽略无法识别的日志类型
        }
    }
```

### 4. 已知待修复点

- chunk 边界对齐：当前在每个 chunk 末尾会再额外开一个 `FileStream` 找换行，逻辑能跑但读了两遍，性能不佳。
- `fs.Position < chunk.End` 与 `StreamReader` 的内部缓冲不一致，可能漏读最后一行或读越界，需要换成 `Encoding` 感知的字节计数。
- `ParseLogLine` 假定字段固定下标，没做容错；在生产日志上很容易抛 `FormatException`。

## 后续可补的方向

- 把 chunk 切分改成"先按字节切，再向后扫到换行"的一次扫描版本，避免双重打开。
- 用 `Channel<T>` / `BlockingCollection<T>` 替代三个独立 `ConcurrentBag`，把分类与消费解耦。
- 加一份单元测试日志样本（含残缺行 / 多种分隔符 / UTF-8 BOM），把这份 Demo 真正调通。
