---
layout:     post
title:      mbedTLS / curl 配置 TLS 的踩坑记录
subtitle:   CIPHER_LIST、Android NDK 版本与 LTO、裁剪后的 config 同步
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - mbedTLS
    - curl
    - Android
    - TLS
---

>原始笔记是几段没有标题的描述加两张截图，"坑"出现了两次，前后段落没有上下文衔接。这里按"配置疑似未生效 / NDK 版本坑 / 抓包结果 / 裁剪后同步 config"四块整理，原始代码与截图保持原样。AES IV 设置策略与 ECDH 握手时序图相关的补充已挪到 [mmtls 笔记]({{ site.baseurl }}/2026/04/25/mmtls/) 里，与 mmtls 的 HKDF / 签名讨论一起阅读更顺。

## 当前保留内容

### 1. CIPHER 配置疑似未生效

设置 `CURLOPT_SSLVERSION`（强制 TLS 1.2）和 `CURLOPT_SSL_CIPHER_LIST`（限定一组 ECDHE 套件）后，仍未达到预期，疑似未生效：

```
    CURLcode ret1;
    ret1 = curl_easy_setopt(curl_handle, CURLOPT_SSLVERSION,  CURL_SSLVERSION_TLSv1_2);
    if(ret1 != CURLE_OK)
    {
        MiLogE("request.url: CURLOPT_SSLVERSION failed ! ret = %d", ret1);
    }
   ret1 = curl_easy_setopt(curl_handle, CURLOPT_SSL_CIPHER_LIST,
                       // "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256" ":"
                       // "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384"
                       // "TLS-ECDHE-ECDSA-WITH-AES-256-GCM-SHA384"
                       "ECDHE-ECDSA-AES256-GCM-SHA384" ":"
                       "ECDHE-ECDSA-AES128-GCM-SHA256"
                        ":"
                       "ECDHE-ECDSA-AES256-SHA384"     ":"
                       "DHE-RSA-AES256-GCM-SHA384"     ":"
                       "ECDHE-RSA-AES256-GCM-SHA384"   ":"
                       "ECDHE-RSA-AES128-GCM-SHA256"   ":"
                       "ECDHE-ECDSA-AES128-SHA"        ":"
                       "ECDHE-ECDSA-AES128-SHA256"     ":"
                       "ECDHE-RSA-CHACHA20-POLY1305"   ":"
                       "ECDHE-RSA-AES256-SHA384"       ":"
                       "ECDHE-RSA-AES128-SHA256"       ":"
                       "ECDHE-ECDSA-CHACHA20-POLY1305" ":"
                       "ECDHE-ECDSA-AES256-SHA"        ":"
                       "ECDHE-RSA-AES128-SHA"          ":"
                       "DHE-RSA-AES128-GCM-SHA256"
                   );
   // curl_easy_setopt(curl_handle, CURLOPT_SSLVERSION,  CURL_SSLVERSION_TLSv1_1|CURL_SSLVERSION_TLSv1_2 |  CURL_SSLVERSION_TLSv1_3 | CURL_SSLVERSION_TLSv1 | CURL_SSLVERSION_SSLv2 | CURL_SSLVERSION_SSLv3);
   if(ret1 != CURLE_OK)
   {
       MiLogE("request.url:CURLOPT_SSL_CIPHER_LIST  ret = %d", ret1);
   }

    // curl_easy_setopt(curl_handle, CURLOPT_TLS13_CIPHERS,
    //                     // "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256" ":"
    //                     // "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384" 
    //                     "TLS-ECDHE-ECDSA-WITH-AES-256-GCM-SHA384"
    //                 );
```

### 2. Android NDK 版本坑

- Android NDK 版本：NDK 23 可用；NDK 25 / NDK 26 都遇到过问题（具体啥问题记录时已忘）。
- 实测换到低版本 NDK 后好使，但是没搞清高版本为什么不行。

![image](https://github.com/20083017/20083017.github.io/assets/8308226/59fe9871-a8e3-4fc4-b58e-4983a351c30b)

可能的方向：clang 版本不同 → LTO 支持不同。低版本 NDK 可能不支持 LTO；Android LTO 还有一个坑——cxx link 阶段需要同时增加 `-flto`，否则会报：

```
file format not recognized
```

### 3. 抓包结果

![image](https://github.com/20083017/20083017.github.io/assets/8308226/f753f8f2-27e7-4140-a3f9-0c24991baa4b)

### 4. 裁剪后的 mbedtls_config.h 同步

裁剪 mbedTLS 时，**记得同步修改 `mbedtls_config.h`**，否则编出来的库行为可能与预期不符。

## 后续可补的方向

- 把"CIPHER_LIST 疑似未生效"复盘到底是 curl 后端编译选项问题，还是 mbedTLS 端不支持这些套件
- 整理一张 NDK 版本 × clang 版本 × LTO 支持情况的对照表
- AES IV 策略与 ECDH 握手时序图见 mmtls 笔记，后续可补 0-RTT PSK / 0-RTT PSK-ECDHE 两种变体的时序图
