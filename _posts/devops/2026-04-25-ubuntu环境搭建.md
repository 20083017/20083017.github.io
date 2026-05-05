---
layout:     post
title:      Ubuntu 环境搭建笔记
subtitle:   apt 换源（清华 / 163 / 阿里云 / 中科大）+ pip / 网络 / 工具杂记
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Ubuntu
    - Linux
    - 环境搭建
---

>原始笔记是几段标题层级混乱的环境搭建片段，"中科大源"的内容实际上还是阿里云的（直接复用了），netplan / curl / root 几小节零散贴在末尾。这里只把章节按"换源 / Python / 系统配置 / 网络 / 工具"四块归拢，命令片段原样保留，不替换其中可疑的源地址，避免误改。

## 当前保留内容

### 1. 更换 apt 源（jammy / 22.04）

#### 1.1 清华源

```
sudo bash -c "cat << EOF > /etc/apt/sources.list && apt update 
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy main restricted universe multiverse
# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy main restricted universe multiverse
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse
# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse
# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse
deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-security main restricted universe multiverse
# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-security main restricted universe multiverse
EOF"
```

#### 1.2 163 源

```
sudo bash -c "cat << EOF > /etc/apt/sources.list && apt update 
deb http://mirrors.163.com/ubuntu/ jammy main restricted universe multiverse
deb http://mirrors.163.com/ubuntu/ jammy-security main restricted universe multiverse
deb http://mirrors.163.com/ubuntu/ jammy-updates main restricted universe multiverse
deb http://mirrors.163.com/ubuntu/ jammy-proposed main restricted universe multiverse
deb http://mirrors.163.com/ubuntu/ jammy-backports main restricted universe multiverse
deb-src http://mirrors.163.com/ubuntu/ jammy main restricted universe multiverse
deb-src http://mirrors.163.com/ubuntu/ jammy-security main restricted universe multiverse
deb-src http://mirrors.163.com/ubuntu/ jammy-updates main restricted universe multiverse
deb-src http://mirrors.163.com/ubuntu/ jammy-proposed main restricted universe multiverse
deb-src http://mirrors.163.com/ubuntu/ jammy-backports main restricted universe multiverse
EOF"
```

#### 1.3 阿里云

```
sudo bash -c "cat << EOF > /etc/apt/sources.list && apt update 
deb http://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ jammy-proposed main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy-proposed main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse
EOF"
```

#### 1.4 中科大

> 注：原始笔记此处的内容与"阿里云"一致，疑似复制粘贴时漏改。这里如实保留，待校对后再用真正的中科大源（`mirrors.ustc.edu.cn`）替换。

```
sudo bash -c "cat << EOF > /etc/apt/sources.list && apt update 
deb http://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ jammy-proposed main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy-proposed main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse
EOF"
```

换源完成之后，生效命令：`sudo apt update`。

### 2. Python / pip

#### 2.1 pip 升级与查看可用版本

```
sudo pip install --upgrade pip

查看安装版本
pip install numpy==
```

#### 2.2 Python openssl 源码编译？python3-openssl？

（待补充。）

### 3. 系统配置

#### 3.1 分区、扩容

参考：<https://blog.csdn.net/Xin_101/article/details/125929428>

#### 3.2 关闭锁屏

（待补充。）

#### 3.3 Windows 设置输入法（关闭微软自带，更换为搜狗）

设置 → 时间和语言 → 键盘 → 添加语言并删除原有的微软输入法。

#### 3.4 Windows 设置程序的开机启动（类似 macOS）

（待补充。）

### 4. 网络（netplan）

```
network:
  version: 2
  renderer: networkd
  ethernets:
    enp3s0:
      addresses:
        - 10.10.10.2/24
      gateway4: 10.10.10.1
      nameservers:
          search: [mydomain, otherdomain]
          addresses: [10.10.10.1, 1.1.1.1]
```

#### 其他 netplan 配置

如 1 个网卡多个 IP 等场景，待补充。

### 5. 常用工具与账号

#### 5.1 curl / net-tools / vim

（待补充安装清单与最小配置。）

#### 5.2 root 账号设置密码

```
sudo passwd root
```

#### 5.3 安装 GitKraken

参考：<https://github.com/wanZzz6/Modules-Learn/blob/master/%E6%8A%80%E6%9C%AF/Gitkraken%20%E6%9C%80%E6%96%B0%E7%89%88v9%E3%80%81v10%E7%A0%B4%E8%A7%A3%E6%95%99%E7%A8%8B.md>

## 后续可补的方向

- 把"中科大源"修正为真正的 `mirrors.ustc.edu.cn`，并补一份脚本：自动 ping 三家源择最快的写入 `sources.list`。
- 补全 Python openssl 源码编译的步骤（含 `--with-openssl=` 配置）。
- netplan 多 IP / 多网卡 / VLAN 的几个常见 yaml 模板各给一份。
