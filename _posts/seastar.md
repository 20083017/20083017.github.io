---
layout:     post
title:      Seastar 编译与 DPDK 记录整理
subtitle:   编译依赖、WSL 限制与 DPDK 运行要点
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Seastar
    - DPDK
    - WSL
---

>把原始记录中的编译依赖、DPDK 配置和 WSL 限制整理成一条更容易复用的排查路径。

## 编译阶段先记住的几个问题

原始笔记里最核心的背景是：

- 某些 gcc / clang 版本不太稳定
- 一些 demo / test 需要裁掉才能先把主线编过
- `fmt` 和 `gnutls` 版本会直接影响构建是否通过

## 依赖安装

```bash
sudo ./install-dependencies.sh
```

如果系统库版本不够，原始记录里还单独补了一套升级 GnuTLS 的流程。

## 升级 GnuTLS 的一套命令

```bash
sudo apt install build-essential pkg-config libgmp-dev tar wget libunistring-dev

cd /tmp
wget https://ftp.gnu.org/gnu/nettle/nettle-3.9.1.tar.gz
tar -xzf nettle-3.9.1.tar.gz
cd nettle-3.9.1
./configure --prefix=/usr/local --disable-openssl
make -j$(nproc)
sudo make install

cd /tmp
wget https://www.gnupg.org/ftp/gcrypt/gnutls/v3.8/gnutls-3.8.6.tar.xz
tar -xf gnutls-3.8.6.tar.xz
cd gnutls-3.8.6

PKG_CONFIG_PATH="/usr/local/lib/pkgconfig" ./configure \
  --prefix=/usr/local \
  --with-included-libtasn1 \
  --without-p11-kit \
  --disable-doc

make -j$(nproc)
sudo make install
sudo ldconfig
```

## 常用构建命令

```bash
sudo ./configure.py --mode=debug --cook=fmt
sudo ninja -C build/debug -j4
```

如果还要导出编译数据库并打开 DPDK：

```bash
sudo ./configure.py --mode=debug --cook=fmt --compile-commands-json --enable-dpdk
```

## TCP demo 测试

```bash
./tcp_sctp_server_demo
./tcp_sctp_client_demo --server 127.0.0.1:10000 --conn=2 --test=rxrx
```

原始笔记里的经验是：demo 往往需要 root 权限，而且连接数一上去就容易暴露网络栈或环境限制。

## DPDK 启动失败时先看什么

原始日志里最典型的报错是：

```text
EAL: FATAL: Cannot get hugepage information.
EAL: Error - exiting with code: 1
Cause: Cannot init EAL
```

这通常先指向两类问题：

1. hugepage 没配好
2. 当前环境（尤其是虚拟机 / WSL）并不适合直接按物理机场景跑 DPDK

## 一个精简的 DPDK 配置文件

```ini
[binaries]
c = 'gcc'
cpp = 'g++'
pkgconfig = 'pkg-config'

[host_machine]
system = 'linux'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'

[options]
enable_drivers = 'net/virtio'
enable_docs = false
enable_kmods = false
enable_tests = false
```

## 一个常见的 CMake 配置思路

```bash
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DSEASTAR_CXX_STANDARD=20 \
  -DSeastar_ENABLE_DPDK=ON \
  -DSeastar_DPDK_CONFIG=../dpdk-custom.conf \
  -DSeastar_ENABLE_APPS=OFF \
  -DSeastar_ENABLE_DEMOS=OFF \
  -DSeastar_ENABLE_TESTS=OFF \
  -DSeastar_ENABLE_SHARED=OFF \
  -DSeastar_ENABLE_HWLOC=OFF \
  -DSeastar_ENABLE_ALLOC_FAILURE_INJECTION=OFF \
  -DSeastar_ENABLE_EXCEPTIONS=ON \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DCMAKE_PREFIX_PATH="/usr/local"
```

## hugepage 基本准备

```bash
cat /proc/meminfo | grep Huge

echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
mkdir /mnt/huge
mount -t hugetlbfs nodev /mnt/huge
```

## WSL 下的限制

原始记录里还提到两类问题：

- nested virtualization 相关配置
- 网卡绑定和 `vfio-pci` 在虚拟化环境下常常不可用

所以更实际的经验是：

- 在 WSL 里优先把它当作“验证构建和基础功能”的环境
- 真正涉及 DPDK、hugepage、网卡绑定时，优先在更接近物理机的环境验证
- 如果只是要通路打通，可先考虑 `pcap` 这类更容易启动的后端

## 按环境分工：本地 VM vs 云上裸金属 / SR-IOV

不同环境能验证的事情不一样，混在一起跑容易把"环境限制"当成"代码 bug"。一个比较实用的分工是：

### 本地 VirtualBox / WSL2：编译、单测、pcap 或 net/virtio demo

定位是"验证业务逻辑能不能编出来、跑起来、行为对不对"，不追性能。

- 编译 Seastar、跑 `ninja test` 单元测试
- 业务代码用 posix 网络栈跑 demo，调试逻辑首选
- 需要走 DPDK 路径时：
  - VirtualBox 把网卡设成 paravirtualized，使用 `net/virtio` PMD
  - WSL2 没有可绑定的真实网卡，只能用 `net/pcap` 后端
- DPDK 的 meson 配置里只留 `net/virtio,net/pcap`，不开 `net/ixgbe`、`net/i40e`、`net/mlx5` 这些物理网卡 PMD

这一档**不要做**的事：

- 不要绑 `vfio-pci`：VirtualBox 没 IOMMU 透传，WSL2 内核没有 vfio
- 不要看 pps / 延迟数字：virtio-net 的中断和拷贝路径会主导，没参考价值
- 看到 `EAL: Cannot get hugepage information` 之类先查环境，别当业务 bug

中间还有一档可选：本地 KVM + VT-d passthrough 把闲置网卡直通给 Guest，能跑通完整 `vfio-pci` 流程，是本地最接近物理机的调试环境。

### 云上裸金属 / SR-IOV 实例：性能基准、最终验收

定位是"复现真实物理机的 DPDK 路径，跑吞吐 / pps / 尾延迟，发布前验收"。

- 选实例先确认 DPDK 支持矩阵（云厂文档一般直接给 PMD 名字）：
  - AWS 裸金属 `*.metal` 或 ENA 增强网络 → `net/ena`
  - Azure Accelerated Networking → `net/netvsc` + `net/failsafe`（双 PMD，热迁移回落到 synthetic）
  - GCP gVNIC → `net/gve`（DPDK 22.11+）
  - 阿里神龙裸金属 / g7ne、腾讯黑石 → 按 VF 类型选对应 PMD
- 启动参数加 hugepage 和 IOMMU（裸金属需要 `intel_iommu=on iommu=pt`，普通 SR-IOV VM 通常不用）
- 裸金属需要 `dpdk-devbind.py --bind=vfio-pci`，**留至少一张管理网卡给内核**，别把自己踢下线
- SR-IOV VM 通常不绑 vfio-pci，PMD 直接接管，按云厂文档来
- DPDK meson 配置打开实际用到的物理 PMD（`net/ena`、`net/mlx5` 等）

跑基准时容易踩的坑：

- AWS 等平台要关掉网卡的 source/dest check，否则 DPDK 发的非自身 MAC 流量会被云侧丢掉
- `--smp` 和网卡 NUMA 节点对齐（看 `/sys/class/net/ethX/device/numa_node`）
- CPU 用 `isolcpus` / `nohz_full` 隔离，避免 reactor stall
- 性能不稳先排查云侧配额限速（如 AWS CloudWatch ENA 的 `bw_*_allowance_exceeded`），不一定是代码问题

验收清单：DPDK 启动日志识别到正确网卡、hugepage 实际占用 = 配置量、持续 1 小时压测无丢包无内存泄漏、云侧监控未触顶。

## 整理后的排查顺序

1. 先解决依赖库版本问题
2. 再确认 `configure.py` 和编译器版本是否匹配
3. 如果启用 DPDK，先看 hugepage 和驱动条件
4. 在 WSL / 虚拟机里，不要默认把 DPDK 失败当成业务代码问题
