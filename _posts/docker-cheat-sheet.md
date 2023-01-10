环境说明：
当前文档针对公司当前大部分开发机的版本：
$ cat /etc/issue
CentOS release 6.3 (Final)
$ uname -r
3.10.0.514.26.2.el7.x86_64
一、挂载 cgroup
1. root权限执行 Docker官网上提供的脚本：cgroupfs-mount

    #!/bin/sh
    #copyright 2011 Canonical, Inc
    #           2014 Tianon Gravi
    # Author: Serge Hallyn <serge.hallyn@canonical.com>
    #         Tianon Gravi <tianon@debian.org>
    set -e

    # for simplicity this script provides no flexibility

    # if cgroup is mounted by fstab, don't run
    # don't get too smart - bail on any uncommented entry with 'cgroup' in it
    if grep -v '^#' /etc/fstab | grep -q cgroup; then
            echo 'cgroups mounted from fstab, not mounting /sys/fs/cgroup'
            exit 0
    fi

    # kernel provides cgroups?
    if [ ! -e /proc/cgroups ]; then
            exit 0
    fi

    # if we don't even have the directory we need, something else must be wrong
    if [ ! -d /sys/fs/cgroup ]; then
            exit 0
    fi

    # mount /sys/fs/cgroup if not already done
    if ! mountpoint -q /sys/fs/cgroup; then
            mount -t tmpfs -o uid=0,gid=0,mode=0755 cgroup /sys/fs/cgroup
    fi

    cd /sys/fs/cgroup

    # get/mount list of enabled cgroup controllers
    for sys in $(awk '!/^#/ { if ($4 == 1) print $1 }' /proc/cgroups); do
            mkdir -p $sys
            if ! mountpoint -q $sys; then
                    if ! mount -n -t cgroup -o $sys cgroup $sys; then
                            rmdir $sys || true
                    fi
            fi
    done


    # example /proc/cgroups:
    #  #subsys_name hierarchy       num_cgroups     enabled
    #  cpuset       2       3       1
    #  cpu  3       3       1
    #  cpuacct      4       3       1
    #  memory       5       3       0
    #  devices      6       3       1
    #  freezer      7       3       1
    #  blkio        8       3       1

    # enable cgroups memory hierarchy, like systemd does (and lxc/docker desires)
    # https://github.com/systemd/systemd/blob/v245/src/core/cgroup.c#L2983
    # https://bugs.debian.org/940713
    if [ -e /sys/fs/cgroup/memory/memory.use_hierarchy ]; then
            echo 1 > /sys/fs/cgroup/memory/memory.use_hierarchy
    fi

    exit 0

2. 确认是否成功挂载
$ df -h
Filesystem Size Used Avail Use% Mounted on
/dev/vda1 40G 12G 27G 30% /
cgroup 16G 0 16G 0% /sys/fs/cgroup

二、搭建网桥
$ brctl addbr docker0
$ ip addr add 10.0.4.1/24 dev docker0
$ ip link set dev docker0 up
$ brctl show
bridge name bridge id STP enabled interfaces
docker0 8000.000000000000 no


三、安装docker
$ mkdir /tmp/docker_install && cd /tmp/docker_install
$ wget "http://koala.dmop.baidu.com:8080/fc/getfilebyid?id=8829" -O docker-1.12.5.tar.gz && tar -zxvf docker-1.12.5.tar.gz && rm -rf docker-1.12.5.tar.gz
$ mv docker/* /usr/bin && rm -rf docker
四、启动
1、配置仓库
$ vim /etc/docker/daemon.json
仓库配置文件，增加如下内容
{
  "insecure-registries" : ["",""],
  "graph":"/var/lib/docker"
}
将默认路径调整，否则容易出现，no space left。
如果保存不了，可能是没有 docker 文件夹，先 mkdir /etc/docker
2、启动
$ nohup /usr/bin/dockerd --bip=10.0.4.1/24 -H tcp://0.0.0.0:2375 -H unix:///var/run/docker.sock >/dev/null 2>/dev/null &
$ nohup /usr/bin/dockerd --bip=10.0.4.1/24 -H tcp://127.0.0.1:2375 -H unix:///var/run/docker.sock >/dev/null 2>/dev/null &
【注】：docker重启
1. kill -9 pid
2. 运行上面的启动命令即可










docker 命令
https://www.runoob.com/docker/docker-image-usage.html

docker rmi -f name:tag
docker rmi -f imageid


docker run -u root -t -i  bca1732dcdeb   /bin/bash




