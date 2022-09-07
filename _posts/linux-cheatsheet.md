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


