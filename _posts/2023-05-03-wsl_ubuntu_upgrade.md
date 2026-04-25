---
layout:     post
title:      WSL Ubuntu 升级与配置小记
subtitle:   虚拟化开关、do-release-upgrade 报错、桥接模式、wsl 资源与 perf 编译脚本
date:       2023-05-03
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - WSL
    - Ubuntu
    - Windows
    - Linux Kernel
---

>原始笔记把 WSL 升级踩到的坑、网络配置和 perf 编译脚本堆在一起，这里按「升级 / 配置 / 工具」三块整理，原始命令尽量保留。

## 1. Hyper-V / 虚拟化开关

WSL2 依赖 Windows Hypervisor，必要时可以临时关闭虚拟化（例如调试 VirtualBox 等三方虚拟机）：

```powershell
# 打开
bcdedit /set hypervisorlaunchtype auto

# 关闭
bcdedit /set hypervisorlaunchtype off
```

切换后需要重启 Windows 才会生效。关闭后 WSL2 也会失效，记得用完再切回 `auto`。

## 2. `do-release-upgrade` 常见报错

### 2.1 `Authentication failed`

```text
authenticate 'focal.tar.gz' against 'focal.tar.gz.gpg'
Authentication failed
```

通常是系统密钥损坏，重新安装一次即可：

```bash
sudo apt install --reinstall ubuntu-keyring
```

如果是 DNS 问题（拉不到 keyring 列表），先确认 `/etc/resolv.conf` 配置正确。

### 2.2 升级直接 `Restoring original system state. Aborting`

```text
Hit http://archive.ubuntu.com/ubuntu bionic InRelease
...
[LONG PAUSE]
Restoring original system state
Aborting
```

WSL2 上从 18.04 升到 20.04 时，最常见原因之一是 `snapd`。原始笔记里保留的解法是先把 snap 清理掉，再 `do-release-upgrade`：

```bash
sudo apt-get purge snapd
```

参考：<https://askubuntu.com/questions/1356056/do-release-upgrade-silently-fails-upgrading-from-18-04-lts-to-20-04-lts-in-wsl>

### 2.3 升级后 OpenMPI 报 `update-alternatives` 错误

```text
update-alternatives: error: /var/lib/dpkg/alternatives/mpi corrupt:
  slave link same as main link /usr/bin/mpicc
```

清理掉 mpi 的 alternatives 后重装：

```bash
sudo rm -f /etc/alternatives/mpi* /var/lib/dpkg/alternatives/mpi*
sudo apt install open-mpi
```

### 2.4 Ubuntu 22.04 上 `Failed to retrieve available kernel versions`

`needrestart` 在 WSL2 下检测内核 / microcode 升级会失败，关掉对应提示即可：

```bash
sudo vim /etc/needrestart/needrestart.conf

# 取消注释并改为：
$nrconf{kernelhints} = 0;
$nrconf{ucodehints}  = 0;
```

## 3. 一些常用 WSL 配置

### 3.1 设置默认编辑器

```bash
sudo update-alternatives --config editor      # 选 vim 或其它
git config --global core.editor vim
```

### 3.2 关闭 dash（让 sh 指向 bash）

```bash
sudo dpkg-reconfigure dash
# 选 No 即可
```

### 3.3 桥接模式（Windows 11+）

WSL2 桥接模式需要 Windows 11 或更高版本。

`%UserProfile%\.wslconfig`：

```ini
[wsl2]
networkingMode=bridged
vmSwitch=wsl
```

Windows 侧可以用一份 PowerShell 脚本自动准备好桥接环境（要求以管理员身份执行）：

```powershell
# 检查并以管理员身份重新启动 PowerShell
$currentWi = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentWp = [Security.Principal.WindowsPrincipal]$currentWi
if (-not $currentWp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $boundPara = ($MyInvocation.BoundParameters.Keys |
        ForEach-Object { '-{0} {1}' -f $_, $MyInvocation.BoundParameters[$_] }) -join ' '
    $currentFile = $MyInvocation.MyCommand.Definition
    $fullPara = $boundPara + ' ' + ($args -join ' ')
    Start-Process "$psHome\pwsh.exe" -ArgumentList "$currentFile $fullPara" -Verb runas
    return
}

# 先随意执行一条 wsl 指令，确保 WSL 启动，否则不会出现 WSL 网络
Write-Output "正在检测 WSL 运行状态..."
wsl --cd ~ -e ls

Write-Output "正在获取网卡信息..."
Get-NetAdapter

Write-Output "`n正在将 WSL 网络桥接到以太网..."
Set-VMSwitch WSL -NetAdapterName wsl

Write-Output "`n正在修改 WSL 网络配置..."
wsl --cd ~ -e sh -c ./set_eth0.sh

Write-Output "`ndone"
pause
```

### 3.4 限制 WSL2 可用内存

`%UserProfile%\.wslconfig`：

```ini
[wsl2]
memory=2GB
swap=4GB
localhostForwarding=true
```

### 3.5 hosts 文件托管

如果不想让 WSL 自动覆盖 `/etc/hosts`：

```ini
# /etc/wsl.conf
[network]
generateHosts = false
```

### 3.6 WSL ip 静态配置（备份用）

实际很少用到，按需启用：

```bash
sudo ip addr del $(ip addr show eth0 | grep 'inet\b' | awk '{print $2}' | head -n 1) dev eth0
sudo ip addr add 192.168.31.164/24 broadcast 192.168.31.255 dev eth0
sudo ip route add 0.0.0.0/0 via 192.168.31.1 dev eth0
```

### 3.7 WSL 与 Windows 时钟不同步

```bash
# 让系统使用 UTC，并以 UTC 重置硬件时钟
sudo timedatectl set-local-rtc 0 --adjust-system-clock
```

也可以把校时脚本挂到 `~/.bashrc`：

```bash
echo "source ~/update_time.sh" >> ~/.bashrc
```

`update_time.sh`：

```bash
#!/bin/bash
sudo timedatectl set-local-rtc 0 --adjust-system-clock
```

参考：<https://www.cnblogs.com/xiaotong-sun/p/16138941.html>

## 4. 在 WSL2 上编译 `perf`

WSL2 自带的 `perf` 经常没有，或与当前内核版本对不上。下面这份脚本会自动：

1. 解析当前内核版本
2. 拉 `microsoft/WSL2-Linux-Kernel` 仓库
3. 找到匹配 / 相近的 tag
4. 编译 `tools/perf` 并安装到 `/usr/local/bin/perf`

`build-perf-wsl2.sh`：

```bash
#!/bin/bash
# 自动化编译适用于当前 WSL2 内核的 perf 工具
# 使用方式：chmod +x build-perf-wsl2.sh && sudo ./build-perf-wsl2.sh

set -euo pipefail

REPO_URL="https://github.com/microsoft/WSL2-Linux-Kernel.git"
SRC_DIR="/tmp/WSL2-Linux-Kernel-perf"
PERF_BIN="/usr/local/bin/perf"

echo "🔍 正在获取当前内核版本..."
KERNEL_FULL=$(uname -r)
echo "VMLINUX: $KERNEL_FULL"

# 提取版本号，支持下面两种格式：
#   5.15.167.4-microsoft-standard-WSL2 → 5.15.167.4
#   5.15.167.4                         → 5.15.167.4
KERNEL_VERSION=$(echo "$KERNEL_FULL" | grep -oE '^[0-9]+(\.[0-9]+){3}')

if [ -z "$KERNEL_VERSION" ]; then
    echo "❌ 无法从 '$KERNEL_FULL' 解析出版本号。"
    echo "   支持格式如：5.15.167.4 或 5.15.167.4-microsoft-standard-WSL2"
    exit 1
fi

echo "VMLINUX_VERSION: $KERNEL_VERSION"

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
    BASE_VERSION=$(echo "$KERNEL_VERSION" | cut -d. -f1-3)
    CANDIDATES=$(git tag -l "linux-msft-wsl-$BASE_VERSION.*" | sort -V | tail -n 5)
    if [ -n "$CANDIDATES" ]; then
        echo "🟡 未找到精确匹配，尝试使用相近版本:"
        echo "$CANDIDATES"
        MATCHED_TAG=$(echo "$CANDIDATES" | tail -n 1)
    fi
fi

if [ -z "$MATCHED_TAG" ]; then
    echo "❌ 未找到匹配的 tag (尝试过: $TAG_EXACT, $TAG_V)"
    echo "   请检查 https://github.com/microsoft/WSL2-Linux-Kernel/tags"
    exit 1
fi

echo "🎯 匹配到 tag: $MATCHED_TAG"
git checkout "$MATCHED_TAG" || { echo "❌ 切换 tag 失败"; exit 1; }

BRANCH_NAME="perf-build-$KERNEL_VERSION"
git switch -c "$BRANCH_NAME"
echo "✅ 已创建并切换到分支: $BRANCH_NAME"

echo "🛠️  开始编译 perf..."
cd tools/perf

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
make -j"$(nproc)"
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

## 5. 后续可补的方向

- WSL2 与 systemd 在新版 Ubuntu 上的集成方式
- 在 WSL2 中跑 docker / k3s 的网络抓包配合
- `wsl --export` / `--import` 做镜像备份与回滚
