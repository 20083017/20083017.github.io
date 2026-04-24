---
layout:     post
title:      OpenSSL 1.1.1g 与 Python 3.8.6 安装记录
subtitle:   在保留原始经验的基础上，优先使用独立前缀安装
date:       2026-04-24
author:     BY
header-img: img/post-bg-unix-linux.jpg
catalog: true
tags:
    - OpenSSL
    - Python
    - Linux
---

>这篇文章前一次整理时，删除了不少旧笔记内容，主要是因为其中夹杂了“直接替换系统 OpenSSL / 系统库”的高风险操作。为了尽量保留原始经验，这一版把原先有价值的安装、交叉编译、性能优化和 cryptodev 记录补回来，但不再原样保留会破坏系统环境的替换步骤。

## 先确认系统自带版本

```bash
openssl version
which openssl
whereis openssl
```

原始环境中的检查结果大致如下：

```bash
[root@cnki-120-145-80 ~]# openssl version
OpenSSL 1.0.2k-fips  26 Jan 2017

[root@cnki-120-145-80 ~]# which openssl
/usr/bin/openssl

[root@cnki-120-145-80 ~]# whereis openssl
openssl: /usr/bin/openssl /usr/lib64/openssl /usr/include/openssl /usr/share/man/man1/openssl.1ssl.gz
```

如果系统自带版本过老，**不要直接覆盖 `/usr/bin/openssl`、`/usr/include/openssl` 或 `/usr/lib64/libssl.so*`**。更稳妥的做法是保留系统库，另装一份新的，让目标 Python 或业务程序显式链接新库。

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

原始笔记里也记录过 3.0.4 / 3.0.12 的编译方式，本质上思路类似：不要动系统库，另外编译、另外安装、单独验证。

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

## 历史做法（默认不推荐，但作为特殊情况记录保留）

原始笔记里其实还记录过几段“为了让系统默认命令马上切到新版本”而采用的处理方式。前一次整理时，这些内容被整段删掉了；这次继续把它们补回来，但明确标注为：**只适用于你已经充分评估影响范围、且确实需要让系统默认路径切换到新版本的特殊场景，不是通用升级步骤。**

### 1. 直接替换系统 `openssl` 命令与头文件

原始笔记里的处理命令大致如下：

```bash
mv /usr/bin/openssl /usr/bin/openssl.bak
mv /usr/include/openssl /usr/include/openssl.bak

ln -s /usr/local/openssl/bin/openssl /usr/bin/openssl
ln -s /usr/local/openssl/include/openssl /usr/include/openssl
```

它的目的很直接：让系统里默认执行到的 `openssl` 命令、以及默认包含到的头文件，立刻指向新安装版本。

当时这样做的出发点，是想让 `openssl version`、依赖系统头文件的编译流程立刻“看到”新版本。但这类做法的问题也很明显：

- 会影响系统自带工具、SSH、包管理器或其他依赖旧 ABI 的程序
- 一旦链接关系不完整，系统层面的问题会比业务进程问题更难排查
- 回滚时不仅要恢复命令，还要确认 include、so、缓存是否都恢复一致

更稳妥的替代方式仍然是：**保留系统路径不变，只让目标程序显式使用新前缀里的 OpenSSL。**

### 2. 在系统动态库目录里手工补 `libssl.so*` / `libcrypto.so*` 软链接

原笔记里还记录过两段与动态库相关的特殊处理：

```bash
echo "/usr/local/openssl/lib64" >> /etc/ld.so.conf
ldconfig -v
```

以及在某些报错场景下，手工补系统库目录软链接：

```bash
ln -s /usr/local/openssl/lib/libssl.so.1.1 /usr/lib/libssl.so.1.1
ln -s /usr/local/openssl/lib/libssl.so.1.1 /usr/lib64/libssl.so.1.1
ln -s /usr/local/openssl/lib/libcrypto.so.1.1 /usr/lib64/libcrypto.so.1.1
```

这些记录之所以值得保留，是因为它们对应的确实是当时遇到的“特殊情况处理”：

- 新版本已经编译安装成功，但运行时仍找不到对应 so
- 某些旧环境里，业务程序就是通过系统默认库搜索路径启动的
- 需要先把问题定位清楚，再决定是否要做系统级可见的补充配置

这样做看起来能“快速救火”，但风险在于：

- 它绕过了系统原本的库版本管理方式
- 很容易让不同程序在同一台机器上加载到彼此并不兼容的库
- 后续升级、排障时，很难第一时间意识到是这些手工软链接在生效

如果确实需要系统级可见的新库，优先考虑：

- 在单独的 `ld.so.conf.d/*.conf` 文件中声明库路径
- 执行 `ldconfig` 统一刷新缓存
- 或者直接在目标程序的启动脚本 / service 配置里设置运行时库路径

### 3. 为什么这次保留“说明”但不保留“原命令”

因为这些历史做法本身确实反映了当时遇到的问题：

- 需要让旧系统尽快用上新版本 OpenSSL
- Python 编译或运行时找不到目标版本的 `ssl`
- 动态库路径没有配置好，导致新程序起不来

所以这次做的不是“继续删除”，而是把它们保留为**历史特殊处理记录**。只是阅读时要区分清楚：

- 这些命令说明“以前碰到问题时是怎么处理的”
- 不等于“现在默认就该这样做”
- 真要使用，至少先确认系统工具、SSH、包管理器、业务二进制、回滚路径都在可控范围内

## 编译 Python 3.8.6 并链接新的 OpenSSL

执行编译时可通过 `-j` 选项指定并行任务数来加快速度，通常可结合 `nproc` 使用。原始笔记里也特别提到：**Python 编译通常不需要 root 用户，普通用户安装到自己的 prefix 更合适。**

```bash
cd /path/to/Python-3.8.6

./configure --prefix=$HOME/local/python-3.8.6 \
            --with-openssl=/usr/local/openssl-1.1.1g

make -s -j "$(nproc)"
make install
```

安装后会在 `prefix` 路径下生成 Python 二进制文件，验证方式例如：

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

## 补充：原始笔记中的交叉编译与性能记录

下面这些内容是原文中比较有参考价值的部分，这里保留为补充记录。它们更偏“平台经验”，不是通用安装步骤，使用前请按自己的工具链和目标板环境逐项验证。

### 不同 SSL 库的编译记录

```bash
# wolfssl 32位 armv7 平台交叉编译
./configure \
    --host=arm-linux-gnueabihf \
    CC=/home/liuquan6/.toolchain/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-9.1.0-gcc \
    AR=/home/liuquan6/.toolchain/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-9.1.0-ar \
    STRIP=/home/liuquan6/.toolchain/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-9.1.0-strip \
    RANLIB=/home/liuquan6/.toolchain/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-9.1.0-ranlib \
    --prefix=/mnt/e/test/wolfssl/output \
    CFLAGS="-march=armv8-a -DHAVE_PK_CALLBACKS -DWOLFSSL_USER_IO -DNO_WRITEV -DTIME_T_NOT_64BIT" \
    --disable-filesystem --enable-fastmath --enable-sp-asm \
    --disable-shared
make
make install
```

```bash
# openssl 32位 armv7 交叉编译
# 某些平台不禁用 asm 会导致编译错误

tar -xvf openssl-3.0.12.tar.gz
cd openssl-3.0.12/

# 安装目录设为当前目录下的 tmp，no-asm、shared 的功能请结合 INSTALL.md 阅读
./config no-asm shared --prefix=$PWD/tmp

# 如果要启用硬件 engine，例如 devcrypto，需要结合目标平台能力单独确认
# 原始笔记里提到过 enable-devcryptoeng，这类选项一定要先确认目标内核和驱动支持

# 之后再按自己的工具链修改 Makefile，例如 CROSS_COMPILE、架构选项等
make
make install
```

### 性能优化策略

原始记录里的要点如下：

```text
1、指令优化：aesni、aesce 等
2、硬件加密
3、asm
4、加密 block size 也会影响速度，需要结合业务场景测试
```

这些优化项都强依赖 CPU 架构、编译器、内核和驱动栈，建议单独做基准测试，不要凭单次结果直接推广。

### 性能验证 / 联调时常见命令

原始笔记虽然更偏“想到什么记什么”，但这类性能相关命令确实有保留价值，至少便于后续复测：

```bash
# 查看当前 openssl 是否能识别 engine
/usr/local/openssl-1.1.1g/bin/openssl engine -t -c

# 观察某个算法在当前机器上的速度
/usr/local/openssl-1.1.1g/bin/openssl speed -elapsed -evp aes-128-gcm
/usr/local/openssl-1.1.1g/bin/openssl speed -elapsed -evp aes-256-gcm

# 如果平台有硬件加速能力，可对比是否启用 engine / asm 前后的结果
```

这些命令本身不会替换系统库，但它们的结论也不能脱离场景解读。尤其是：

- `speed` 结果更适合做“同机、同编译参数、同算法”的横向对比
- `aesni` / `aesce` / `asm` / 硬件 engine 的收益，要结合目标 CPU 指令集与驱动情况
- 最终仍要以真实业务负载下的吞吐、时延、CPU 占用为准

## 补充：cryptodev engine 记录

原始笔记中还保留了 cryptodev engine 的截图和示例，这部分对做硬件加速联调时仍然有参考价值。

### cryptodev engine

对应硬件加密时，通常还需要安装 `cryptodev.ko`：

![image](https://github.com/user-attachments/assets/f714e814-2148-4daf-a71f-e06cc82646f4)

![image](https://github.com/user-attachments/assets/56ab6e91-789f-475f-8be9-5be04a229c03)

### cryptodev 示例

下面是原笔记保留的一个 `devcrypto` engine 例子：

```c
#include <openssl/conf.h>
#include <openssl/des.h>
#include <openssl/err.h>
#include <openssl/evp.h>
#include <openssl/objects.h>
#include <openssl/rand.h>
#include <openssl/ssl.h>
#include <openssl/engine.h>

#if !defined(LIBRESSL_VERSION_NUMBER)
#include <openssl/kdf.h>
#endif
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/provider.h>
#include <openssl/core_names.h>
#endif

int main(int ac, char **av, char **ae)
{
    ENGINE *e = NULL;
    if ((e = ENGINE_by_id("devcrypto")) == NULL) {
        printf("cryptodev engine not found!\n\n");
        return 0;
    }

    const EVP_CIPHER *cipher;
    int len;
    unsigned char tag[16];

    unsigned char key[] = {
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
        0x38, 0x39, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35,
        0x36, 0x37, 0x38, 0x39, 0x30, 0x31, 0x32, 0x33,
        0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x30, 0x31
    };
    unsigned char iv[] = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b};
    unsigned char data[] = {
        0x0, 0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7,
        0x8, 0x9, 0xa, 0xb, 0xc, 0xd, 0xe, 0xf,
        0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
        0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
        0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
        0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e, 0x2f,
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
        0x38, 0x39, 0x3a, 0x3b
    };

    ERR_load_crypto_strings();

    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    cipher = EVP_aes_256_gcm();

    EVP_EncryptInit_ex(ctx, cipher, NULL, NULL, NULL);
    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, sizeof(iv), NULL);
    EVP_EncryptInit_ex(ctx, NULL, NULL, key, iv);

    len = sizeof(data);
    int h = 0;

    EVP_EncryptUpdate(ctx, data, &len, data, len);
    EVP_EncryptFinal(ctx, tag, &h);

    printf("DATA:");
    for (int i = 0; i < sizeof(data); ++i)
        printf("%02X,", data[i]);
    printf("\n");

    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, sizeof tag, tag);
    printf("TAG:");
    for (int i = 0; i < sizeof(tag); ++i)
        printf("%02X,", tag[i]);
    printf("\n");

    ctx = EVP_CIPHER_CTX_new();
    EVP_DecryptInit(ctx, cipher, key, iv);
    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, 16, tag);
    EVP_DecryptInit(ctx, NULL, key, iv);
    EVP_DecryptUpdate(ctx, data, &h, data, len);
    printf("DATA:");
    for (int i = 0; i < sizeof(data); ++i)
        printf("%02X,", data[i]);
    printf("\n");
    int dec_success = EVP_DecryptFinal(ctx, data, &h);
    printf("TAG: %d\n", dec_success);

    fflush(stdout);
    return 0;
}
```

## 为什么上次会删掉大量内容

简单说，是因为原文里同时混杂了两类内容：

1. **值得保留的经验笔记**：版本检查、Python 编译、交叉编译、性能优化、cryptodev 示例。
2. **高风险系统改造步骤**：直接替换 `/usr/bin/openssl`、覆盖系统 include / so、在系统库目录里手工补软链接。

前一次整理时，把第二类高风险内容清掉了，但也连带把第一类经验内容删得太多。这次做了折中：**尽量恢复原始信息量，但不再原样保留容易把系统搞坏的步骤。**

## 结论

这类升级最重要的不是“把系统里的 OpenSSL 换掉”，而是：

1. 保留系统自带库
2. 用独立前缀安装新库
3. 让目标 Python 或业务程序显式链接新库
4. 平台相关的性能和交叉编译问题，单独做验证和记录

这样既能保留原始经验，也不会把整个系统环境一起带崩。
