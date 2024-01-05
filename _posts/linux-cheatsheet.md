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

#### strace 系统函数trace
	/usr/bin/strace  -o output2.txt -T -tt -e trace=all ./chat
	/usr/bin/strace -tt -T -v -f -e trace=file -o strace1.log -s 1024 ./chat
	/usr/bin/strace -tt -T -v -f -e trace=file -o strace1.log -s 1024 -p pid
#### ltrace 库函数trace
 
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
  
#### CPU使用率低但是负载高   
当系统负载高时，并不意味着CPU资源不足，只是意味着运行的任务过多，这些任务有可能在等待或者使用cpu，也有可能等待IO完成   

当系统负载高，并且CPU使用率也比较高时，一般意味着CPU资源不足   

而当系统负载高，而CPU使用率比较低时，一般有如下两种情况   

CPU频繁的进行上下文切换（比如应用中开启了太多的线程），导致任务执行的时间比较短（利用vmstat命令查看，如果cs列或in列的值很大，说明就是这种情况）   
IO任务太多，导致大量进程处于不可中断状态（利用top命令查看，cpu使用百分比中，wa状态（cpu等待io完成）的使用百分比很高时，说明就是这种情况）   
执行vmstat，查看in列（每秒中断的次数）和cs列（每秒上下文切换次数）比较高，则表明CPU频繁的进行上下文切换    
top发现cpu的iowait比较高（wa列的值），则利用I/0问题排查套路接着排查   
  
#### 如果我们希望对特定的进程进行监控，可以使用pidstat -w命令
pidstat是sysstat工具的一个命令，用于监控全部或指定进程的cpu、内存、线程、设备IO等系统资源的占用情况

pidstat首次运行时显示自系统启动开始的各项统计信息，之后运行pidstat将显示自上次运行该命令以后的统计信息。用户可以通过指定统计的次数和时间来获得所需的统计信息   

```
# 每隔3s输出一次数据
[root@VM-0-14-centos ~]# pidstat -w 3
Linux 3.10.0-1127.19.1.el7.x86_64 (VM-0-14-centos)      10/10/2021      _x86_64_        (2 CPU)

08:13:38 PM   UID       PID   cswch/s nvcswch/s  Command
08:13:41 PM     0         6      1.66      0.00  ksoftirqd/0
08:13:41 PM     0         7      0.33      0.00  migration/0
08:13:41 PM     0         9     20.27      0.00  rcu_sched
```

结果中的cswch和nvcswch是我们需要重点关注的对象   

cswch（自愿上下文切换）：进程无法获取所需要的资源，导致的上下文切换。例如IO，内存等系统资源不足时，就会发生自愿上下文切换 nvcswch（非自愿上下文切换）：进程由于时间片已到等愿意，被系统强制调度，进而发生的上下文切换。比如，当大量进程都在争抢CPU时，就容易发生非自愿上下文切换   
  

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

### 查看cpu核数
```
grep 'model name' /proc/cpuinfo | wc -l
```

cpu密集型进程/IO密集型进程/大量等待cpu调度进程均会导致负载高，但是IO密集型进程不会导致cpu利用率高

sysstat包含常用性能工具，其中 mpstat 和 pidstat 分别查看cpu利用率和进程占用情况的工具 , vmstat 分析系统性能的工具

```
# -P ALL 表示监控所有cpu，后面的数字5表示间隔5s输出一组数据
mpstat -P ALL 5

```

### 节点负载高的排查方法

uptime 查看负载变化情况
通过 mpstat 查看cpu计算量大还是进程争抢大或者io过多

iowait表示等待io多，cpu表示cpu本身的消耗，根据 二者数值可以判断是计算密集型还是io密集型。


### 查看进程负载高
```
# 间隔5s输出一组数据，只输出一次
pidstat -u 5 1
```
如果，cpu高，iowait低，说明是纯计算密集型；如果cpu低，iowait高，纯io密集型，io包含网络io，磁盘io。二者都高，可以继续查看队列情况，上下文切换次数和类型进一步判断。

查看整体的上下文切换情况及队列长度，队列长度大于核数说明负载高。

```
每隔5s输出1组数据

vmstat 5

# r 表示就绪队列长度
# cs 表示上下文切换次数
# in 表示每s中断次数
# b 表示处于不可中断睡眠状态的进程数
```

### 查看每个进程的上下文切换种类

```
# 每隔5s输出一组数据 
pdistat -w 5

#cswch 进程每s自愿上下文切换次数，说明进程都在等其他资源，如io
#nvswch 进程每s非资源上下文切换次数，等待线程过多
#自愿 一般情况下在资源不足，无法获取资源的情况下出现，非自愿 一般在大量线程进行cpu争用的时候出现
#pidstat 默认展示进程数据， 增加-t 参数显示线程数据
```


### 
```
ls -l 4472_gid | awk -F' ' '{print $9}' | xargs -i sh -c  'cat 4472_gid/{}' |  xargs -i sh -c  'echo -n  {} " "; echo  "get ig_{}" | ../redis-cli -h ip -p 9000;'  | grep 4472 >> new_t.txt &
```

###  ssh 连接iot设备
ssh -oHostKeyAlgorithms=+ssh-dss root@192.168.8.109









