APNs 全称是 Apple Push Notification service （苹果推送通知服务）。

早期的 APNs 是使用证书的方式，缺点是有时效性，需要定期更换。

到了 iOS10 时期，苹果推出了新的认证方式：密钥标识符。

密钥标识符没有时效，可以永久使用，每个密钥标识符对应一个密钥文件，如果密钥文件泄露，可以注销密钥标识符使其失效。


#使用脚本测试 APNs

开发环境下使用沙盒服务器：api.sandbox.push.apple.com

正式环境服务器：api.push.apple.com

TEAM_ID 是开发者的组 ID，在这里查看：Locate your Team ID

AUTH_KEY_ID 是推送 token 的标识符，在这里查看：Get a key identifier

TOKEN_KEY_FILE_NAME 是推送 token 的密钥文件，每个 token 对应一个密钥，文件后缀是 p8，不要设置密码。

DEVICE_TOKEN 是目标设备上的 token，需要 Xcode 调试才能确定，格式是十六进制的字符串，相关信息查阅 Registering Your App with APNs 。

TOPIC 是 App 的 bundle id，DEVICE_TOKEN 是根据 bundle id 生成的，如果错误会收到 Topic 和 device token 不匹配的提示。

使用的 curl 需要支持 HTTP/2，如何确定：

```
# curl -V

curl 7.78.0 (x86_64-apple-darwin20.6.0) libcurl/7.78.0 OpenSSL/1.1.1l zlib/1.2.11 zstd/1.5.0 libidn2/2.3.2 libpsl/0.21.1 (+libidn2/2.3.2) nghttp2/1.45.1
Release-Date: 2021-07-21
Protocols: dict file ftp ftps gopher gophers http https imap imaps mqtt pop3 pop3s rtsp smb smbs smtp smtps telnet tftp 
Features: alt-svc AsynchDNS HSTS HTTP2 HTTPS-proxy IDN IPv6 Largefile libz NTLM NTLM_WB PSL SSL TLS-SRP UnixSockets zstd
```

输出的信息中，Features 列出的特性里如果有 HTTP2 就说明可以支持。

使用以下 shell 脚本来测试推送服务：


```
#!/usr/bin/env zsh

set -e

TEAM_ID=B********B
TOKEN_KEY_FILE_NAME="/path/to/APNs_AuthKey_3********3.p8"
AUTH_KEY_ID=3********3
TOPIC=com.********
DEVICE_TOKEN=d1aa48f********f2ed4761ad249f105375fb930a6cb713c12b0a43551b6e509
APNS_HOST_NAME=api.sandbox.push.apple.com

# openssl s_client -connect "${APNS_HOST_NAME}":443

JWT_ISSUE_TIME=$(date +%s)
JWT_HEADER=$(printf '{ "alg": "ES256", "kid": "%s" }' "${AUTH_KEY_ID}" | openssl base64 -e -A | tr -- '+/' '-_' | tr -d =)
JWT_CLAIMS=$(printf '{ "iss": "%s", "iat": %d }' "${TEAM_ID}" "${JWT_ISSUE_TIME}" | openssl base64 -e -A | tr -- '+/' '-_' | tr -d =)
JWT_HEADER_CLAIMS="${JWT_HEADER}.${JWT_CLAIMS}"
JWT_SIGNED_HEADER_CLAIMS=$(printf "${JWT_HEADER_CLAIMS}" | openssl dgst -binary -sha256 -sign "${TOKEN_KEY_FILE_NAME}" | openssl base64 -e -A | tr -- '+/' '-_' | tr -d =)
AUTHENTICATION_TOKEN="${JWT_HEADER}.${JWT_CLAIMS}.${JWT_SIGNED_HEADER_CLAIMS}"

/usr/bin/curl -v \
              --header "apns-topic: $TOPIC" \
              --header "apns-push-type: alert" \
              --header "authorization: bearer $AUTHENTICATION_TOKEN" \
              --data '{"aps":{"alert":"test"}}' \
              --http2 https://${APNS_HOST_NAME}/3/device/${DEVICE_TOKEN}
```







