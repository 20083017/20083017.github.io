# Push 服务多厂商对接 v1.0

> 适用：iOS/Android 离线消息推送  
> 厂商：APNs, FCM, 华为, 小米, OPPO, vivo, 魅族, 荣耀  
> 目标：高送达率、低延迟、容灾切换

---

## 目录

1. 总体架构
2. 厂商通道对比
3. 通道选择策略
4. 各厂商对接细节
5. Token 管理
6. 推送内容设计
7. 推送优先级与合并
8. 失败处理与降级
9. 配额与限流
10. 监控指标
11. 性能优化

---

# 1. 总体架构

## 1.1 架构图

```
┌────────────────────────────────────────────┐
│  Kafka: msg.push.high / msg.push.normal     │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────┐
│  Push Sender 集群                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Sender 1 │ │ Sender 2 │ │ Sender N │   │
│  └──────────┘ └──────────┘ └──────────┘   │
└──────────────────┬─────────────────────────┘
                   │
        ┌──────────┴───────────┐
        ▼                      ▼
┌──────────────┐        ┌──────────────┐
│ Channel      │        │ Token        │
│ Router       │        │ Manager      │
│ (选哪个厂商)  │        │ (Token 存取) │
└──────┬───────┘        └──────────────┘
       │
       ├──────────┬──────────┬──────────┬──────────┐
       ▼          ▼          ▼          ▼          ▼
   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐
   │APNs │   │FCM  │   │华为  │   │小米  │   │OPPO │
   └─────┘   └─────┘   └─────┘   └─────┘   └─────┘
```

## 1.2 核心模块

| 模块 | 职责 |
|---|---|
| **Push Sender** | 消费 Kafka，统一推送入口 |
| **Channel Router** | 选择最合适的推送通道 |
| **Channel Adapter** | 各厂商协议适配 |
| **Token Manager** | 设备 Token CRUD + 缓存 |
| **Rate Limiter** | 厂商配额控制 |
| **Retry Queue** | 失败重试 |
| **DLQ** | 死信队列 |

---

# 2. 厂商通道对比

## 2.1 主流通道对比

| 通道 | 平台 | 协议 | QPS 限制 | 送达率 | 时延 | 备注 |
|---|---|---|---|---|---|---|
| **APNs** | iOS | HTTP/2 | 单连接高 | > 95% | < 1s | Apple 官方 |
| **FCM** | Android (海外) | HTTP/XMPP | 较高 | > 90% | 1~5s | Google 官方 |
| **华为 Push** | 华为机型 | REST | 5000/s | > 95% | < 3s | 国内首选 |
| **小米 Push** | 小米机型 | REST | 限频 | > 95% | < 3s | 国内 |
| **OPPO Push** | OPPO 机型 | REST | 限频 | > 90% | < 3s | 国内 |
| **vivo Push** | vivo 机型 | REST | 限频 | > 90% | < 3s | 国内 |
| **魅族 Push** | 魅族机型 | REST | 限频 | > 90% | < 3s | 国内 |
| **荣耀 Push** | 荣耀机型 | REST | 限频 | > 95% | < 3s | 国内 |
| **应用自有通道** | Android (App 在线) | 长连接 | 不限 | 100% | < 100ms | 退到后台失效 |

## 2.2 国内 vs 国外

```
国内:
  - 华为/小米/OPPO/vivo 等系统通道（杀进程也能推）
  - FCM 在国内不可用
  - 自建长连接（App 在线时）
  
国外:
  - FCM 是事实标准
  - APNs (iOS)
  - Web Push (浏览器)
```

## 2.3 通道分级

```
Tier 1 (高优先级，立即送达):
  - APNs
  - 厂商系统通道（华为/小米/OPPO/vivo/...）
  - FCM high priority
  
Tier 2 (普通):
  - FCM normal
  - 自有长连接
  
Tier 3 (营销):
  - 营销专用通道
  - 限频严格
```

---

# 3. 通道选择策略

## 3.1 决策流程

```
推送请求
   │
   ▼
[1] 用户在线? → 自有长连接 → 完成
   │
   ▼ 离线
[2] iOS? → APNs → 完成
   │
   ▼ Android
[3] 设备品牌? 
   ├─ 华为 → 华为 Push
   ├─ 小米 → 小米 Push
   ├─ OPPO → OPPO Push
   ├─ vivo → vivo Push
   ├─ 魅族 → 魅族 Push
   ├─ 荣耀 → 荣耀 Push
   └─ 其他/Google 系 → FCM
```

## 3.2 厂商识别

```kotlin
// Android 客户端识别厂商
fun detectVendor(): String {
    val manufacturer = Build.MANUFACTURER.lowercase()
    val brand = Build.BRAND.lowercase()
    
    return when {
        "huawei" in manufacturer || "huawei" in brand -> "huawei"
        "honor" in manufacturer || "honor" in brand -> "honor"
        "xiaomi" in manufacturer || "redmi" in brand -> "xiaomi"
        "oppo" in manufacturer || "realme" in brand -> "oppo"
        "vivo" in manufacturer || "iqoo" in brand -> "vivo"
        "meizu" in manufacturer -> "meizu"
        else -> "fcm"
    }
}
```

客户端注册时上报到服务端：

```json
{
  "device_id": "...",
  "platform": "android",
  "vendor": "huawei",
  "push_token": "...",
  "app_version": "1.0.0"
}
```

## 3.3 多通道兜底

```
主通道发送 → 失败/超时
   │
   ▼ 降级
副通道 (FCM/自有长连接)
   │
   ▼ 仍失败
进入 DLQ
```

实现：

```go
func (s *PushSender) sendWithFallback(ctx context.Context, req *PushRequest) error {
    primary := s.router.Select(req.Device)
    
    err := s.send(ctx, primary, req)
    if err == nil {
        return nil
    }
    
    // 降级到 FCM（如果设备支持）
    if req.Device.HasGooglePlay {
        err2 := s.send(ctx, ChannelFCM, req)
        if err2 == nil {
            return nil
        }
    }
    
    // 降级到自有通道（只在 App 在线时有用）
    if s.isAppActive(req.Device) {
        return s.sendInApp(ctx, req)
    }
    
    return err
}
```

---

# 4. 各厂商对接细节

## 4.1 APNs (iOS)

### 协议
```
HTTP/2 长连接
端点: api.push.apple.com:443 (生产)
      api.development.push.apple.com:443 (开发)
```

### 鉴权
```
方式 1: 证书 (.p12)
方式 2: Token-based (.p8) - 推荐
```

### Token-based 鉴权代码

```go
import "github.com/sideshow/apns2"
import "github.com/sideshow/apns2/token"

func newAPNSClient() *apns2.Client {
    authKey, _ := token.AuthKeyFromFile("AuthKey_XXX.p8")
    
    apnsToken := &token.Token{
        AuthKey: authKey,
        KeyID:   "ABCDEF1234",
        TeamID:  "1234567890",
    }
    
    return apns2.NewTokenClient(apnsToken).Production()
}

func sendAPNS(client *apns2.Client, deviceToken string, payload []byte) error {
    notification := &apns2.Notification{
        DeviceToken: deviceToken,
        Topic:       "com.example.app",
        Payload:     payload,
        Priority:    apns2.PriorityHigh,
        PushType:    apns2.PushTypeAlert,
        CollapseID:  "conv_123",     // 同会话合并
        Expiration:  time.Now().Add(24 * time.Hour),
    }
    
    res, err := client.Push(notification)
    if err != nil {
        return err
    }
    
    if res.Sent() {
        return nil
    }
    return fmt.Errorf("apns reject: %s", res.Reason)
}
```

### Payload 格式

```json
{
  "aps": {
    "alert": {
      "title": "群聊名称",
      "subtitle": "张三",
      "body": "你好"
    },
    "badge": 5,
    "sound": "default",
    "thread-id": "conv_123",
    "category": "im_message",
    "mutable-content": 1,
    "content-available": 1
  },
  "ext": {
    "conv_id": "c123",
    "msg_id": "s888",
    "type": "mention"
  }
}
```

### 关键字段

| 字段 | 用途 |
|---|---|
| `apns-priority` | 10 (立即) / 5 (省电) |
| `apns-collapse-id` | 同 ID 替换旧推送 |
| `apns-expiration` | 过期时间 |
| `apns-push-type` | alert / background / voip |
| `thread-id` | 通知分组 |
| `mutable-content` | 触发 NSE 修改内容 |

### 错误处理

```go
// 常见错误
const (
    APNsBadDeviceToken    = "BadDeviceToken"
    APNsUnregistered      = "Unregistered"
    APNsExpiredToken      = "ExpiredToken"
    APNsTooManyRequests   = "TooManyRequests"
    APNsPayloadTooLarge   = "PayloadTooLarge"
)

func handleAPNSError(reason string, deviceToken string) {
    switch reason {
    case APNsBadDeviceToken, APNsUnregistered, APNsExpiredToken:
        // 永久失败，删除 token
        tokenMgr.Delete(deviceToken)
    case APNsTooManyRequests:
        // 临时失败，限流后重试
        time.Sleep(1 * time.Second)
    }
}
```

## 4.2 FCM (Firebase Cloud Messaging)

### 协议
```
HTTP/1 (Legacy) / HTTP v1 (推荐)
端点: fcm.googleapis.com/v1/projects/{project_id}/messages:send
```

### 鉴权
```
OAuth2 Service Account
```

### 代码示例

```go
import "firebase.google.com/go/v4/messaging"

func sendFCM(client *messaging.Client, token string, msg *Message) error {
    fcmMsg := &messaging.Message{
        Token: token,
        Notification: &messaging.Notification{
            Title: msg.Title,
            Body:  msg.Body,
        },
        Data: msg.Data,
        Android: &messaging.AndroidConfig{
            Priority:     "high",
            CollapseKey:  msg.ConvID,
            TTL:          ptr(24 * time.Hour),
        },
        APNS: &messaging.APNSConfig{
            Headers: map[string]string{
                "apns-priority": "10",
            },
        },
    }
    
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()
    
    _, err := client.Send(ctx, fcmMsg)
    return err
}
```

### 错误处理

```go
const (
    FCMInvalidArgument    = "INVALID_ARGUMENT"
    FCMUnregistered       = "UNREGISTERED"     // token 失效
    FCMSenderIDMismatch   = "SENDER_ID_MISMATCH"
    FCMQuotaExceeded      = "QUOTA_EXCEEDED"
    FCMUnavailable        = "UNAVAILABLE"
)
```

## 4.3 华为 Push

### 端点
```
https://push-api.cloud.huawei.com/v1/{appId}/messages:send
```

### 鉴权
```
1. 客户端 Credential → 获取 access_token (有效期 1h)
2. 请求带 Authorization: Bearer {access_token}
```

### Token 获取

```go
func getHuaweiAccessToken() (string, error) {
    resp, err := http.PostForm(
        "https://oauth-login.cloud.huawei.com/oauth2/v3/token",
        url.Values{
            "grant_type":    {"client_credentials"},
            "client_id":     {clientID},
            "client_secret": {clientSecret},
        },
    )
    if err != nil {
        return "", err
    }
    
    var result struct {
        AccessToken string `json:"access_token"`
        ExpiresIn   int    `json:"expires_in"`
    }
    json.NewDecoder(resp.Body).Decode(&result)
    
    // 缓存 token，提前 5min 刷新
    tokenCache.Set(result.AccessToken, time.Duration(result.ExpiresIn-300)*time.Second)
    
    return result.AccessToken, nil
}
```

### 推送请求

```json
POST /v1/{appId}/messages:send
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "validate_only": false,
  "message": {
    "notification": {
      "title": "群聊名",
      "body": "张三: 你好"
    },
    "android": {
      "collapse_key": -1,
      "urgency": "HIGH",
      "ttl": "86400s",
      "category": "IM",
      "notification": {
        "title": "群聊名",
        "body": "张三: 你好",
        "click_action": {
          "type": 1,
          "intent": "intent://...",
          "action": "..."
        }
      }
    },
    "data": "{\"conv_id\":\"c123\",\"msg_id\":\"s888\"}",
    "token": ["push_token_1"]
  }
}
```

### 关键参数

| 参数 | 说明 |
|---|---|
| `urgency` | HIGH / NORMAL |
| `category` | IM (即时通讯，不限频) / VOIP / SOCIAL_COMMUNICATION |
| `ttl` | 离线消息存活 |
| `collapse_key` | 同 key 合并 |

### 重要：分类申请

华为对推送有严格分类管理：
- **服务与通讯类（IM）** ← 即时通讯申请
- **资讯营销类**：限频，每天限制条数

必须申请 IM 自分类权益才能不限频。

## 4.4 小米 Push

### 端点
```
国内: https://api.xmpush.xiaomi.com/v3/message/regid
国际: https://api.xmpush.global.xiaomi.com/...
```

### 鉴权
```
HTTP Header: Authorization: key={AppSecret}
```

### 代码示例

```go
func sendXiaomi(req *XiaomiRequest) error {
    form := url.Values{
        "registration_id":  {req.Token},
        "title":            {req.Title},
        "description":      {req.Body},
        "payload":          {req.PayloadJSON},
        "notify_type":      {"-1"},     // 默认提示方式
        "pass_through":     {"0"},      // 通知栏消息
        "extra.notify_foreground": {"1"},
        "extra.channel_id": {"im_high"},  // 通知分组
    }
    
    httpReq, _ := http.NewRequest("POST", endpoint, strings.NewReader(form.Encode()))
    httpReq.Header.Set("Authorization", "key="+appSecret)
    httpReq.Header.Set("Content-Type", "application/x-www-form-urlencoded")
    
    resp, err := http.DefaultClient.Do(httpReq)
    // ...
}
```

### 通道分类

```
默认通道:        限频 1000 条/秒
IM 通道:        申请后不限频
资讯营销通道:    限频
```

## 4.5 OPPO Push

### 端点
```
https://api.push.oppomobile.com/server/v1/auth        # 鉴权
https://api.push.oppomobile.com/server/v1/message/notification/unicast  # 单推
```

### 鉴权（每天获取一次 auth_token）

```go
func getOPPOAuthToken() (string, error) {
    timestamp := time.Now().UnixMilli()
    sign := sha256(fmt.Sprintf("%s%d%s", appKey, timestamp, masterSecret))
    
    // POST 拿 auth_token
    // ...
}
```

## 4.6 vivo Push

### 端点
```
https://api-push.vivo.com.cn/message/auth
https://api-push.vivo.com.cn/message/send
```

### 关键限制
- 单设备每天 5 条普通消息
- IM 类需申请白名单

## 4.7 各厂商共性总结

```
都需要:
  1. 客户端 SDK 集成
  2. 注册时获取 device token
  3. 上报服务端
  4. 服务端按 token 推送
  5. 鉴权 (token / signature)
  6. 错误处理（token 失效要清理）
  
都支持:
  - 通知栏消息
  - 透传消息（应用在线才收到）
  - 角标
  - 折叠（collapse）
  - TTL
```

---

# 5. Token 管理

## 5.1 Token 表设计

```sql
CREATE TABLE push_token (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id         BIGINT NOT NULL,
  device_id       VARCHAR(64) NOT NULL,
  platform        VARCHAR(16) NOT NULL,    -- ios / android
  vendor          VARCHAR(32) NOT NULL,    -- apns / fcm / huawei / xiaomi ...
  token           VARCHAR(512) NOT NULL,
  app_version     VARCHAR(32),
  os_version      VARCHAR(32),
  language        VARCHAR(8),
  timezone        VARCHAR(32),
  status          TINYINT DEFAULT 1,       -- 0:invalid 1:active
  last_active_at  BIGINT,
  created_at      BIGINT NOT NULL,
  updated_at      BIGINT NOT NULL,
  
  UNIQUE KEY uk_device (user_id, device_id),
  KEY idx_user (user_id),
  KEY idx_token (token(64))                  -- 反查用
) PARTITION BY HASH(user_id) PARTITIONS 64;
```

## 5.2 Token 注册

```go
func RegisterPushToken(req *RegisterReq) error {
    // 1. 校验
    if req.Token == "" || req.Vendor == "" {
        return ErrInvalidArg
    }
    
    // 2. UPSERT
    db.Exec(`
        INSERT INTO push_token (user_id, device_id, platform, vendor, token, ...)
        VALUES (?, ?, ?, ?, ?, ...)
        ON DUPLICATE KEY UPDATE 
          token = VALUES(token),
          vendor = VALUES(vendor),
          updated_at = VALUES(updated_at)
    `, req.UserID, req.DeviceID, req.Platform, req.Vendor, req.Token)
    
    // 3. 缓存
    redis.HSet(fmt.Sprintf("push_tokens:%d", req.UserID), req.DeviceID, req.Token)
    
    return nil
}
```

## 5.3 Token 失效处理

```go
func MarkTokenInvalid(token string, reason string) {
    db.Exec(`
        UPDATE push_token 
        SET status = 0, updated_at = ? 
        WHERE token = ?
    `, time.Now().UnixMilli(), token)
    
    // 清缓存
    // 上报指标
    metrics.TokenInvalid.WithLabelValues(reason).Inc()
}

// 各厂商失败时调用
case APNsBadDeviceToken, APNsUnregistered:
    MarkTokenInvalid(token, "apns_unregistered")
case FCMUnregistered:
    MarkTokenInvalid(token, "fcm_unregistered")
```

## 5.4 Token 缓存

```
Key: push_tokens:{userId}
Type: Hash
Field: deviceId
Value: {vendor, token, ...} (JSON)
TTL: 1h
```

每次推送优先查 Redis，miss 回源 DB 并回填。

## 5.5 Token 清理

```sql
-- 每天清理 30 天未活跃的 token
DELETE FROM push_token 
WHERE last_active_at < UNIX_TIMESTAMP(NOW() - INTERVAL 30 DAY) * 1000;

-- 或：长期失效的
DELETE FROM push_token 
WHERE status = 0 AND updated_at < UNIX_TIMESTAMP(NOW() - INTERVAL 7 DAY) * 1000;
```

---

# 6. 推送内容设计

## 6.1 内容结构

```protobuf
message PushPayload {
  string title = 1;
  string body = 2;
  string subtitle = 3;
  
  // 显示
  string sound = 10;
  int32 badge = 11;
  string thread_id = 12;       // 分组
  string category = 13;
  
  // 数据
  string conv_id = 20;
  string msg_id = 21;
  string sender_id = 22;
  string msg_type = 23;        // text / image / mention / call
  
  // 行为
  string click_action = 30;    // 点击跳转
  
  // 优先级
  int32 priority = 40;         // 1:high 0:normal
  string collapse_id = 41;     // 合并 ID
  int64 expiration = 42;       // 过期时间
}
```

## 6.2 隐私模式

```kotlin
fun buildPushBody(msg: Message, settings: PushSettings): String {
    return when (settings.previewMode) {
        FULL -> "${msg.sender}: ${msg.preview}"
        SENDER_ONLY -> "${msg.sender} 发来一条消息"
        HIDDEN -> "您有一条新消息"
    }
}
```

## 6.3 多语言

服务端按用户语言生成不同内容：

```go
func localizedPushBody(userID int64, msg *Message) string {
    lang := getUserLanguage(userID)  // zh-CN / en-US / ja-JP
    
    template := i18n.Get(lang, "push.body")
    return fmt.Sprintf(template, msg.Sender, msg.Preview)
}
```

## 6.4 富文本推送（图片/卡片）

```
APNs:
  - mutable-content: 1
  - 客户端 NSE 下载图片
  
Android:
  - BigPictureStyle / BigTextStyle
  - 各厂商支持不同
```

---

# 7. 推送优先级与合并

## 7.1 优先级映射

| 业务场景 | 优先级 | 通道 | 合并 |
|---|---|---|---|
| @ 我的消息 | 高 | apns_high / fcm_high | 否 |
| 私聊 | 高 | apns_high / fcm_high | 否 |
| 引用回复 | 高 | apns_high / fcm_high | 否 |
| 普通群消息 | 中 | apns / fcm | 是（按会话合并） |
| 系统通知 | 中 | apns / fcm | 否 |
| 营销消息 | 低 | 营销专用通道 | 是 |

## 7.2 合并策略

### 时间窗口聚合

```
1 秒内同一 (userId, convId) 多条消息
合并为 1 条: "X 条新消息"
```

实现：

```go
type AggregateKey struct {
    UserID int64
    ConvID int64
}

type Aggregator struct {
    pending map[AggregateKey][]*Message
    timer   *time.Timer
    mu      sync.Mutex
}

func (a *Aggregator) Add(msg *Message) {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    key := AggregateKey{msg.UserID, msg.ConvID}
    a.pending[key] = append(a.pending[key], msg)
    
    if a.timer == nil {
        a.timer = time.AfterFunc(1*time.Second, a.flush)
    }
}

func (a *Aggregator) flush() {
    a.mu.Lock()
    pending := a.pending
    a.pending = make(map[AggregateKey][]*Message)
    a.timer = nil
    a.mu.Unlock()
    
    for key, msgs := range pending {
        if len(msgs) == 1 {
            sendNormal(msgs[0])
        } else {
            sendAggregated(key, msgs)
        }
    }
}
```

### 利用厂商合并能力

```
APNs:    apns-collapse-id
FCM:     collapse_key
华为:    collapse_key
小米:    notify_id

设置同 ID → 系统替换旧通知
```

## 7.3 免打扰处理

```go
func shouldSendPush(userID int64, msg *Message) bool {
    settings := getUserPushSettings(userID)
    
    // 全局免打扰
    if settings.GlobalMute && !msg.IsMention {
        return false
    }
    
    // 时间段免打扰
    if isInQuietHours(settings, time.Now()) && !msg.IsMention {
        return false
    }
    
    // 会话免打扰
    convSettings := getConvPushSettings(userID, msg.ConvID)
    if convSettings.Muted {
        // @ 我例外
        if msg.IsMention && convSettings.AllowMentionInMute {
            return true
        }
        return false
    }
    
    return true
}
```

---

# 8. 失败处理与降级

## 8.1 错误分类

| 类型 | 例子 | 处理 |
|---|---|---|
| 永久失败 | token 失效、不合法 | 删除 token，不重试 |
| 临时失败 | 网络抖动、限流 | 退避重试 |
| 配额耗尽 | 厂商 QPS 超限 | 降级到备用通道 |
| 内容拒绝 | payload 过大 | 缩减内容重发 |

## 8.2 重试机制

```go
func (s *PushSender) sendWithRetry(ctx context.Context, req *PushRequest) error {
    backoff := []time.Duration{
        100 * time.Millisecond,
        500 * time.Millisecond,
        2 * time.Second,
    }
    
    for i, delay := range backoff {
        if i > 0 {
            time.Sleep(delay)
        }
        
        err := s.send(ctx, req)
        if err == nil {
            return nil
        }
        
        if !isRetryable(err) {
            return err  // 永久失败
        }
    }
    
    // 重试用尽，进 DLQ
    return s.sendToDLQ(req)
}
```

## 8.3 DLQ 处理

```
DLQ topic: msg.push.high.dlq

消费者:
  - 记录失败原因
  - 人工分析模式
  - 部分错误可补偿（如 token 刷新）
```

## 8.4 降级策略

```go
// 厂商熔断
type ChannelHealth struct {
    SuccessRate float64
    LastError   time.Time
}

func (s *PushSender) selectChannel(device *Device) Channel {
    primary := primaryChannelFor(device)
    
    health := s.health[primary]
    if health.SuccessRate < 0.5 && time.Since(health.LastError) < 1*time.Minute {
        // 降级到备用
        return fallbackChannelFor(device)
    }
    
    return primary
}
```

---

# 9. 配额与限流

## 9.1 厂商配额

```
APNs:    单连接 ~1000 QPS（HTTP/2 多路复用）
FCM:     ~6000 QPS / project
华为:    5000 QPS（默认），可申请提升
小米:    3000 QPS（默认）
OPPO:    限频严格
vivo:    限频严格
```

## 9.2 限流实现

```go
type RateLimiter struct {
    limiters map[Channel]*rate.Limiter
}

func NewRateLimiter() *RateLimiter {
    return &RateLimiter{
        limiters: map[Channel]*rate.Limiter{
            ChannelAPNs:   rate.NewLimiter(rate.Limit(1000), 100),
            ChannelFCM:    rate.NewLimiter(rate.Limit(5000), 500),
            ChannelHuawei: rate.NewLimiter(rate.Limit(4000), 400),
            ChannelXiaomi: rate.NewLimiter(rate.Limit(2500), 250),
        },
    }
}

func (r *RateLimiter) Allow(ch Channel) bool {
    return r.limiters[ch].Allow()
}
```

超限时排队：

```go
func (s *PushSender) send(ctx context.Context, req *PushRequest) error {
    // 等待限流（最多 5s）
    waitCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()
    
    if err := s.rateLimiter.Wait(waitCtx, req.Channel); err != nil {
        return ErrRateLimited
    }
    
    return s.adapter.Send(ctx, req)
}
```

---

# 10. 监控指标

## 10.1 关键指标

| 指标 | 说明 |
|---|---|
| `push_sent_total{channel,result}` | 推送总数 |
| `push_latency{channel}` | 推送延迟 |
| `push_success_rate{channel}` | 成功率 |
| `push_token_invalid{channel,reason}` | Token 失效数 |
| `push_rate_limited{channel}` | 被限流次数 |
| `push_dlq_size{topic}` | DLQ 堆积 |
| `push_quota_remaining{channel}` | 配额余量 |

## 10.2 告警

```
P0: 任一厂商成功率 < 80% 持续 5 分钟
P1: DLQ 增长率异常
P1: 配额告罄
P2: 单个 token 连续失败
```

## 10.3 大盘

```
- 各厂商 QPS / 成功率
- 各错误码分布
- Token 池规模
- 端到端延迟（消息入库 → 推送送达）
```

---

# 11. 性能优化

## 11.1 连接复用

```
APNs: HTTP/2 长连接，多路复用
FCM:  HTTP/2
其他: HTTP/1.1 keepalive
```

## 11.2 批量发送

部分厂商支持批量：

```
FCM:    multicast (一次最多 500 token)
APNs:   不支持批量，但 HTTP/2 高并发即可
华为:   batch send (一次最多 1000 token)
小米:   regid_list (一次最多 1000 token)
```

## 11.3 异步并发

```go
// 同一推送任务给多个用户
func (s *PushSender) batchSend(reqs []*PushRequest) {
    sem := make(chan struct{}, 100)  // 并发 100
    var wg sync.WaitGroup
    
    for _, req := range reqs {
        wg.Add(1)
        sem <- struct{}{}
        go func(r *PushRequest) {
            defer wg.Done()
            defer func() { <-sem }()
            s.send(context.Background(), r)
        }(req)
    }
    
    wg.Wait()
}
```

## 11.4 缓存

- Access Token 缓存（华为、OPPO、vivo 都需要）
- Token 缓存（Redis）
- 用户推送设置缓存

---

# 附录：各厂商对接 Checklist

```
[ ] 注册厂商开发者账号
[ ] 创建 App / 获取 AppID/AppKey/AppSecret
[ ] 客户端集成 SDK
[ ] 客户端获取 Device Token
[ ] 服务端实现推送 API
[ ] 处理 Token 失效
[ ] 申请 IM 自分类（华为/小米/OPPO/vivo）
[ ] 监控接入
[ ] 测试覆盖（前台/后台/锁屏/灭屏）
[ ] 灰度上线
```

---

**文档结束** | Version 1.0