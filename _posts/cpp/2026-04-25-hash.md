---
layout:     post
title:      常见哈希算法速览
subtitle:   加密哈希与查找型哈希的分类整理
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Hash
    - Algorithm
    - Cryptography
---

>原始笔记是一段连贯文字，把加密哈希和查找哈希的常见算法都铺开介绍。这里只做分类与排版，把原文的描述切成可以扫读的小节。

## 一、加密哈希算法

主要应用在三个方向：

1. 文件校验
2. 数字签名
3. 鉴权协议

### 1. MD5

MD5（Message-Digest Algorithm 5），用于确保信息传输完整一致，是计算机广泛使用的杂凑算法之一，主流编程语言普遍已有 MD5 实现。它将不定长度信息运算为另一固定长度值（128-bit）；基本流程是：求余、取余、调整长度、与链接变量循环运算得到结果。MD5 的前身有 MD2、MD3 和 MD4。

MD5 一度被广泛应用于安全领域。但在 2004 年王小云教授公布了 MD5、MD4、HAVAL-128、RIPEMD-128 等 Hash 函数的碰撞，使用其技术在数小时内就可以找到 MD5 碰撞，本算法不再适合当前的安全环境。目前 MD5 主要用于错误检查，例如一些 BitTorrent 下载会通过计算 MD5 校验下载到的碎片完整性。

### 2. SHA-1

SHA-1 曾经在许多安全协议中广为使用，包括 TLS、SSL、PGP、SSH、S/MIME 和 IPsec，曾被视为 MD5 的后继者。它是如今很常见的加密哈希算法，HTTPS 传输和软件签名认证都很喜欢它。但它毕竟是 1995 年由美国国安局（NSA）提出的老技术，已逐渐跟不上时代，被破解的速度越来越快。

微软在 2013 年的 Windows 8 系统里就改用了 SHA-2，Google、Mozilla 则宣布 2017 年 1 月 1 日起放弃 SHA-1。在普通民用场合（如校验下载软件），SHA-1 仍然可以继续用，就像早已被淘汰的 MD5 一样。

### 3. SHA-2

SHA-224、SHA-256、SHA-384 和 SHA-512 并称为 SHA-2。它们没有像 SHA-1 那样接受公众密码社区的详细检验，因此其密码安全性还没有被广泛信任。虽然至今尚未出现对 SHA-2 的有效攻击，但其算法跟 SHA-1 仍然相似，因此有人开始发展其他替代的哈希算法。

### 4. SHA-3

SHA-3 之前名为 Keccak 算法，是一种加密杂凑算法。由于 MD5 出现成功的破解，以及对 SHA-0 和 SHA-1 出现理论上破解的方法，NIST 认为需要一个与之前算法不同、可替换的加密杂凑算法，也就是现在的 SHA-3。

### 5. RIPEMD-160

RIPEMD-160 是一个 160 位加密哈希函数，旨在替代 128 位哈希函数 MD4、MD5 和 RIPEMD。它没有输入大小限制；处理速度比 SHA-2 慢，安全性也不如 SHA-256 和 SHA-512。

## 二、查找型哈希算法

### 1. lookup3

Bob Jenkins 在 1997 年发表了《A hash function for hash table lookup》，文章自发表以后在网上有更多扩展内容。文中广泛收录了很多已有的哈希函数，包括他自己的 “lookup2”。2006 年，Bob 发布了 lookup3。它实现了较好的散列均匀分布，但相对耗时；具有两个特性：(1) 抗篡改性，输入参数任何一位的更改都会带来一半以上位的变化；(2) 可逆性，但逆运算非常耗时。

### 2. Murmur3

murmurhash 是 Austin Appleby 于 2008 年创立的一种非加密哈希算法，适用于基于哈希进行查找的场景。最新版本是 MurmurHash3，支持 32 位、64 位及 128 位值的产生。MurMur 经常用在分布式环境中（如 Hadoop），特点是高效快速，缺点是分布不是很均匀。

### 3. FNV-1a

FNV 又称 Fowler/Noll/Vo，来自 3 位算法设计者的名字（Glenn Fowler、Landon Curt Noll 和 Phong Vo）。FNV 有 3 种：FNV-0（已过时）、FNV-1、FNV-1a，后两者差别极小。FNV-1a 生成的哈希值是无符号整型；bit 数是 2 的 n 次方（32、64、128、256、512、1024），通常 32-bit 就能满足大多数应用。

### 4. CityHash

2011 年 Google 发布 CityHash（由 Geoff Pike 和 Jyrki Alakuijala 编写），其性能好于 MurmurHash。后来 CityHash 被发现容易受到针对算法漏洞的攻击，该漏洞允许多个哈希冲突发生。

### 5. SpookyHash

又是 Bob Jenkins 这位哈希牛人的作品，2011 年发布的新哈希函数性能优于 MurmurHash，但只给出 128 位输出；后续发布的 SpookyHash V2 提供了 64 位输出。

### 6. FarmHash

FarmHash 由 Google 发布，是 CityHash 的后继，继承了许多技巧和技术，并声称从多个方面对 CityHash 做了改进。

### 7. xxhash

xxhash 由 Yann Collet 发表，官网：<http://cyan4973.github.io/xxHash/>。性能很好，被很多开源项目使用，是 Bloom Filter 的首选之一。

## 后续可补的方向

- 实测各算法在不同 key 长度下的吞吐对比
- 使用场景速查表（密码存储、文件校验、HashMap、Bloom Filter 等分别选哪个）
- 抗碰撞性 / 抗长度扩展攻击的简要说明
