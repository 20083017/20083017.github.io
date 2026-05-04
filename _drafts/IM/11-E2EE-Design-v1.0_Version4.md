# 端到端加密（E2EE）设计 v1.0

> 适用：私聊 / 群聊 端到端加密  
> 协议：Signal Protocol (Double Ratchet + X3DH + Sender Keys)  
> 目标：服务端不可见消息内容、前向安全、后向安全

---

## 目录

1. 安全目标
2. Signal 协议总览
3. 密钥协商 (X3DH)
4. 双棘轮 (Double Ratchet)
5. 群组加密 (Sender Keys)
6. 服务端职责
7. 多设备同步
8. 实现注意事项

---

# 1. 安全目标

## 1.1 安全属性

| 属性 | 含义 |
|---|---|
| **机密性** | 服务端无法解密 |
| **完整性** | 消息不可篡改 |
| **认证性** | 确认发送者身份 |
| **前向安全** | 长期密钥泄露不影响历史消息 |
| **后向安全** | 单条消息密钥泄露不影响后续消息 |
| **否认性** | 无��证明某条消息确实是某人发的 |

## 1.2 威胁模型

```
假设:
  - 服务端可被攻陷
  - 网络可被监听
  - 客户端在用户设备上是可信的

不防:
  - 客户端被入侵
  - 用户被胁迫
  - 元数据（谁和谁聊、何时聊）
```

---

# 2. Signal 协议总览

## 2.1 三大组件

```
1. X3DH (Extended Triple Diffie-Hellman)
   → 密钥协商，建立初始会话

2. Double Ratchet
   → 持续密钥更新，前向 + 后向安全

3. Sender Keys
   → 群组加密优化
```

## 2.2 整体流程

```
首次会话:
  X3DH → 共享密钥 SK
  SK → 初始化 Double Ratchet

后续消息:
  Double Ratchet → 每条消息独立密钥
  
群组:
  每个发送者维护 Sender Key Chain
  对群成员一对一发送 Sender Key
  群消息只用 Sender Key 加密一次
```

---

# 3. 密钥协商 (X3DH)

## 3.1 密钥类型

每个用户维护：

| 密钥 | 长期/短期 | 用途 |
|---|---|---|
| Identity Key (IK) | 长期 | 身份认证 |
| Signed Pre Key (SPK) | 中期 (周/月轮换) | 用 IK 签名 |
| One-Time Pre Keys (OPK) | 一次性 | 一次性 |

## 3.2 服务端 Pre-Key Bundle

```
用户上传到服务端:
{
  IK_pub:     长期身份公钥
  SPK_pub:    签名预共享公钥
  SPK_sig:    SPK 用 IK 签名
  OPKs:       [OPK1_pub, OPK2_pub, ...]  100 个
}

服务端职责:
  - 存储 bundle
  - 给请求方分发 SPK + 一个 OPK
  - 删除已用 OPK
  - 客户端补充 OPK (低于 10 时通知)
```

## 3.3 X3DH 协商流程

```
A 想给 B 发消息（首次）:

1. A 从服务端获取 B 的 PreKeyBundle:
   - IK_B
   - SPK_B + SPK_sig_B
   - OPK_B (可选)
   
2. A 验证 SPK_sig_B (用 IK_B)

3. A 生成临时密钥 EK_A

4. A 计算 4 个 DH:
   DH1 = DH(IK_A, SPK_B)
   DH2 = DH(EK_A, IK_B)
   DH3 = DH(EK_A, SPK_B)
   DH4 = DH(EK_A, OPK_B)   # 如有 OPK
   
   SK = KDF(DH1 || DH2 || DH3 || DH4)

5. A 构造首条消息:
   - IK_A_pub
   - EK_A_pub
   - 用 SK 派生的密钥加密的消息
   - OPK_id (告诉 B 用哪个 OPK)

6. A 发送给服务端

7. B 收到:
   - 取出对应 OPK 私钥
   - 计算同样的 4 个 DH (用自己私钥 + A 的公钥)
   - 派生相同 SK
   - 解密
```

## 3.4 关键安全性

```
只有 IK_B 泄露 → 不影响（需要 SPK 和 OPK）
只有 SPK_B 泄露 → 不影响（需要 IK 和 OPK）
所有都泄露 → 历史消息可解密（防止此场景靠定期轮换）
```

---

# 4. 双棘轮 (Double Ratchet)

## 4.1 核心思想

每条消息用不同的密钥加密。  
密钥不断"棘轮式"前进，不可逆。

## 4.2 两个棘轮

### DH 棘轮（外层）

```
每次发送方有新消息要发 →
  生成新 DH 密钥对
  消息携带新公钥
  接收方收到后用自己当前 DH 私钥 + 新公钥 → 计算共享密钥 → 派生新 root key
```

### Symmetric 棘轮（内层）

```
对称密钥不断 KDF 派生:
  CK_0 → CK_1 → CK_2 → ...
  
每个 CK 派生一个 message key:
  MK_i = KDF(CK_i)
  
用完即弃,无法回推
```

## 4.3 状态机

每个会话维护：

```
RootKey (RK)
SendingChainKey (CKs)
ReceivingChainKey (CKr)

DHs (本端 DH 密钥对)
DHr (对端 DH 公钥)

Ns (本端发送计数)
Nr (本端接收计数)
PN (上一棘轮的发送计数)

MKSKIPPED (跳过的 message keys，处理乱序)
```

## 4.4 发送消息

```python
def encrypt_message(state, plaintext):
    # 派生 message key
    state.CKs, MK = KDF_CK(state.CKs)
    
    # 加密
    ciphertext = AES_GCM(MK, plaintext, header)
    
    # 构造 header
    header = {
        "DH": state.DHs.public,
        "PN": state.PN,
        "N": state.Ns
    }
    
    state.Ns += 1
    
    return header, ciphertext
```

## 4.5 接收消息

```python
def decrypt_message(state, header, ciphertext):
    # 处理跳过的 keys (乱序到达)
    plaintext = try_skipped_keys(state, header, ciphertext)
    if plaintext: return plaintext
    
    # 检查是否是新 DH ratchet
    if header.DH != state.DHr:
        # 跳过当前 chain 中剩余的 keys
        skip_message_keys(state, header.PN)
        # 执行 DH ratchet
        DH_ratchet(state, header)
    
    # 跳过到当前 N
    skip_message_keys(state, header.N)
    
    # 派生 message key
    state.CKr, MK = KDF_CK(state.CKr)
    state.Nr += 1
    
    # 解密
    return AES_GCM_Decrypt(MK, ciphertext, header)


def DH_ratchet(state, header):
    state.PN = state.Ns
    state.Ns = 0
    state.Nr = 0
    state.DHr = header.DH
    
    # 用对端新公钥更新 root key
    state.RK, state.CKr = KDF_RK(state.RK, DH(state.DHs.private, state.DHr))
    
    # 生成新 DH 密钥对
    state.DHs = generate_DH()
    state.RK, state.CKs = KDF_RK(state.RK, DH(state.DHs.private, state.DHr))
```

## 4.6 处理乱序

```
A 发送: msg1 (N=0), msg2 (N=1), msg3 (N=2)
B 收到顺序: msg1, msg3, msg2

收到 msg3 时:
  N=2, 当前期望 N=1
  把 N=1 的 message key 算出来存到 MKSKIPPED
  解密 msg3

收到 msg2 时:
  从 MKSKIPPED 找到 N=1 的 key
  解密
  删除已用 key
```

`MKSKIPPED` 上限（如 1000），防止 DoS。

---

# 5. 群组加密 (Sender Keys)

## 5.1 难点

```
N 人群, 每条消息要给 N 个人加密 → O(N) 次加密 + 巨大流量

解决: Sender Keys
```

## 5.2 Sender Key 模型

```
每个发送者在每个群里维护一个 Sender Key Chain:
  SK_chain (对称密钥)

每条群消息:
  用 SK_chain 当前 message key 加密
  广播给所有成员

新成员加入:
  发送者用 1对1 (Double Ratchet) 把当前 SK_chain 状态发给新成员
```

## 5.3 流程

### 初始化

```
A 建群 / 加入群:
  生成 Sender Key (随机)
  对每个群成员用 1对1 加密 (用各自的 Double Ratchet 会话) 发送 Sender Key
  
群成员收到 Sender Key:
  存储 (groupId, senderId) → SenderKey
```

### 发送

```
A 在群里发消息:
  用自己的 Sender Key 派生 message key
  加密消息
  广播 (服务端只看到密文)
  
A 推进自己的 Sender Key Chain
```

### 接收

```
B 收到群消息:
  根据 senderId 找对应的 Sender Key
  派生同样的 message key
  解密
```

### 成员变更

```
新成员加入:
  现有成员把当前 Sender Key 状态发给新成员
  (新成员只能看到加入之后的消息)

成员退出:
  剩余成员重新生成各自的 Sender Key
  分发给剩余成员
  (退出成员的 Sender Key 失效)
```

## 5.4 Sender Key 轮换

```
触发:
  - 成员变化
  - 一定时间 (如 7 天)
  - 一定消息数 (如 1000 条)
```

## 5.5 大群挑战

```
万人群每次成员变化要 1对1 给 9999 人发新 SK → 不可行

折中:
  - 大群放弃严格 E2EE
  - 用群密钥 (服务端中转加密) 
  - 或 MLS 协议（IETF 标准化中,支持大群）
```

---

# 6. 服务端职责

## 6.1 服务端能做什么

```
✅ 存储 PreKey Bundle
✅ 中转密文消息
✅ 元数据（who-when-to-whom）
✅ 验证身份
✅ 路由
```

## 6.2 服务端不能做什么

```
❌ 解密消息内容
❌ 修改消息内容
❌ 知道密钥
```

## 6.3 元数据保护

```
即使内容加密,元数据也很敏感:
  - 谁和谁聊
  - 何时聊
  - 频率
  
进阶保护:
  - Sealed Sender (Signal): 隐藏发送者
  - Mixnets / Onion Routing
  - 需要权衡性能
```

---

# 7. 多设备同步

## 7.1 难点

```
用户在手机和 PC 都登录
B 给用户发消息 → 两个设备都要能解密

但每个设备有独立的密钥对
```

## 7.2 方案 A：每设备独立会话

```
每个设备用自己的 Identity Key 注册
A 给"用户 B"发消息 = 给 B 的所有设备分别加密
N 个设备 = N 次加密
```

Signal 用此方案。

## 7.3 方案 B：主设备 + 链接设备

```
主设备生成主密钥
副设备扫码后,主设备把密钥传给副设备
所有设备共享同一密钥
```

WhatsApp 早期方案。

## 7.4 历史消息同步

```
新设备登录 → 历史消息无法解密（密钥不同）

解决:
  方案 1: 不同步历史 (Signal)
  方案 2: 主设备解密后用其他方式 (备份密钥) 同步
```

---

# 8. 实现注意事项

## 8.1 库选择

```
推荐:
  libsignal-protocol (官方, C/Java/Swift)
  libolm (Matrix)
  
不要自己实现密码学
```

## 8.2 密钥存储

```
设备密钥:
  iOS: Keychain
  Android: KeyStore
  Web: 加密 IndexedDB (用密码派生)

绝不上传服务端
```

## 8.3 验证身份（防 MITM）

```
密钥协商不防中间人 (服务端可换 IK)
需要带外验证:
  - 安全码 (Safety Number)
  - 二维码扫描
  - 比对指纹
```

## 8.4 备份与恢复

```
难点: E2EE 与备份矛盾
方案:
  - iCloud Keychain (Apple)
  - 用户密码加密的云备份 (Signal)
  - PIN 码恢复
```

## 8.5 性能

```
加密性能 ≈ 普通 AES
影响:
  - 消息体增加 (header + 签名)
  - 离线同步慢一点
  - 群组大时密钥分发开销
```

## 8.6 服务端改动

```
- 增加 PreKey Bundle 接口
- 不能服务端搜索消息内容
- 不能服务端做内容审核（改为客户端举报）
- Push 内容只能是 "新消息"
```

## 8.7 不兼容场景

```
- 服务端搜索 (改为客户端搜索)
- 内容审核 (依赖举报)
- 监管要求 (E2EE 与监管冲突)
- 多设备历史 (受限)
```

---

# 附录：MLS（下一代群组 E2EE）

## A.1 简介

```
MLS = Messaging Layer Security
IETF 标准 (RFC 9420)
设计目标: 大群 E2EE
```

## A.2 优势

```
- O(log N) 成员变更
- 支持大群
- 形式化验证
- 异步运行
```

## A.3 状态

```
- WhatsApp 已迁移
- 其他 IM 也在跟进
- 取代 Sender Keys 是趋势
```

---

**文档结束** | Version 1.0