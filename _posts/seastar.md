

### 编译

#### github 配置

修改  /etc/hosts 添加dns 至 github.com

gcc11 好像不好使，   去掉了一些tests的demo 主要是rpc相关的，可以跑起来了。
修改configure.py 默认编译工具为 clang++， clang14,也不好使  


sudo ./install-dependencies.sh


```
sudo ./configure.py --mode=debug --cook=fmt
sudo ninja -C build/debug -j4

sudo ./configure.py --mode=debug --cook=fmt --compile-commands-json --enable-dpdk
```

### tcp 测试
```

默认 posix-stack
demo 需要使用root权限运行
./tcp_sctp_server_demo
 ./tcp_sctp_client_demo --server 127.0.0.1:10000 --conn=32 --test=rxrx  连接数太多, 卡住了？
./tcp_sctp_client_demo --server 127.0.0.1:10000 --conn=2 --test=rxrx

set args --network-stack=native --dpdk-pmd --tap-device=eth0 --host-ipv4-addr=127.0.0.1 --gw-ipv4-addr=127.0.0.1  --netmask-ipv4-addr=255.255.255.0
```

### dpdk 配置
```
EAL: Detected CPU lcores: 8
EAL: Detected NUMA nodes: 1
EAL: Detected static linkage of DPDK
[New Thread 0x7fffd60eb640 (LWP 211240)]
EAL: Multi-process socket /run/user/1000//dpdk/rte/mp_socket
[New Thread 0x7fffd58cd640 (LWP 211241)]
EAL: Selected IOVA mode 'VA'
EAL: FATAL: Cannot get hugepage information.
EAL: Cannot get hugepage information.
EAL: Error - exiting with code: 1
  Cause: Cannot init EAL
```

```
run_with_dpdk.sh
解决方法：
先进行dpdk的配置，配置方法请另行搜索，然后进行大页的配置以及挂载。
大页配置：
查看虚拟机大叶内存
cat /proc/meminfo | grep Huge
设置内存大小
su
echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages

大页挂载：
mkdir /mnt/huge
mount -t hugetlbfs nodev /mnt/huge

mkdir的时候会提示文件存在，继续就行了。
```

### 编译安装libvirt 
```
EAL: get_seg_fd(): open '/dev/hugepages/rtemap_0' failed: Permission denied
EAL: Couldn't get fd on hugepage file
EAL: error allocating rte services array
EAL: FATAL: rte_service_init() failed
EAL: rte_service_init() failed
EAL: Error - exiting with code: 1
  Cause: Cannot init EAL
```

https://github.com/microsoft/WSL2-Linux-Kernel/releases

make config   
允许支持 virtualization，编译之后配置wslconfig，使用外部内核

```
[wsl2]
#networkingMode=bridged
#vmSwitch=wsl

nestedVirtualization=true
kernel=C:\\Users\\mi\\bzImage
#pageReporting=true
kernelCommandLine=intel_iommu=on iommu=pt kvm.ignore_msrs=1 kvm-intel.nested=1 kvm-intel.ept=1 kvm-intel.emulate_invalid_guest_state=0 kvm-intel.enable_shadow_vmcs=1 kvm-intel.enable_apicv=1
```

#### 注意
You could clone https://github.com/microsoft/WSL2-Linux-Kernel.git and checkout linux-msft-wsl-5.15.79.1. Export the headers and build your module.   

### 网卡配置

```
网卡配置
使用到usertools/dpdk-devbind.py

在使用hyper-v之后就不能再使用虚拟机的Intel VT-x，因此vfio-pci不能使用，如果可以的话官方建议使用vfio-pci保证安全性，见6. Linux Drivers — Data Plane Development Kit 22.07.0 documentation

下面介绍使用igb_uio驱动的方式，DPDK20.x版本后不再提供igb_uio的源码，可以到此下载

dpdk-kmods - Kernel modules or add-ons 

解压后执行make编译即可，得到模块文件igb_uio.ko，执行

export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/home/liuquan6/WSL2-Linux-Kernel-linux-msft-wsl-5.15.153.1    

sudo modprobe uio
sudo insmod igb_uio.ko
安装两个模块，此时执行
```




