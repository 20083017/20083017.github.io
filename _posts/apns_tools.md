---
layout:     post
title:      APNs 调试与鉴权记录
subtitle:   token-based 与 certificate-based 两种调试方式的最小备忘
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios10.jpg
catalog: true
tags:
    - iOS
    - APNs
    - JWT
    - curl
---

>把原始笔记里关于 APNs 的概念、脚本和 jwt-cpp 试验代码重新收拢成一篇可回看的调试记录。

## 1. 先记住 APNs 有两套常见鉴权方式

APNs 全称是 Apple Push Notification service。

这篇主要整理两类调试方式：

1. **token-based**
   - 使用 `.p8` 私钥
   - 需要自己生成 JWT
   - 适合长期使用，密钥标识符可以持续复用
2. **certificate-based**
   - 使用证书和私钥文件
   - 更偏历史方案或兼容旧流程时使用

原始笔记里保留的一条结论值得继续保留：

>早期 APNs 常见做法是证书方式；后来的 token-based 方式更适合长期维护，因为密钥标识符可持续使用，泄露时再单独吊销即可。

## 2. 调试前要先确认的几个量

无论用哪种方式，下面几个参数都要先确认清楚：

- `TEAM_ID`：Apple Developer 团队 ID
- `AUTH_KEY_ID`：APNs key identifier
- `TOKEN_KEY_FILE_NAME`：对应的 `.p8` 私钥文件
- `DEVICE_TOKEN`：目标设备 token
- `TOPIC`：App 的 bundle id
- `APNS_HOST_NAME`：调试环境主机名

常用主机：

- 开发环境：`api.sandbox.push.apple.com`
- 正式环境：`api.push.apple.com`

这里最容易混淆的是 `TOPIC` 和 `DEVICE_TOKEN`。  
`DEVICE_TOKEN` 是跟具体 App 标识绑定的，如果 `TOPIC` 写错，通常会得到 topic 与 device token 不匹配之类的错误。

## 3. 先确认本机 curl 是否支持 HTTP/2

APNs 请求需要 HTTP/2，因此在动手前先跑一遍：

```bash
curl -V
```

如果输出里 `Features` 包含 `HTTP2`，说明当前 curl 可以直接拿来调试。例如：

```text
curl 7.78.0 (x86_64-apple-darwin20.6.0) libcurl/7.78.0 OpenSSL/1.1.1l zlib/1.2.11 zstd/1.5.0 libidn2/2.3.2 libpsl/0.21.1 (+libidn2/2.3.2) nghttp2/1.45.1
Protocols: dict file ftp ftps gopher gophers http https imap imaps mqtt pop3 pop3s rtsp smb smbs smtp smtps telnet tftp
Features: alt-svc AsynchDNS HSTS HTTP2 HTTPS-proxy IDN IPv6 Largefile libz NTLM NTLM_WB PSL SSL TLS-SRP UnixSockets zstd
```

## 4. token-based：用 shell 脚本直接测 APNs

原始笔记里最有价值的部分，是这条可以直接打通链路的 shell 脚本。整理后保留成下面这版：

```zsh
#!/usr/bin/env zsh

set -e

TEAM_ID="YOUR_TEAM_ID"
AUTH_KEY_ID="YOUR_AUTH_KEY_ID"
TOKEN_KEY_FILE_NAME="/path/to/AuthKey_XXXXXXXXXX.p8"
TOPIC="com.example.app"
DEVICE_TOKEN="YOUR_DEVICE_TOKEN"
APNS_HOST_NAME="api.sandbox.push.apple.com"

JWT_ISSUE_TIME=$(date +%s)
JWT_HEADER=$(printf '{ "alg": "ES256", "kid": "%s" }' "${AUTH_KEY_ID}" | openssl base64 -e -A | tr -- '+/' '-_' | tr -d '=')
JWT_CLAIMS=$(printf '{ "iss": "%s", "iat": %d }' "${TEAM_ID}" "${JWT_ISSUE_TIME}" | openssl base64 -e -A | tr -- '+/' '-_' | tr -d '=')
JWT_HEADER_CLAIMS="${JWT_HEADER}.${JWT_CLAIMS}"
JWT_SIGNED_HEADER_CLAIMS=$(printf "%s" "${JWT_HEADER_CLAIMS}" | openssl dgst -binary -sha256 -sign "${TOKEN_KEY_FILE_NAME}" | openssl base64 -e -A | tr -- '+/' '-_' | tr -d '=')
AUTHENTICATION_TOKEN="${JWT_HEADER}.${JWT_CLAIMS}.${JWT_SIGNED_HEADER_CLAIMS}"

/usr/bin/curl -v \
  --header "apns-topic: ${TOPIC}" \
  --header "apns-push-type: alert" \
  --header "authorization: bearer ${AUTHENTICATION_TOKEN}" \
  --data '{"aps":{"alert":"test"}}' \
  --http2 "https://${APNS_HOST_NAME}/3/device/${DEVICE_TOKEN}"
```

### 这段脚本主要在做什么

1. 用 `TEAM_ID` 和 `AUTH_KEY_ID` 拼 JWT header / claims
2. 使用 `.p8` 私钥按 **ES256** 算法签名
3. 把 JWT 放到 `authorization: bearer ...` 头里
4. 用 curl 直接请求 APNs HTTP/2 接口

### 使用时优先检查的点

- `.p8` 文件路径是否正确
- `TOPIC` 是否和 App bundle id 一致
- `DEVICE_TOKEN` 是否来自同一套环境
- 沙盒 token 不要拿去请求正式环境，反之亦然

## 5. jwt-cpp 试验代码：核心是 ES256 和密钥格式

原始记录里有一大段 jwt-cpp 实验代码，核心信息其实只有两条：

1. APNs token 要用 **ES256**
2. jwt-cpp 这类库在本地实验时，通常更适合直接喂 **PEM** 格式私钥

因此先把 `.p8` 转成 `.pem`：

```bash
openssl pkcs8 -nocrypt -in AuthKey_XXXXXXXXXX.p8 -out AuthKey.pem
```

整理后保留一份最小示例：

```cpp
std::string ec_priv_key = R"(-----BEGIN PRIVATE KEY-----
YOUR_PRIVATE_KEY
-----END PRIVATE KEY-----)";

auto token = jwt::create()
                 .set_issuer("YOUR_TEAM_ID")
                 .set_key_id("YOUR_AUTH_KEY_ID")
                 .set_type("JWS")
                 .set_issued_at(std::chrono::system_clock::now())
                 .sign(jwt::algorithm::es256("", ec_priv_key, "", ""));

std::cout << token << std::endl;
```

原始笔记里还保留了对 decode 结果的观察，结论同样值得留下：

```text
alg = "ES256"
kid = "YOUR_AUTH_KEY_ID"
iss = "YOUR_TEAM_ID"
```

这说明 shell 脚本生成的 token，在结构上就是一个标准的 ES256 JWT。

### 回看这段实验代码时要注意

- `verify()` 走的是公钥校验思路
- `create()` / `sign()` 走的是私钥签名思路
- APNs 的 token 鉴权重点不是“随便生成一个 JWT”，而是**按 Apple 要求生成 ES256 签名 JWT**

原始记录里还尝试过 `hs256` 之类的代码路径，但对 APNs 场景并不适用，回看时可以直接忽略。

## 6. certificate-based：证书方式的 curl 备忘

如果要回查旧方案，可以保留下面这条最小脚本：

```zsh
#!/usr/bin/env zsh

set -e

TOPIC="com.example.app"
DEVICE_TOKEN="YOUR_DEVICE_TOKEN"
APNS_HOST_NAME="api.push.apple.com"

CERTIFICATE_FILE_NAME="/path/to/certificate.pem"
CERTIFICATE_KEY_FILE_NAME="/path/to/private_key.pem"

/usr/bin/curl -v \
  --header "apns-topic: ${TOPIC}" \
  --header "apns-push-type: alert" \
  --cert "${CERTIFICATE_FILE_NAME}" --cert-type PEM \
  --key "${CERTIFICATE_KEY_FILE_NAME}" --key-type PEM \
  --data '{"aps":{"alert":"test hello"}}' \
  --http2 "https://${APNS_HOST_NAME}/3/device/${DEVICE_TOKEN}"
```

这套方式的重点不是 JWT，而是：

- 证书文件格式是否正确
- 证书和私钥是否配套
- 当前证书是否覆盖目标 App / 环境

## 7. 最后只保留几条最实用的排查提醒

如果 APNs 调试不通，优先按下面顺序看：

1. curl 是否支持 HTTP/2
2. 请求的是沙盒还是正式环境
3. `TOPIC` 是否和 App bundle id 一致
4. `DEVICE_TOKEN` 是否属于同一个 App 和同一环境
5. token-based 场景里，JWT 是否确实按 ES256 生成
6. certificate-based 场景里，证书和私钥是否匹配

## 8. 参考链接

- https://developer.apple.com/documentation/usernotifications/setting_up_a_remote_notification_server/establishing_a_token-based_connection_to_apns
- https://forums.mbed.com/t/jwt-es256-token-using-ecdsa/13068
- https://github.com/Thalhammer/jwt-cpp
- https://github.com/arun11299/cpp-jwt
- https://www.cnblogs.com/moodlxs/archive/2012/10/15/2724318.html
- https://eclipsesource.com/blogs/2016/09/07/tutorial-code-signing-and-verification-with-openssl/
- https://0x90e.github.io/2017/02/12/verify_a_signature_with_certificate/
- https://juejin.cn/post/6991476688345366564
- https://www.cnblogs.com/tml839720759/p/3926006.html
- https://www.cnblogs.com/bohat/p/12482357.html
