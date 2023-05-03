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

#### dmesg
```
unix_time=echo "$(date +%s) - $(cat /proc/uptime | cut -f 1 -d' ') + 12106473.374733" | bc

输出结果 s 转换为 unix时间
```

#### strace
	/usr/bin/strace  -o output2.txt -T -tt -e trace=all ./chat
	/usr/bin/strace -tt -T -v -f -e trace=file -o strace1.log -s 1024 ./chat
	/usr/bin/strace -tt -T -v -f -e trace=file -o strace1.log -s 1024 -p pid
#### pstack gstack

#### proc
/proc/N/fd
/proc/net/tcp

以上2个，配合使用可以定位 socket fd的连接。

/proc/locks
/proc/cmdline

## 清理线上大文件，先设置低优先级，再删除
考虑到对线上服务 IO 造成的影响，应该将大文件 mv 走之后，设置操作为低优先级再执行
mv ... && cd .. && nice -n 6 "${command}"

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
	ps -T -H ${pid}   

#### ip 正则  
ip grep   
grep -E "[^^][0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}"   
grep -oE "[^^][0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}"   3.log   --col  

#### xargs 执行shell
	cat 2.txt | xargs -I {} sh -c {}  或者 -i 如果-I报错的话。
#### scp	
scp output/bin/test {user}@{host}:{path}  
scp -v -r yun_conf {user}@{host}:{path}  
#### 使用gcore
最初统计的时候，发现CPU高的情况会出现1秒多的时间，如果发现CPU高负载时，直接调用gcore {pid}的命令，可以保留堆栈信息，明确具体高负载的位置。

将使用gcore的指令，添加到统计工具中取，设置CPU上门限触发。

通过gdb看了几个coredump文件，发现堆栈和函数调用基本一致。可以明确的看到，大量的耗时发生在了AddActInfoV3这一函数中：
![image](https://user-images.githubusercontent.com/8308226/188916763-a1e6961a-3e46-407e-97db-465637353bbe.png)

#### vmtouch
查看linux文件的pagecache情况-vmtouch   

vmtouch - the Virtual Memory Toucher 就是用来查看linux文件缓存（page cache）使用情况，命中率   
现网是真正提升能力的地方,因为机器高负载之后,会出现各种各样的问题,包括很很多"假象". 而机器高负载的原因很多,比如内存. 之前遇到的问题就是, pagecache使用过多,导致内存不足,然后接着cpu飙升,> 严重影响业务质量.这就是为什么要搞个vmtouch的原因. 我要查看哪些文件大量使用page cache， 然后好直接 echo 3 > /proc/sys/vm/drop_caches ,暴力清除缓存   


#### 合并txt文件
```
ls *.txt |
while read file_name;
do
    # 用.为分隔符只要文件名，去掉文件后缀
    cat "$file_name" >> all.txt
    echo "" >> all.txt
done
```

#### 查看符号
nm bin文件

#### 查看依赖的so文件
ldd bin文件


### ssh + rsync 互传文件，rsync断点续传
```
 Start port forwarding backend
ssh -f -N -L 1234:HostC:22 user@HostB
# You can
# 1. Either, login HostC from port 1234 on localhost
ssh -p 1234 user@localhost
# 2. OR, scp directly
scp -p 1234 src_dir/ user@localhost:target_dir/
```
```
# upload
rsync -P --rsh='ssh -p 1234' /data/myfile user@localhost:/data/
# download
rsync -P --rsh='ssh -p 1234' user@localhost:/data/myfile /data/
```


