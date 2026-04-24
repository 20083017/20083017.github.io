---
layout:     post
title:      OpenSSL 1.1.1g 与 Python 3.8.6 安装记录
subtitle:   用独立前缀安装，避免覆盖系统 OpenSSL
date:       2026-04-24
author:     BY
header-img: img/post-bg-unix-linux.jpg
catalog: true
tags:
    - OpenSSL
    - Python
    - Linux
---

>不要在老系统上直接替换 `/usr/bin/openssl`、`/usr/include/openssl` 或 `/usr/lib64/libssl.so*`。这类改动会影响系统自带工具，轻则命令报错，重则 SSH、包管理器或业务进程直接起不来。更稳妥的做法是把新版本 OpenSSL 安装到独立目录，再让目标 Python 显式链接它。

## 先确认系统自带版本

```bash
openssl version
which openssl
whereis openssl
```

如果系统自带版本过老，不要原地覆盖，保留系统库，另装一份新的。

## 安装 OpenSSL 1.1.1g 到独立前缀

下面示例把 OpenSSL 安装到 `/usr/local/openssl-1.1.1g`：

```bash
cd /opt
wget https://www.openssl.org/source/old/1.1.1/openssl-1.1.1g.tar.gz
tar -xvf openssl-1.1.1g.tar.gz
cd openssl-1.1.1g

./config --prefix=/usr/local/openssl-1.1.1g \
         --openssldir=/usr/local/openssl-1.1.1g \
         shared

make -j"$(nproc)"
make test
sudo make install
```

验证时优先直接调用新路径，而不是替换系统命令：

```bash
/usr/local/openssl-1.1.1g/bin/openssl version
```

如果只是当前 shell 里临时使用新版本，可以这样：

```bash
export PATH=/usr/local/openssl-1.1.1g/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/openssl-1.1.1g/lib:$LD_LIBRARY_PATH
```

如需长期使用，优先在单独的启动脚本、systemd unit 或用户 profile 里设置；不要把兼容性问题简单粗暴地变成 `/usr/lib64` 下的手工软链接。

## 编译 Python 3.8.6 并链接新的 OpenSSL

Python 不需要用 root 安装到系统目录，使用普通用户装到自己的前缀通常更安全：

```bash
cd /path/to/Python-3.8.6

./configure --prefix=$HOME/local/python-3.8.6 \
            --with-openssl=/usr/local/openssl-1.1.1g

make -j"$(nproc)"
make install
```

安装后验证：

```bash
$HOME/local/python-3.8.6/bin/python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"
```

## 常见问题

### 1. 运行时找不到 `libssl.so`

优先检查：

- `LD_LIBRARY_PATH` 是否包含 OpenSSL 安装目录下的 `lib`
- 目标二进制的 `rpath` / `runpath` 是否正确
- 是否误把程序链接到了系统旧库

如果确实需要系统级动态库配置，也应通过单独的 `ld.so.conf.d/*.conf` 文件管理，再执行 `ldconfig`；不要随手把 so 文件软链接到 `/usr/lib64` 覆盖系统期望的版本。

### 2. 某些平台交叉编译报 asm 相关错误

这通常和工具链、目标架构及 OpenSSL 版本有关。遇到这类问题时，优先阅读对应版本的 `INSTALL.md`，按目标平台单独验证 `no-asm`、交叉编译前缀和 engine 选项，不要把其他平台的 Makefile 修改片段直接照搬到当前环境。

## 结论

这类升级最重要的不是“把系统里的 OpenSSL 换掉”，而是：

1. 保留系统自带库
2. 用独立前缀安装新库
3. 让目标 Python 或业务程序显式链接新库

这样即使编译失败或兼容性不符，也不会把整个系统环境一起带崩。


