---
layout:     post
title:      Socket问题排查整理
subtitle:   不适合阅读的整理的一些个人常用的 Socket参数 整理
date:       2022-09-09
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Socket
---

>随便整理的一些自用的Git指令


# Socket参数整理
一、Accept Queue检查
* accept queue is full，且tcp_abort_on_overflow=1
1. cat /proc/sys/net/ipv4/tcp_abort_on_overflow
* accept queue默认长度只有50（通过backlog设置）
1. ss -l|grep 89.*0
2. 050*:::8920*:*:*:*
3. 050*:::8930*:*:*:*
* accept queue溢出，通过观察这个统计值发现出现这种情况时该统计值会增加
1. netstat -s|grep overflowed
2. 13924575 times the listen queue ofasocket overflowedthe listen queue ofasocket overflowedthe listen queue ofasocket overflowed
二、sysctl内核参数检查
* linux内核参数优化
     net.ipv4.tcp_syncookies = 1
     net.ipv4.tcp_max_syn_backlog = 16384
     net.core.somaxconn=16384

* nginx配置参数优化
     backlog = 32768

关闭nagle算法 tcp_no_delay
so_sendbuf,so_recvbuf 设置问题，建议不设置？

三、 netstat -antp | grep 端口
      查看端口状态，发现所有端口均处于 closewait 状态

     压测demo中无closesocket逻辑，添加closesocket后修复。

四、 ulimit -a
       系统允许大开的fd数量
     lsof -p  pid |  wc -l
     某进程已经打开的fd数量

进程允许大开最大fd数量

lsof -p pid 可得知， 16520 fd 泄露

strace + lsof 能解决大部分fd泄漏的问题,
strace -f -p 4730 -T -tt -o /home/futi/strace_4730.log

strace -f -F -o dcop-strace.txt dcopserver
这里 -f -F选项告诉strace同时跟踪fork和vfork出来的进程，-o选项把所有strace输出写到dcop-strace.txt里 面，dcopserver是要启动和调试的程序

tcp 连接数 

netstat -ant|awk '/^tcp/ {++S[$NF]} END {for(a in S) print (a,S[a])}'


2.检查程序问题
  如果你对你的程序有一定的解的话，应该对程序打开文件数(链接数)上限有一定的估算，如果感觉数字异常，请使用第一步的lsof -p 进程id > openfiles.log命令，获得当前占用句柄的全部详情进行分析
  
  对比2个时间点 lsof -p pid， 调用存在 cann't identify protocol 问题。


![image](https://user-images.githubusercontent.com/8308226/188905265-46e478e0-ba94-4516-aab9-75c7d7b7b3f0.png)


所以，触发rst操作是因为client端存在未处理完消息的情况下，就关闭socket，为不合理操作。

tcpdump，wireshark 抓包分析
这种情况一般是由抓包方式引起的。在有些操作系统中，tcpdump默认只抓每个帧的前96个字节，我们可以用“-s”参数来指定想要抓到的字节数，比如下面这条命令可以抓到1000字节。
tcpdump tcp -i xgbe0  -t -s 0 -c 100 and dst port 8863 and src net 10.128.161.11 -w ./target.cap
tcpdump tcp -i xgbe0  -t -s 0 -c 2000 and net 10.128.161.15 and  net 10.128.161.11 -w ./target.cap

tcpdump -i any port 4012 -w server.pcap
* tcp: ip icmp arp rarp 和 tcp、udp、icmp这些选项等都要放到第一个参数的位置，用来过滤数据报的类型
* -i eth1 : 只抓经过接口eth1的包
* -t : 不显示时间戳
* -s 0 : 抓取数据包时默认抓取长度为68字节。加上-S 0 后可以抓到完整的数据包
* -c 100 : 只抓取100个数据包
* dst port ! 22 : 不抓取目标端口是22的数据包
* src net 192.168.1.0/24 : 数据包的源网络地址为192.168.1.0/24
* -w ./target.cap : 保存成cap文件，方便用ethereal(即wireshark)分析


tcp选项 keepalive 查看
sysctl -a | grep net.ipv4
wireshark 抓包，66字节表示 tcp 心跳协议，未关闭。


