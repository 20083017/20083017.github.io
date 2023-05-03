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
