---
layout:     post
title:      KCP 协议笔记
subtitle:   设计目的、缓存控制、丢包模拟与 TCP 单连接吞吐推导
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - 网络
    - KCP
    - TCP
---

>原始笔记基本上是几段从 issue / wiki 摘录下来的内容拼接而成，一段未拆分的引用块里塞了 KCP 设计目的、Latency vs RTT 的辩论、benchmark 图说明等多种信息。这里按"设计目的 / 缓存控制（三类业务场景）/ FEC / 多路复用 / 丢包模拟工具 / TCP 单连接吞吐推导"分节整理，原文与命令保持不动。

## 当前保留内容

### 1. KCP 的设计目的

```
不是为流量设计的（每秒钟多少 KB），是为流速设计的（RTT）

KCP 设计目的是比 TCP 更低的 Latency/RTT，而不是更好的带宽利用率或者 KB/s，那么：

当你的传输速率接近物理带宽极限时，由于 TCP 带宽利用率更充分，所以 TCP 会更快（KB/s）。
当你的传输没有到物理带宽极限时，当有丢包发生时，KCP 会更快（KB/s）。
当你的传输没有到物理带宽极限时，当没有丢包发生时，两个一样快（KB/s）。
那么为什么经常有用 kcp 加速 VPS 翻墙和音视频推流呢？因为一般你上一下 youtube 或者传递下音视频流，带宽远没有达到物理上限（不是你这种 iperf 要榨干网络的传输法），比如公网高峰期 5%-10%的丢包的时候，远距离传输的时候，此时物理带宽的上限远没达到，但是因为延迟和丢包率的存在，导致 tcp 的 latency 极高，KB/s 也上不去，这也是最常见的情况，此时 KCP 的加速效果明显，不管对 Latency 和 KB/s。

理解这个原理你就不会用榨干网络带宽的方式来测试 KB/s 了。

RTT 30%, 40% 的降低哪里来的？
真实产品 100 多万用户同时在线测试出来的，模拟丢包测试出来的，取个平均值。

我自己应用过 KCP 的项目，基本都测试过：
https://github.com/skywind3000/kcp/wiki/HISTORY

不止我一个人测试，数个团队分别不同层面测试，结论相同。

RTT 本身很大程度上是取决于本身网络链路状态，类似于网络的一个基本属性。测试数据也显示并不能有什么提升。

你说的 RTT 是物理级别 UDP / ICMP 的 round-trip-time，我指的 RTT 是数据经过 TCP/KCP 之类可靠协议传输走一圈的时间，只要没有触碰到物理带宽上限，当然会比 TCP 快很多，这个数值的测试，KCP 首页末尾也提到了很多，他们的程序和测试环境描述都放在那里，你感兴趣自己去看。

test.cpp 也模拟了不同延迟和丢包情况下，这些策略的开关到底能带来多大的提升。这么明显的区别你但凡看过一下都不会说出 "很大程度上是取决于本身网络链路状态" 这种话来。

为了准确交流，RTT 指代网络物理层的 udp/icmp ping 值，而 Latency 指数据经过可靠协议传输后走一圈的延迟。标准 Latency 测试要怎么测呢？不是简单弄个 KB/s，你先要画一张表：

丢包/延迟	10ms	50ms	100ms	200ms
0%	..	..	..	..
5%	..	..	..	..
10%	..	..	..	..
15%	..	..	..	..
20%	..	..	..	..
然后针对每一种情况，计算出一个平均延迟来，比如下面这张图，就是网络延迟 300 毫秒，丢包率 20% 的情况，多种不同的协议传输延迟（Latency）分布图：

benchmark

横坐标是延迟，纵坐标是该协议有百分之多少的样本延迟小于等于横坐标代表的值。

举个例子：

青色圆圈，就是 TCP，在上面所述的网络条件下 50% 的样本落在了 542ms 范围内，而 70% 的样本能够落在 800ms 范围内。
对比裸 KCP 绿色三角（P1），72% 的样本能够落在 542ms 的范围内，90%的样本落在了 600ms 范围内。
对比 KCP+FEC 黑色十字（P3），98% 的样本落到了 416ms 的范围内。
而青色方块（P4），是未经任何可靠协议处理的，裸 UDP RTT 时间，你可以理解成网络 RTT 的物理下限，协议做的好，就是无限制的靠近这条青色方块线，协议做的差就会远离。

在上面这个图中，就所有样本的平均延迟而言，KCP 472ms 同时 TCP 是 698ms，而最大延迟，KCP 比 TCP 低很多倍（记不得了）。

对每种不同网络情况，都做这么一张图，都得到一个平均延迟和最大延迟，填到上面的表上去，30%-40%就是这么测试出来的，搞明白了么？
```

![image](https://github.com/user-attachments/assets/65f464ed-224f-41af-ab6f-c00fee7f77ca)

### 2. 缓存控制

参考：<https://github.com/skywind3000/kcp/wiki/Flow-Control-for-Users>

#### 2.1 游戏控制数据

```
缓存控制：游戏控制数据
大部分逻辑严密的 TCP游戏服务器，都是使用无阻塞的 tcp链接配套个 epoll之类的东西，当后端业务向用户发送数据时会追加到用户空间的一块发送缓存，比如 ring buffer 之类，当 epoll 到 EPOLL_OUT 事件时（其实也就是tcp发送缓存有空余了，不会EAGAIN/EWOULDBLOCK的时候），再把 ring buffer 里面暂存的数据使用 send 传递给系统的 SNDBUF，直到再次 EAGAIN。

那么 TCP SERVER的后端业务持续向客户端发送数据，而客户端又迟迟没能力接收怎么办呢？此时 epoll 会长期不返回 EPOLL_OUT事件，数据会堆积在该用户的 ring buffer 之中，如果堆积越来越多，ring buffer 会自增长的话就会把 server 的内存给耗尽。因此成熟的 tcp 游戏服务器的做法是：当客户端应用层发送缓存（非tcp的sndbuf）中待发送数据超过一定阈值，就断开 TCP链接，因为该用户没有接收能力了，无法持续接收游戏数据。

使用 KCP 发送游戏数据也一样，当 ikcp_waitsnd 返回值超过一定限度时，你应该断开远端链接，因为他们没有能力接收了。

但是需要注意的是，KCP的默认窗口都是32，比tcp的默认窗口低很多，实际使用时应提前调大窗口，但是为了公平性也不要无止尽放大（不要超过1024）

```

#### 2.2 传送文件

```
缓存控制：传送文件
你用 tcp传文件的话，当网络没能力了，你的 send调用要不就是阻塞掉，要不就是 EAGAIN，然后需要通过 epoll 检查 EPOLL_OUT事件来决定下次什么时候可以继续发送。

KCP 也一样，如果 ikcp_waitsnd 超过阈值，比如2倍 snd_wnd，那么停止调用 ikcp_send，ikcp_waitsnd的值降下来，当然期间要保持 ikcp_update 调用。
```

#### 2.3 实时视频直播

```
缓存控制：实时视频直播
视频点播和传文件一样，而视频直播，一旦 ikcp_waitsnd 超过阈值了，除了不再往 kcp 里发送新的数据包，你的视频应该进入一个 "丢帧" 状态，直到 ikcp_waitsnd 降低到阈值的 1/2，这样你的视频才不会有积累延迟。

这和使用 TCP推流时碰到 EAGAIN 期间，要主动丢帧的逻辑时一样的。

同时，如果你能做的更好点，waitsnd 超过阈值了，代表一段时间内网络传输能力下降了，此时你应该动态降低视频质量，减少码率，等网络恢复了你再恢复。
```

### 3. 丢包率高的情况下提高传输效率：FEC

```
高丢包率的情况下使用
https://github.com/cnbatch/kcptube/blob/main/docs/fec_zh-hans.md
```

### 4. KCP 如何计算丢包率

（待补充。）

### 5. 多路复用

```
建立多个连接？  连接太多会导致cpu占用升高，比如同时建立 tcp udp
client 端功能
```

### 6. 模拟丢包工具（tc + netem）

#### 6.1 随机丢包 10%

```
sudo tc qdisc add dev eth0 root netem loss 10%
```

#### 6.2 延迟 40ms

```
sudo tc qdisc add dev eth0 root netem delay 40ms
```

#### 6.3 仅作用于某个地址

```
sudo tc qdisc add dev eth0 root handle 1: prio
sudo tc qdisc add dev eth0 parent 1:3 handle 30: netem loss 13% delay 40ms
sudo tc filter add dev eth0 protocol ip parent 1:0 u32 match ip dst 199.91.72.192 match ip dport 36000 0xffff flowid 1:3
```

上面的命令告诉 tc，对发往 `199.91.72.192:36000` 的网络包产生 13% 的丢包和 40ms 的延迟，而发往其它目的地址的网络包将不受影响。

#### 6.4 删除规则

```
sudo tc qdisc del dev eth0 root
```

### 7. 为什么单个 TCP 连接很难占满带宽

```
计算 TCP吞吐量的公式

TCP窗口大小(bits) / 延迟(秒) = 每秒吞吐量(bits)

比如说windows系统一般的窗口大小为64K， 中国到美国的网络延迟为150ms.

64KB = 65536 Bytes. 65536 * 8 = 524288 bits

每秒吞吐量(bits) = 524288 / 0.15 = 3495253 bit/s = 0.41MB/S

所以就算是10M专线，那么单个Tcp连接也最大只能达到0.41M的速度。

计算最优 TCP窗口大小 的公式

带宽(bits每秒) * 往返延迟(秒) = TCP窗口大小(bits) / 8 = TCP窗口大小(字节)

因此在芝加哥和纽约之间 10M 的带宽和 150ms 的延迟的例子中，可以计算如下：

10 * 1024* 1024 bps * 0.15 seconds = 1572864 bits / 8 = 1,572,864 Bytes = 1.5 MB
```

## 后续可补的方向

- 把 KCP 关键参数（`nodelay` / `interval` / `resend` / `nc` / `snd_wnd` / `rcv_wnd`）的取值与场景对照表沉淀下来。
- 给出一份本机 `tc + netem` + KCP 参数扫描脚本，可以自动生成"丢包/延迟 vs Latency"表格。
- 补一节"KCP 如何计算丢包率"的源码走读，对应 `ikcp.c` 中的 `xmit / lost / rttvar`。
