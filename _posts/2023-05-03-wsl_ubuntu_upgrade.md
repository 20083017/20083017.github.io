---
layout:     post
title:      wsl_ubuntu_upgrade 指南
subtitle:   wsl ubuntu升级小记
date:       2023-05-03
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - windows10
    - ubuntu
    - wsl
---

>整理wsl升级ubuntu内核遇到的问题

# wsl_ubuntu_upgrade 指南

## 打开关闭虚拟化
```
打开 
bcdedit /set hypervisorlaunchtype auto
关闭
bcdedit /set hypervisorlaunchtype off
```

## Authentication failed
在 Ubuntu 上执行升级命令时提示以下报错   
```
# do-release-upgrade
Checking for a new Ubuntu release
Get:1 Upgrade tool signature [1,554 B]                                                                                
Get:2 Upgrade tool [1,319 kB]                                                                                         
Fetched 1,320 kB in 0s (0 B/s)                                                                                        
authenticate 'focal.tar.gz' against 'focal.tar.gz.gpg' 
Authentication failed
Authenticating the upgrade failed. There may be a problem with the network or with the server.
```
此问题一般是系统密钥出错导致的，因此重新安装即可解决。   
```
sudo apt install --reinstall ubuntu-keyring
```

配置网关  /etc/resolv.conf   


## upgrade 失败
apt-get update failed because certificate verification failed because handshake failed on nodesource
```
sudo apt install ca-certificates
```


# 报错 升级失败
```
This question already has answers here:
Can't upgrade to Ubuntu 21.04 : "Restoring original system state. Aborting" (3 answers)
Closed 1 year ago.
It's high time I upgrade Ubuntu from 18.04 to 20.04! But I don't get very far before the process aborts without an error message. Is there a log file I can check for further information?

$ uname -a
Linux tribble 5.4.72-microsoft-standard-WSL2 #1 SMP Wed Oct 28 23:40:43 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux

$ lsb_release -a
No LSB modules are available.
Distributor ID: Ubuntu
Description:    Ubuntu 18.04.5 LTS
Release:        18.04
Codename:       bionic

$ sudo do-release-upgrade
Checking for a new Ubuntu release
Get:1 Upgrade tool signature [1554 B]
Get:2 Upgrade tool [1340 kB]
Fetched 1342 kB in 0s (0 B/s)
authenticate 'focal.tar.gz' against 'focal.tar.gz.gpg'
extracting 'focal.tar.gz'
In the created screen:

Reading cache

Checking package manager
Reading package lists... Done
Building dependency tree
Reading state information... Done
Hit http://security.ubuntu.com/ubuntu bionic-security InRelease
Hit http://archive.ubuntu.com/ubuntu bionic InRelease
Hit http://ppa.launchpad.net/maxmind/ppa/ubuntu bionic InRelease
Hit http://archive.ubuntu.com/ubuntu bionic-updates InRelease
Hit http://archive.ubuntu.com/ubuntu bionic-backports InRelease
Hit https://packagecloud.io/cs50/repo/ubuntu bionic InRelease
Fetched 0 B in 0s (0 B/s)
Reading package lists... Done
Building dependency tree
Reading state information... Done
[LONG PAUSE]

Restoring original system state

Aborting
Reading package lists... Done
Building dependency tree
Reading state information... Done
=== Command terminated with exit status 1 (Thu Aug  5 02:10:50 2021) ===
```

## sudo apt-get purge snapd
https://askubuntu.com/questions/1356056/do-release-upgrade-silently-fails-upgrading-from-18-04-lts-to-20-04-lts-in-wsl

## 更新(K)Ubuntu 18.04至20.04后出现OpenMPI-bin错误
```
update-alternatives: error: /var/lib/dpkg/alternatives/mpi corrupt: slave link same as main link /usr/bin/mpicc
```
解决方式
首先删除openmpi的更新替代项：
```
sudo rm -f /etc/aternatives/mpi* /var/lib/dpkg/alternatives/mpi*
```
重新安装openmpi
```
sudo apt install open-mpi
```

## Failed to retrieve available kernel versions
Ubuntu 22.04 LTS on WSL: "Failed to retrieve available kernel versions"/"Failed to check for processor microcode upgrades" when installing packages

```
sudo vim /etc/needrestart/needrestart.conf

uncomment && change the setting

$nrconf{kernelhints} = 0;
$nrconf{ucodehints} = 0;
```




### 设置wsl 默认的编辑器
```
sudo update-alternatives --config editor
选择vim 或者 其他编辑器即可
git config --global core.editor vim
```

### 关闭dash
```
选择no，即可
sudo dpkg-reconfigure dash
```

### 橋接模式
 注意：windows 必須是11以上   
![image](https://github.com/20083017/20083017.github.io/assets/8308226/b02f3382-2ca0-4990-bc31-b880cebc9d39)


windows  powershell脚本   
```
# 检查并以管理员身份运行PS并带上参数
$currentWi = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentWp = [Security.Principal.WindowsPrincipal]$currentWi
if( -not $currentWp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
{
    $boundPara = ($MyInvocation.BoundParameters.Keys | foreach{'-{0} {1}' -f  $_ ,$MyInvocation.BoundParameters[$_]} ) -join ' '
    $currentFile = $MyInvocation.MyCommand.Definition
    $fullPara = $boundPara + ' ' + $args -join ' '
    Start-Process "$psHome\pwsh.exe"   -ArgumentList "$currentFile $fullPara"   -verb runas
    return
}
#首先随意执行一条wsl指令，确保wsl启动，这样后续步骤才会出现WSL网络
echo "正在检测wsl运行状态..."
wsl --cd ~ -e ls
echo "正在获取网卡信息..."
Get-NetAdapter
echo "`n正在将WSL网络桥接到以太网..."
Set-VMSwitch WSL -NetAdapterName wsl
echo "`n正在修改WSL网络配置..."
wsl --cd ~ -e sh -c ./set_eth0.sh
echo "`ndone"
pause

```

c/users/username/.wslconfig   
```
[wsl2]
networkingMode=bridged
vmSwitch=wsl
```

### 修改wsl 可用内存

```
[wsl2]
memory=2GB
swap=4GB
localhostForwarding=true

```

### wsl hosts 文件
```
# [network]
# generateHosts = false
```

wsl ip静态配置(未用到)   
```
# sudo ip addr del $(ip addr show eth0 | grep 'inet\b' | awk '{print $2}' | head -n 1) dev eth0
# sudo ip addr add 192.168.31.164/24 broadcast 192.168.31.255 dev eth0
# sudo ip route add 0.0.0.0/0 via 192.168.31.1 dev eth0
```


### wsl 与windows 时钟不同步
```
timedatectl set-local-rtc 1 --adjust-system-clock

timedatectl set-local-rtc 0 --adjust-system-clock  ok

  echo "source ~/update_time.sh" >> ~/.bashrc  打开shell，自动执行脚本

https://www.cnblogs.com/xiaotong-sun/p/16138941.html
```
update_time.sh   
```
#!bin/bash

sudo timedatectl set-local-rtc 0 --adjust-system-clock
```


### wsl 安装perf 工具
```
#!/bin/bash

# build-perf-wsl2.sh
# 自动化编译适用于当前 WSL2 内核的 perf 工具
# 作者：Qwen
# 使用方式：chmod +x build-perf-wsl2.sh && sudo ./build-perf-wsl2.sh

set -euo pipefail

REPO_URL="https://github.com/microsoft/WSL2-Linux-Kernel.git"
SRC_DIR="/tmp/WSL2-Linux-Kernel-perf"
PERF_BIN="/usr/local/bin/perf"

echo "🔍 正在获取当前内核版本..."
KERNEL_FULL=$(uname -r)
echo "VMLINUX: $KERNEL_FULL"

# 提取版本号，支持格式：
# 5.15.167.4-microsoft-standard-WSL2 → 5.15.167.4
# 5.15.167.4   → 5.15.167.4
KERNEL_VERSION=$(echo "$KERNEL_FULL" | grep -oE '^[0-9]+(\.[0-9]+){3}')

if [ -z "$KERNEL_VERSION" ]; then
    echo "❌ 无法从 '$KERNEL_FULL' 解析出版本号。"
    echo "   支持格式如：5.15.167.4 或 5.15.167.4-microsoft-standard-WSL2"
    exit 1
fi

echo "VMLINUX_VERSION: $KERNEL_VERSION"

# 目标 tag 可能的名字
TAG_EXACT="linux-msft-wsl-$KERNEL_VERSION"
TAG_V="v$KERNEL_VERSION"

echo "📁 准备源码目录: $SRC_DIR"
rm -rf "$SRC_DIR"
mkdir -p "$SRC_DIR"
cd "$SRC_DIR"

echo "🌀 克隆 WSL2 内核源码仓库..."
git clone "$REPO_URL" .
echo "✅ 仓库克隆完成"

echo "📥 正在拉取所有远程 tags..."
git fetch origin --tags --quiet
echo "✅ Tags 拉取完成"

# 查找匹配的 tag
MATCHED_TAG=""
if git show-ref -t --verify "refs/tags/$TAG_EXACT" > /dev/null 2>&1; then
    MATCHED_TAG="$TAG_EXACT"
elif git show-ref -t --verify "refs/tags/$TAG_V" > /dev/null 2>&1; then
    MATCHED_TAG="$TAG_V"
else
    # 模糊匹配：找最接近的版本（比如 5.15.167.x）
    BASE_VERSION=$(echo "$KERNEL_VERSION" | cut -d. -f1-3)  # 5.15.167
    CANDIDATES=$(git tag -l "linux-msft-wsl-$BASE_VERSION.*" | sort -V | tail -n 5)
    if [ -n "$CANDIDATES" ]; then
        echo "🟡 未找到精确匹配，尝试使用相近版本:"
        echo "$CANDIDATES"
        # 取最新一个
        MATCHED_TAG=$(echo "$CANDIDATES" | tail -n 1)
    fi
fi

if [ -z "$MATCHED_TAG" ]; then
    echo "❌ 未找到匹配的 tag (尝试过: $TAG_EXACT, $TAG_V)"
    echo "   请检查 https://github.com/microsoft/WSL2-Linux-Kernel/tags"
    exit 1
fi

echo "🎯 匹配到 tag: $MATCHED_TAG"

echo "🔄 切换到 tag: $MATCHED_TAG"
git checkout "$MATCHED_TAG" || {
    echo "❌ 切换 tag 失败"
    exit 1
}

# 创建本地分支避免 detached HEAD
BRANCH_NAME="perf-build-$KERNEL_VERSION"
git switch -c "$BRANCH_NAME"
echo "✅ 已创建并切换到分支: $BRANCH_NAME"

echo "🛠️  开始编译 perf..."
cd tools/perf

# 安装依赖（如果尚未安装）
if ! command -v libelf-dev &> /dev/null; then
    echo "📦 安装编译依赖..."
    apt-get update && apt-get install -y \
        libelf-dev \
        libdw-dev \
        binutils-dev \
        gcc \
        make \
        pkg-config
fi

echo "⚙️  执行 make..."
make -j$(nproc)

echo "✅ 编译完成"

echo "🚚 安装 perf 到 $PERF_BIN"
sudo cp perf "$PERF_BIN"
sudo chmod +x "$PERF_BIN"

echo "🎉 成功！perf 已安装"
"$PERF_BIN" --version

echo "✅ 验证: perf stat echo test"
"$PERF_BIN" stat echo "perf 已就绪"

echo "💡 使用方法: perf stat <command>, perf record <command>, 等"
```
