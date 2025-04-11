
C# 9.0  未调通    

```
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;

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
