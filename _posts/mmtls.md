---
layout:     post
title:      mmtls 协议笔记
subtitle:   微信自研 mmtls 与 TLS 1.3 在握手方式 / 公钥派发 / 密钥扩展上的取舍
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - 网络
    - 安全
    - TLS
    - 微信
    - mbedTLS
---

>原始笔记是几张图片夹着大段未拆分的 TLS / mmtls 论述，可读性很差。这里按"握手方式选择 / 签名密钥泄露与撤销 / 签名内容如何与本次握手绑定 / 1-RTT ECDHE 细节 / 密钥扩展（HKDF）/ verify_key 的下发与撤销 / 参考资料"分节整理，原文与配图原样保留。

## 当前保留内容

![image](https://user-images.githubusercontent.com/8308226/234161851-298a1b93-57cf-4589-828b-b9f2741d3cad.png)

### 1. 握手方式选择

(1) 客户端没有 PSK，为了安全性，这时和长连接的握手方式一样，使用 1-RTT ECDHE。

(2) 客户端有 PSK，这时为了减少网络时延，应该使用 0-RTT PSK 或 0-RTT PSK-ECDHE。在这两种握手方式下，由于业务请求包始终是基于 PSK 进行保护的，同一个 PSK 多次协商出来的对称加密 key 是同一个，这个对称加密 key 的安全性依赖于 ticket_key 的安全性，因此 0-RTT 情况下，业务请求包始终是无法做到前向安全性。0-RTT PSK-ECDHE 这种方式只能保证本短连接业务响应回包的前向安全性，这带来安全性上的优势是比较小的，但是与 0-RTT PSK 握手方式相比，0-RTT PSK-ECDHE 在每次握手对 server 会多 2 次 ECDH 运算和 1 次 ECDSA 运算。微信的短连接是非常频繁的，这对性能影响极大，因此综合考虑，在客户端有 PSK 的情况下，我们选择使用 0-RTT PSK 握手。

由于 0-RTT PSK 握手安全性依赖 ticket_key，为了加强安全性，在实现上：

- PSK 必须要限制过期时间，避免长期用同一个 PSK 来进行握手协商；
- ticket_key 必须定期轮换，且具有高度机密的运维级别。

三种方式：1-RTT ECDHE 握手、1-RTT PSK 握手、0-RTT PSK 握手。

> client 端本身的完整性，非 mmtls 协议保护的范畴；mmtls 仅对 server 端进行 ECDSA 认证——意思是 server 端需要进行 sign，client 端需要进行 verify。

### 2. 如何避免签名密钥 sign_key 泄露带来的影响？

沿用现有逻辑。

如果 sign_key 泄露，那么任何人都可以伪造成 Server 欺骗 Client，因为它拿到了 sign_key 就可以签发任何内容，Client 用 verify_key 去验证签名必然验签成功。因此 sign_key 如果泄露必须要能够对 verify_key 进行撤销，重新派发新的公钥。这其实和前一问题（公钥派发）是紧密联系的，本问题是公钥撤销问题。TLS 是通过 CRL 和 OCSP 两种方式来撤销公钥的，但是这两种方式存在撤销不及时或给验证带来额外延迟的副作用。由于 mmtls 是通过内置 verify_key 在客户端，必要时通过强制升级客户端的方式就能完成公钥撤销及更新。

另外，sign_key 是需要 Server 高度保密的，一般不会被泄露，对于微信后台来说，类似于 sign_key 这样需要长期私密保存的密钥之前也有存在，早已形成了一套方法和流程来应对长期私密保存密钥的问题。

### 3. 用 sign_key 进行签名的内容仅仅只包含 svr_pub_key 是否有隐患？

回顾一下，上面描述的带认证的 ECDH 协商过程似乎已经足够安全，无懈可击了。但是面对成亿的客户端发起 ECDH 握手到成千上万台接入层机器，每台机器对一个 TCP 连接随机生成不同的 ECDH 公私钥对，这里试想一种情况：假设某一台机器某一次生成的 ECDH 私钥 svr_pri_key1 泄露，这实际上是可能的——因为临时生成的 ECDH 公私钥对本身没有做任何保密保存的措施，是明文、短暂地存放在内存中，一般情况没有问题，但在分布式环境，大量机器大量随机生成公私钥对的情况下，难保某一次不被泄露。

这样用 sign_key（sign_key 是长期保存且分布式环境共享的）对 svr_pub_key1 进行签名得到签名值 Signature1。此时攻击者已经拿到 svr_pri_key1、svr_pub_key1 和 Signature1，他就可以实施中间人攻击：让客户端每次拿到的服务器 ECDH 公钥都是 svr_pub_key1。

- 客户端随机生成 ECDH 公私钥对 (cli_pub_key, cli_pri_key) 并将 cli_pub_key 发给 Server；
- 中间人将消息拦截下来，将 cli_pub_key 替换成自己生成的 cli_pub_key'，并将 svr_pub_key1 和 Signature1 回给 Client；
- Client 通过计算 `ECDH_Compute_Key(svr_pub_key1, cli_pri_key) = Key1`；
- Server 通过计算 `ECDH_Compute_Key(cli_pub_key', svr_pub_key) = Key'`；
- 中间人既可以计算出 Key1 和 Key'，这样它就可以用 Key1 和 Client 通信，用 Key' 和 Server 进行通信。

发生上述被攻击的原因在于一次握手中公钥的签名值被用于另外一次握手中。如果有一种方法能够使得这个签名值和一次握手一一对应，那么就能解决这个问题。

解决办法也很简单：在握手请求的 ClientHello 消息中带一个 Client_Random 随机值，然后在签名的时候将 Client_Random 和 svr_pub_key 一起做签名，这样得到的签名值就与 Client_Random 对应了。mmtls 在实际处理过程中，为了避免 Client 的随机数生成器有问题、造成生成不够随机的 Client_Random，实际上 Server 也会生成一个随机数 Server_Random，然后在对公钥签名的时候将 Client_Random、Server_Random、svr_pub_key 一起做签名——这样由 Client_Random、Server_Random 保证得到的签名值唯一对应一次握手。

### 4. 1-RTT ECDHE 细节

#### 4.1 随机数生成

随机数生成算法、防重放攻击，client_random、server_random，选择第 3 种：

1) `random` 函数：使用线性同余算法生成伪随机数（最初级随机数，不够随机）
2) `random_device`：linux 系统中为抓取 `/dev/urandom` 设备中生成的随机数流（真随机数，但还是不够随机）
3) `mt19937`：梅森旋转法，理论上可以产生完全随机数，一般使用 `random_device` 作为种子
4) `uniform_int_distribution`：整数均匀分布，对生成的随机数作处理，转换成一定范围均匀分布的随机数

#### 4.2 密钥扩展

TLS 1.3 明确要求通信双方使用的对称加密 Key 不能完全一样，否则在一些对称加密算法下会被完全攻破，即使是使用 AES-GCM 算法，如果通信双方使用完全相同的加密密钥进行通信，在使用的时候也要小心翼翼地保证一些额外条件，否则会泄露部分明文信息。另外，AES 算法的初始化向量（IV）如何构造也是很有讲究的，一旦用错就会有安全漏洞。

也就是说，对于 handshake 协议协商得到的 pre_master_secret 不能直接作为双方进行对称加密密钥，需要经过某种扩展变换，得到六个对称加密参数：

```
Client Write MAC Key    （用于Client算消息认证码，以及Server验证消息认证码）
Server Write MAC Key   （用于Server算消息认证码，以及Client验证消息认证码）
Client Write Encryption Key（用做Client做加密，以及Server解密）
Server Write Encryption Key（用做Server做加密，以及Client解密）
Client Write IV  （Client加密时使用的初始化向量）　
Server Write IV  （Server加密时使用的初始化向量）
```

当然，使用 AES-GCM 作为对称加密组件，MAC Key 和 Encryption Key 只需要一个就可以了。

握手生成的 pre_master_secret 只有 48 个字节，上述几个加密参数的长度加起来肯定就超过 48 字节了，所以需要一个函数来把 48 字节延长到需要的长度。在密码学中专门有一类算法承担密钥扩展的功能，称为密钥衍生函数（Key Derivation Function）。TLS 1.3 使用 HKDF 做密钥扩展，mmtls 也是选用的 HKDF 做密钥扩展。

在前文中，用 pre_master_secret 代表握手协商得到的对称密钥，在 TLS 1.2 之前确实叫这个名字，但是在 TLS 1.3 中由于需要支持 0-RTT 握手，协商出来的对称密钥可能会有两个，分别称为 Static Secret (SS) 和 Ephemeral Secret (ES)。从 TLS 1.3 文档中截取一张图进行说明：

![image](https://user-images.githubusercontent.com/8308226/234161990-9965d48a-17bb-4c1d-a0f9-6563390b1412.png)

上图中 Key Exchange 就是代表握手的方式：

- 在 1-RTT ECDHE 握手方式下：

```
ES=SS = ECDH_Compute_Key(svr_pub_key, cli_pri_key);
```

- 在 0-RTT ECDH 下：

```
SS=ECDH_Compute_Key(static_svr_pub_key, cli_pri_key), 
ES=ECDH_Compute_Key(svr_pub_Key, cli_pri_Key);
```

- 在 0-RTT/1-RTT PSK 握手下：

```
ES=SS=pre-shared key;
```

- 在 0-RTT PSK-ECDHE 握手下：

```
SS=pre-shared key，
ES=ECDH_Compute_Key(svr_pub_key, cli_pri_key);
```

mmtls 使用的密钥扩展组件为 HKDF，该组件定义了两个函数来保证扩展出来的密钥具有伪随机性、唯一性、不能逆推原密钥、可扩展任意长度密钥：

```
HKDF-Extract( salt, initial-keying-material )
```

该函数的作用是对 initial-keying-material 进行处理，保证它的熵均匀分布，足够伪随机。

```
HKDF-Expand( pseudorandom key, info, out_key_length )
```

参数 pseudorandom key 是已经足够伪随机的密钥扩展材料，HKDF-Extract 的返回值可以作为 pseudorandom key；info 用来区分扩展出来的 Key 是做什么用；out_key_length 表示希望扩展输出的 key 有多长。mmtls 最终使用的密钥是由 HKDF-Expand 扩展出来的。mmtls 把 info 参数分为 length、label、handshake_hash：其中 length 等于 out_key_length；label 是标记密钥用途的固定字符串；handshake_hash 表示握手消息的 hash 值——这样扩展出来的密钥保证连接内唯一。

![image](https://user-images.githubusercontent.com/8308226/234162280-f526093e-14d7-40ca-86ae-77848939f98e.png)

TLS 1.3 草案中定义的密钥扩展方式比较繁琐，如上图所示。为了得到最终认证加密的对称密钥，需要做 3 次 HKDF-Extract 和 4 次 HKDF-Expand 操作，实际测试发现这种密钥扩展方式对性能影响是很大的，尤其在 PSK 握手情况（PSK 握手没有非对称运算）这种密钥扩展方式成为性能瓶颈。

TLS 1.3 之所以把密钥扩展搞这么复杂，本质上还是因为 TLS 1.3 是一个通用的协议框架，具体的协商算法是可以选择的，在有些协商算法下，协商出来的 pre_master_key (SS 和 ES) 就不满足某些特性（如随机性不够），因此为了保证无论选择什么协商算法用它来进行通信都是安全的，TLS 1.3 就在密钥扩展上做了额外的工作。而 mmtls 没有 TLS 1.3 这种包袱，可以针对微信自己的网络通信特点进行优化（前面在握手方式选择上就有体现）。mmtls 在不降低安全性的前提下，对 TLS 1.3 的密钥扩展做了精简，使得性能上较 TLS 1.3 的密钥扩展方式有明显提升。

在 mmtls 中，pre_master_key (SS 和 ES) 经过密钥扩展，得到了一个长度为 `2*enc_key_length + 2*iv_length` 的一段 buffer，用 key_block 表示，其中：

```
client_write_key = key_block[0...enc_key_length-1]
client_write_key = key_block[enc_key_length...2*enc_key_length-1]
client_write_IV  = key_block[2*enc_key_length...2*enc_key_length+iv_length-1]
server_write_IV  = key_block[2*enc_key_length+iv_length...2*enc_key_length+2*iv_length-1]
```

#### 4.3 防重放

AES-GCM 使用 nonce（随机数），认证成功即可。

### 5. client 端 verify_pub_key 如何更新？

- **Verify_Key 如何下发给客户端？**

  这实际上是公钥派发的问题。TLS 是使用证书链的方式来派发公钥（证书），对于微信来说，如果使用证书链的方式来派发 Server 的公钥（证书），无论自建 Root CA 还是从 CA 处申请证书，都会增加成本且在验签过程中会存在额外的资源消耗。由于客户端是由我们自己发布的，可以将 verify_key 直接内置在客户端，这样就避免证书链验证带来的时间消耗以及证书链传输带来的带宽消耗。

- **server 端**

  ![image](https://user-images.githubusercontent.com/8308226/234162401-d630b188-b512-4f18-9224-89b684c8145e.png)

### 6. 参考资料

1. <https://yqf3139.github.io/2015/12/13/high-perf-network-in-chrome-trans/>

   ![image](https://user-images.githubusercontent.com/8308226/234162488-cfb26107-4044-4455-a332-46ae04a57ce9.png)

2. <https://mp.weixin.qq.com/s?__biz=MzAwNDY1ODY2OQ==&mid=2649286266&idx=1&sn=f5d049033e251cccc22e163532355ddf&scene=0&key=b28b03434249256b2a5d4fdf323a185a798eaf972317ca3a47ef060d35c5cd8a4ae35715466d5bb5a558e424d20bef6c&ascene=0&uin=Mjc3OTU3Nzk1&devicetype=iMac+MacBookPro10%2C1+OSX+OSX+10.10.5+build%2814F1713%29&version=11020201&pass_ticket=8lpzOjRJO3IS%2BmKcvsqRN%2FlzlWyR2q2fmKv15GKO2PPYAKDGPXDhyfntueC4bIod>

## mbedTLS 实战补充：AES IV 与 ECDH 握手时序图

> mbedTLS / curl 的踩坑记录（CIPHER_LIST、NDK 版本、抓包、裁剪 config）仍在独立的 [mbedtls 笔记]({{ site.baseurl }}/2026/04/25/mbedtls/) 里；这里只补两块和上文 mmtls 协议讨论紧密相关的内容：AES key 配套的 IV / nonce 怎么选、以及完整 1-RTT ECDHE 握手的时序图。

### 1. AES key 与 IV 的设置策略

下面只讨论"对称会话密钥已经协商好"之后，如何安全地选取 IV / nonce。结论先放在前面：

- **AES key**：来自 ECDH/HKDF 的派生结果（参见上文 §4.2 的 `key_block`），长度按算法选 16 / 24 / 32 字节，整条会话内不变。
- **IV / nonce**：**绝不能复用**，不同模式有不同要求（见下表）。

#### 1.1 不同模式下 IV 的硬性要求

| 模式            | IV / nonce 长度     | 是否需要随机 | 是否可公开传输 | 重复使用的后果                            |
| --------------- | ------------------- | ------------ | -------------- | ----------------------------------------- |
| AES-CBC         | 16 字节             | 必须不可预测 | 是             | 同 key 同 IV → 相同前缀的明文产生相同密文 |
| AES-CTR         | 16 字节（含计数器） | 唯一即可     | 是             | 同 (key, counter) → 直接异或泄漏明文      |
| AES-GCM         | 12 字节（推荐）     | 唯一即可     | 是             | **同 (key, IV) 直接破坏认证密钥，灾难性** |
| AES-CCM         | 7~13 字节           | 唯一即可     | 是             | 同 GCM，认证强度被打穿                    |

#### 1.2 推荐策略（mbedTLS 调用层）

- **优先 AES-GCM-12B nonce**，构造方式 `nonce = 4B salt || 8B counter`：
  - `salt` 由握手期 HKDF 派生（即上文 §4.2 中的 `client_write_IV` / `server_write_IV`），双方各持自己方向的 salt；
  - `counter` 从 0 开始，每发一帧 `+1`，到达 2^64-1 之前必须重协商；
  - 这样能保证"同一 key 下 nonce 全局唯一"，且不需要随机源。
- **CBC 场景**用 `mbedtls_ctr_drbg_random()` 现取 16 字节作为 IV，**和密文一起传给对端**，不要从计数器派生（CBC 要求"不可预测"，单调计数器不满足）。
- **CTR 场景**把 IV 拆成 `8B nonce || 8B block_counter`，`nonce` 每条消息独立，`block_counter` 在加密块内自增。
- 任何模式下：**key 轮换**（rekey）触发条件 = 计数器接近上限 / 累计加密字节超过 2^36 / 会话超时，三者取最早。

#### 1.3 mbedTLS 调用要点

- 加密前用 `mbedtls_gcm_setkey()` 一次，之后每条消息只调用 `mbedtls_gcm_crypt_and_tag()` / `mbedtls_gcm_auth_decrypt()`，传入新的 nonce。
- 不要直接复用 `mbedtls_gcm_starts()` + `update()` + `finish()` 的中间状态——重置不彻底容易让前一条消息的 nonce/计数器残留。
- IV 不需要保密，但**必须保证完整性**：在 GCM 中 IV 已经被纳入 GHASH 计算，篡改即认证失败；在 CBC 中要靠外层 MAC（推荐 Encrypt-then-MAC）覆盖 IV。

### 2. ECDH 握手时序图

下面是与本文前半部分讨论的"带服务端认证的 1-RTT ECDHE"对应的时序图，方便和上一节的 AES key 派生衔接。

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant S as Server
    participant V as 客户端内置 verify_key

    Note over C: 生成 (cli_pri, cli_pub)<br/>生成 client_random
    C->>S: ClientHello { client_random, cli_pub, cipher_suites }

    Note over S: 生成 (svr_pri, svr_pub)<br/>生成 server_random<br/>signature = ECDSA_sign(sign_key,<br/>client_random ‖ server_random ‖ svr_pub)
    S-->>C: ServerHello { server_random, svr_pub, signature }

    Note over C,V: ECDSA_verify(verify_key,<br/>client_random ‖ server_random ‖ svr_pub,<br/>signature) == OK
    C->>V: 验签
    V-->>C: 通过

    Note over C: shared_secret = ECDH(cli_pri, svr_pub)
    Note over S: shared_secret = ECDH(svr_pri, cli_pub)

    Note over C,S: HKDF-Extract(salt=client_random‖server_random,<br/>IKM=shared_secret) → PRK<br/>HKDF-Expand(PRK, "c2s key/iv") / ("s2c key/iv")<br/>得到 AES key + 12B salt（见上一节 §1.2）

    C->>S: Finished (AES-GCM, nonce = c2s_salt ‖ counter=0)
    S-->>C: Finished (AES-GCM, nonce = s2c_salt ‖ counter=0)

    Note over C,S: 业务数据：counter 各自单调递增，<br/>到上限前触发 rekey
```

如果 GitHub 没渲染 mermaid，可以读下面这份纯文本对照：

```
   Client                                      Server
     |                                            |
     | --- ClientHello (client_random, cli_pub) ->|
     |                                            |
     |                          生成 (svr_pri, svr_pub)
     |                          签名:
     |                            sig = sign(sign_key,
     |                                  client_random ||
     |                                  server_random ||
     |                                  svr_pub)
     | <-- ServerHello (server_random, svr_pub, sig) -|
     |                                            |
   verify(verify_key, ..., sig)                   |
   shared = ECDH(cli_pri, svr_pub)              shared = ECDH(svr_pri, cli_pub)
     |                                            |
     |  HKDF 派生:  c2s_key/c2s_salt, s2c_key/s2c_salt
     |                                            |
     | -- AES-GCM(c2s_key, c2s_salt||ctr++) ----->|
     | <- AES-GCM(s2c_key, s2c_salt||ctr++) ------|
     |                                            |
```

几个易错点（与上文 §3 的"签名仅含 svr_pub_key 的隐患"呼应）：

- 签名内容**必须**包含 `client_random` 和 `server_random`，否则攻击者可以把一次握手的 `(svr_pub, sig)` 重放到另一次握手里。
- `cli_pri / svr_pri` 是**临时**密钥对，每次握手新生成，握手完成后立即销毁——这是前向安全（PFS）的来源。
- HKDF 的 `salt` 用 `client_random ‖ server_random` 而不是常量，能避免不同会话派生出相同 PRK。
- 客户端做完 ECDH 之后立刻校验 `svr_pub` **不在小子群上**（X25519 由库内置处理；P-256 需要 `mbedtls_ecp_check_pubkey()`），否则会泄漏私钥。

## 后续可补的方向

- 把三种握手方式（1-RTT ECDHE / 0-RTT PSK / 0-RTT PSK-ECDHE）画成时序图，标出每段密钥的来源与生命周期。
- 对照 TLS 1.3 的 `HKDF-Expand-Label`，逐步梳理 mmtls 精简后到底省掉了哪几次 Extract/Expand。
- 跟踪 verify_key 的"客户端强制升级"流程：灰度策略、回滚开关、与旧版本的兼容窗口。
- 把上文 §1.2 的 AES-GCM nonce 拼装方式写成一个最小 demo，对照 mbedTLS 的 `gcm_self_test` 跑一遍。
- 在 §2 时序图基础上补 0-RTT PSK 与 0-RTT PSK-ECDHE 两种变体。
