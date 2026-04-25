---
layout:     post
title:      Ubuntu 上准备多版本 GCC 的源
subtitle:   通过修改 apt 源拉取 gcc 7.3 / 7.5
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Ubuntu
    - GCC
    - apt
---

>原始笔记是几行散乱的 apt 源配置，这里把背景和步骤串起来，方便照着改。

## 背景

老项目偶尔需要指定 GCC 版本（比如 7.3、7.5）来复现编译/链接结果，但默认 Ubuntu 源里未必能直接装到。常见做法是临时换/补一份 apt 源再安装。

## 1. 编辑源列表

```bash
sudo vim /etc/apt/sources.list
```

## 2. 加入需要的源

下面两条是笔记里实际用过的镜像，按需选择：

```text
# gcc 7.3：bionic（18.04）系列
deb https://mirrors.cloud.tencent.com/ubuntu/ bionic main universe

# gcc 7.5：focal（20.04）系列
deb [arch=amd64] http://archive.ubuntu.com/ubuntu focal main universe
```

如果加的是非默认镜像，先导入对应的签名 key，否则 `apt update` 会报 NO_PUBKEY：

```bash
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 3B4FE6ACC0B21F32
```

## 3. 更新并安装

```bash
sudo apt update
sudo apt install gcc-7 g++-7
```

## 后续可补的方向

- `update-alternatives` 切换默认 gcc / g++ 版本的标准做法
- 用 `ppa:ubuntu-toolchain-r/test` 的官方 PPA 装新版 GCC
- 容器 / conda / spack 等隔离方案的对比
