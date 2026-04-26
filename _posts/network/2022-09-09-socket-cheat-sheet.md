---
layout:     post
title:      Socket 问题排查整理
subtitle:   accept 队列 / 内核参数 / fd 泄漏 / tcpdump / WebSocket curl
date:       2022-09-09
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Socket
    - TCP
    - Linux
    - Network
---

>原始笔记把队列检查、内核参数、fd 排查、抓包和 WebSocket 调试混在一起，这里按排查顺序分节整理，方便回看时快速跳到对应小节。

## 1. accept 队列检查

### 1.1 全连接队列是否溢出

如果出现 `accept queue is full`，先确认内核行为：

```bash
cat /proc/sys/net/ipv4/tcp_abort_on_overflow
```

- `0`：内核丢掉 ack（客户端会感觉「最后一次握手没回应」）
- `1`：内核直接发 RST

观察是否真的有溢出：

```bash
netstat -s | grep overflowed
# 例：13924575 times the listen queue of a socket overflowed
```

数字持续增长，就说明确实在丢连接。

### 1.2 监听端口的队列长度

```bash
ss -l | grep ':<port>'
```

在「LISTEN 状态」时：

- `Recv-Q`：当前全连接队列已堆积的数量（已完成三次握手、等待 `accept()` 的 TCP 连接）
- `Send-Q`：当前全连接最大队列长度（即 `backlog`）

例如 `Send-Q = 128`，表示服务最多排 128 个等待 accept 的连接。

> 默认 backlog 经常只有 50，业务上很容易就满。

在「非 LISTEN 状态」时：

- `Recv-Q`：内核已收到但应用进程尚未读走的字节数
- `Send-Q`：已发送但尚未收到对端 ACK 的字节数

### 1.3 当前连接数分布

```bash
netstat -ant | awk '/^tcp/ {++S[$NF]} END {for (a in S) print (a, S[a])}'
```

可以快速看到 `ESTABLISHED` / `TIME_WAIT` / `CLOSE_WAIT` 等各占多少。

## 2. sysctl 内核参数

应对短时间大量握手与队列堆积，常调整：

```text
net.ipv4.tcp_syncookies      = 1
net.ipv4.tcp_max_syn_backlog = 16384
net.core.somaxconn           = 16384
```

接入层（如 nginx）侧也要把 `backlog` 调大：

```text
backlog = 32768
```

其它常见取舍：

- 关闭 Nagle 算法：`TCP_NODELAY`（小包对延迟敏感时）
- `SO_SNDBUF` / `SO_RCVBUF` 不建议手动调，让内核自适应通常更稳

## 3. CLOSE_WAIT 堆积与 fd 泄漏

### 3.1 状态确认

```bash
netstat -antp | grep <port>
```

如果发现端口大量 `CLOSE_WAIT`，通常是**应用层没有调用 `close()`**。
原始笔记里就有过这种例子：压测 demo 漏写 `closesocket`，加上之后立即恢复。

### 3.2 fd 上限和当前占用

```bash
ulimit -a            # 系统允许打开的 fd 数
lsof -p <pid> | wc -l   # 某进程已经打开的 fd 数
```

### 3.3 进一步看是哪些 fd 在泄

```bash
lsof -p <pid> > openfiles.log
```

对比两个时间点的 `openfiles.log`，常见症状是大量 `can't identify protocol` 的 socket，意味着握手已结束但应用没 close。

### 3.4 用 strace 跟系统调用

```bash
strace -f -p <pid> -T -tt -o /tmp/strace_<pid>.log
```

参数含义：

- `-f`：跟踪 fork/clone 出来的子进程/线程
- `-T`：显示每条系统调用耗时
- `-tt`：带毫秒时间戳

如果是从启动开始跟踪：

```bash
strace -f -F -o dcop-strace.txt dcopserver
```

`-f -F` 同时跟踪 `fork` 和 `vfork` 出来的进程；`-o` 把输出写到文件，方便事后分析。

> `strace + lsof` 能解决大部分 fd 泄漏问题。

## 4. RST 与抓包确认

> 触发 RST 通常是因为客户端**还有未读完的数据**就关闭了 socket，属于不规范操作。

确认这类问题最稳的方式是抓包：

```bash
tcpdump tcp -i xgbe0 -t -s 0 -c 100  and dst port 8863 and src net 10.128.161.11 -w ./target.cap
tcpdump tcp -i xgbe0 -t -s 0 -c 2000 and net 10.128.161.15 and net 10.128.161.11 -w ./target.cap
tcpdump -i any port 4012 -w server.pcap
```

常用参数：

- `-i <iface>`：指定网卡（`any` 抓所有）
- `-t`：不显示时间戳（`-tt` 显示）
- `-s 0`：抓完整数据包（默认只抓前 96 字节，会把负载切掉）
- `-c N`：只抓 N 个包就退出
- `dst port ! 22` / `src net 192.168.1.0/24`：BPF 过滤
- `-w file.cap`：保存成 pcap，用 Wireshark 分析

> 在某些系统里，tcpdump 默认只抓每帧前 96 字节，必须加 `-s 0` 才能看到完整 payload。

抓到的 66 字节小包通常对应 TCP 心跳（keep-alive），可以用：

```bash
sysctl -a | grep net.ipv4
```

确认 keep-alive 相关内核参数。

## 5. 一些 Socket 选项

- `TCP_NODELAY`：关 Nagle，小包延迟敏感场景常用
- `SO_KEEPALIVE` + `tcp_keepalive_*`：长连接探活
- `SO_LINGER`：控制 `close()` 时尚未发送数据的处理方式
- `SO_REUSEADDR` / `SO_REUSEPORT`：地址重用、多进程监听同端口

`SO_LOWDELAY` 在原始笔记里只留了个名字，实际平台支持有限，使用前先确认。

## 6. WebSocket 命令行调试

### 6.1 用 curl 发 Upgrade 请求

```bash
curl --include \
     --no-buffer \
     --header "Connection: Upgrade" \
     --header "Upgrade: websocket" \
     --header "Host: example.com:80" \
     --header "Origin: http://example.com:80" \
     --header "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
     --header "Sec-WebSocket-Version: 13" \
     http://example.com:80/
```

本地服务也是同样的写法，把地址换成 `127.0.0.1:<port>` 即可。

### 6.2 更顺手的工具：websocat

`curl` 只够确认握手能否完成，要实际发送 / 接收 WebSocket 帧时，更推荐用 `websocat`：

```bash
websocat ws://127.0.0.1:8123/
```

适合复现某个业务场景或快速验证服务端的消息编解码。

## 7. 排查顺序建议

按这个顺序通常更快：

1. 先用 `netstat -ant | awk` 看连接状态分布
2. `ss -l` 看监听队列是否打满
3. `netstat -s | grep overflowed` 看是否真的丢连接
4. `lsof -p` + 时间差对比找 fd 泄漏 / `CLOSE_WAIT` 来源
5. 必要时 `tcpdump` 抓包，再用 Wireshark 看握手 / RST / Keep-Alive 行为

## 8. 后续可补的方向

- 各内核参数（`tcp_tw_reuse`、`tcp_fin_timeout` 等）的取舍备忘
- `SO_REUSEPORT` 在多进程模型里的常见使用模式
- 用 `bpftrace` / `ss -ti` 替代 `strace` 的轻量观测
