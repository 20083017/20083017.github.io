APNs 全称是 Apple Push Notification service （苹果推送通知服务）。

早期的 APNs 是使用证书的方式，缺点是有时效性，需要定期更换。

到了 iOS10 时期，苹果推出了新的认证方式：密钥标识符。

密钥标识符没有时效，可以永久使用，每个密钥标识符对应一个密钥文件，如果密钥文件泄露，可以注销密钥标识符使其失效。


# 使用脚本测试 APNs

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


# jwt-cpp 测试签名代码

p8文件转换为pem文件

```
openssl pkcs8 -nocrypt -in AuthKey_AZ495JLZUJ.p8   -out AuthKey.pem
```

```

//     std::string rsa_priv_key = R"(-----BEGIN PRIVATE KEY-----
// MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgiYjBk9AwaYG2o+aD
// 455NWrS98cG8h2VOt5y9QYbBwoChRANCAARVo+QFUSYq72Fo7eUs6SatF3XzFPyC
// /HO1KGJA0mxx0l0X2fXDtUoH0nT1/5xc7sw+G6fqchMWp1trrYCClrfo
// -----END PRIVATE KEY-----)";

//     auto token = jwt::create()
//                      .set_issuer("6T9LLJKSM4")   //TEAM_ID
//                      .set_key_id("AZ495JLZUJ")   //AUTH_KEY_ID
//                      .set_type("JWS")
//                      .set_id("com.baidu.baiduhitest")
//                      .set_issued_at(std::chrono::system_clock::now())
//                      .set_expires_at(std::chrono::system_clock::now() + std::chrono::seconds{36000})
//                     //  .set_payload_claim("sample", jwt::claim(std::string{"test"}))
//                      .sign(jwt::algorithm::es256("", rsa_priv_key, "", ""));

//     std::cout << "token:\n" << token << std::endl;

```

jwt-cpp代码选择es256的原因是，根据shell的token进行decode,decode的结果为ES256  ES256的含义是 使用私钥进行 sha256签名  ecdsa的签名
而es256签名算法，需要使用pem文件，不能使用p8文件，所以这里需要将p8文件转换为pem文件。

```
hello jwt-cpp!
iat = 1674094299
jwt-cpp decode success!
hello jwt-cpp!
iss = "6T9LLJKSM4"
jwt-cpp decode success!
alg = "ES256"
kid = "AZ495JLZUJ"
```

```
    // std::string token = "eyJhbGciOiJFUzI1NiIsImtpZCI6IkFaNDk1SkxaVUoiLCJ0eXAiOiJKV1MifQ.eyJleHAiOjE2NzQyMzQ3NjksImlhdCI6MTY3NDE5ODc2OSwiaXNzIjoiNlQ5TExKS1NNNCIsImp0aSI6ImNvbS5iYWlkdS5iYWlkdWhpdGVzdCIsInNhbXBsZSI6InRlc3QifQ.2pjy7NDyDmF2kVi9U8yAU5op4fqxOaZGKFKdW_vpgyAQcRMtniNhkMZOWiJWeK9NWrVcn8Xwi5hwJvK6XAJKbQ";
    // auto decoded = jwt::decode(token);

    // for(auto& e : decoded.get_payload_json())
    // {
    //     std::cout << "hello jwt-cpp!" << std::endl;
    //     std::cout << e.first << " = " << e.second << std::endl;
    //     std::cout << "jwt-cpp decode success!" << std::endl;
    // }

    // for (auto& e : decoded.get_header_json())
    // {
    //     std::cout << e.first << " = " << e.second << std::endl;
    // }
```


# jwt 函数简析

decode()函数：对你的token进行解码；

get_payload_claims()：获取jwt的payload的所有声明，利用std::cout << e1.first << " = " << e1.second.to_json() << std::endl;这句话可以打印输出jwt的负载部分；

get_header_claims()：获取jwt的header的所有声明，并同时可以打印输出jwt的头部；

此处，verify需要使用pubkey，使用何种算法，需要看
jwt::verify().allow_algorithm(jwt::algorithm::hs256{"secret"}).with_issuer("auth0")：声明一个解码器，利用该解码器可以对你的token值进行验证，hs256是你采用的加密算法，“secret”是你的密钥，这里可以根据自己的实际需求进行更改；

verifier.verify()：验证你的token值是否正确。这里我根据自己的实际情况对github上面的开源库做了略微的修改，使其实现：如果token正确的话返回true，token错误返回false；

此处，create使用prikey
jwt::create()：生成一个token；同时你可以设置token的过期时间，上述程序没有设置token的过期时间。


# 参考链接
https://www.cnblogs.com/moodlxs/archive/2012/10/15/2724318.html
https://eclipsesource.com/blogs/2016/09/07/tutorial-code-signing-and-verification-with-openssl/
https://0x90e.github.io/2017/02/12/verify_a_signature_with_certificate/
https://juejin.cn/post/6991476688345366564
https://www.cnblogs.com/tml839720759/p/3926006.html
https://www.cnblogs.com/bohat/p/12482357.html
https://developer.apple.com/documentation/usernotifications/setting_up_a_remote_notification_server/establishing_a_token-based_connection_to_apns?language=objc
https://forums.mbed.com/t/jwt-es256-token-using-ecdsa/13068    
code   
https://github.com/Thalhammer/jwt-cpp
https://github.com/arun11299/cpp-jwt





