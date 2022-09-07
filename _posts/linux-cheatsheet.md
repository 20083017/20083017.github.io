---
layout:     post
title:      linux指令整理
subtitle:   不适合阅读的整理的一些个人常用的 Linux 指令
date:       2022-09-08
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Linux
---

>随便整理的一些自用的Linux指令

# 二进制显示文件 linux
  
  od -tx1 -tc -Ax binFile

# 常用操作

#### awk-1
  cat 2.log | awk -F" " '{print $1" " $2" " $3" " $4}'  | sort -t' ' -k4 -rn
#### awk-2 统计log行数
	grep '2022-07-25 10:' service.log.2022072510 | awk -F' ' '{print $6}' | sort | uniq -c
#### IO 查询命令
  iostat 
  iotop
  lsof /dev/sda | grep head
  cat /proc/$id/io
  pidstat -d 1
  

#### 复制整个文件夹(使用r switch 并且指定目录)
  3-1 从本地文件复制整个文件夹到远程主机上（文件夹. 假如是diff）
  先进入本地目录下，然后运行如下命令：
  scp -v -r diff root@192.168.1.104:/usr/local/nginx/html/websroot@192.168.1.104:/usr/local/nginx/html/webs

  3-2 从远程主机复制整个文件夹到本地目录下（文件夹假如是diff）
  先进入本地目录下，然后运行如下命令：
  scp -r root@192.168.1.104:/usr/local/nginx/html/webs/diff .root@192.168.1.104:/usr/local/nginx/html/webs/diff .

#### perf
  每s采集99次,-p  pid
  perf record -F99 -g -a -e cpu-clock -p 23801
  perf report -i perf.data
  
#### top

top 重要:各个参数的含义, 系统cpu使用率, 业务CPU使用率,swap等   
[linux的top参数含义详解]https://www.cnblogs.com/ggjucheng/archive/2012/01/08/2316399.html

#### 查看线程cpu使用率
[线程cpu使用率]https://www.cnblogs.com/ghost240/p/3863774.html

#### 查看进程线程数量
	ps -T -p ${pid} 


#### 使用gcore
最初统计的时候，发现CPU高的情况会出现1秒多的时间，如果发现CPU高负载时，直接调用gcore {pid}的命令，可以保留堆栈信息，明确具体高负载的位置。

将使用gcore的指令，添加到统计工具中取，设置CPU上门限触发。

通过gdb看了几个coredump文件，发现堆栈和函数调用基本一致。可以明确的看到，大量的耗时发生在了AddActInfoV3这一函数中：
![image](https://user-images.githubusercontent.com/8308226/188916763-a1e6961a-3e46-407e-97db-465637353bbe.png)



