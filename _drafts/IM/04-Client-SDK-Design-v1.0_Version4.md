# IM 客户端 SDK 设计文档 v1.0

> 适用平台：iOS / Android / PC / Web  
> 目标：弱网体验、消息不丢、跨端一致

---

## 目录

1. SDK 架构
2. 协议处理
3. 本地存储
4. 消息发送与重试
5. 消息接收与去重
6. 推拉协同同步
7. 离线消息处理
8. 多端协同
9. 网络质量自适应
10. 错误处理
11. 安全与隐私
12. SDK 接口设计

---

# 1. SDK 架构

## 1.1 模块结构

```
┌─────────────────────────────────────────┐
│         应用层 API (公开接口)             │
│  IMClient / Conversation / Message       │
├─────────────────────────────────────────┤
│         业务层                           │
│  ConvManager / MsgManager / Sync         │
│  Mention / Read / Recall                 │
├─────────────────────────────────────────┤
│         协议层                           │
│  Protocol Codec / Frame Builder          │
├─────────────────────────────────────────┤
│         传输层                           │
│  ConnManager / QUIC / WS / HTTP          │
│  Heartbeat / Reconnect                   │
├─────────────────────────────────────────┤
│         存储层                           │
│  LocalDB / Cache / FilePool              │
├─────────────────────────────────────────┤
│         基础工具                         │
│  Logger / Metrics / Crypto / Codec       │
└─────────────────────────────────────────┘
```

## 1.2 线程模型

```
主线程:    UI 回调
IO 线程:   Socket 读写
DB 线程:   单线程串行操作 (避免锁)
业务线程池: 消息处理、合并、同步
```

## 1.3 关键状态

```kotlin
enum class ConnectionState {
    IDLE,           // 未连接
    CONNECTING,     // 连接中
    AUTHENTICATING, // 鉴权中
    CONNECTED,      // 已连接
    RECONNECTING,   // 重连中
    DISCONNECTED    // 断开
}

enum class SyncState {
    IDLE,
    SYNCING,
    UP_TO_DATE
}
```

---

# 2. 协议处理

## 2.1 协议栈选择

```
默认: QUIC (UDP)
fallback: WebSocket (TCP)
最终 fallback: HTTPS 长轮询
```

## 2.2 协议探测

```kotlin
class ConnectionStrategy {
    suspend fun connect(): Connection {
        // 1. 优先用上次成功的协议
        val lastProtocol = prefs.getString("last_protocol", "quic")
        
        // 2. Happy Eyeballs：并发尝试
        val results = parallelConnect(
            quic(timeout = 3.seconds),
            ws(timeout = 5.seconds)
        )
        
        // 3. 取先成功的
        val connection = results.firstSuccess()
        
        // 4. 缓存协议偏好
        prefs.put("last_protocol", connection.protocol)
        
        return connection
    }
}
```

## 2.3 帧编解码

```kotlin
class FrameCodec {
    fun encode(cmd: Int, seqId: Long, body: ByteArray): ByteArray {
        val buf = ByteBuffer.allocate(18 + body.size)
        buf.put(0x4D.toByte())          // Magic
        buf.put(VERSION)
        buf.putShort(cmd.toShort())
        buf.putShort(0)                 // flags
        buf.putLong(seqId)
        buf.putInt(body.size)
        buf.put(body)
        return buf.array()
    }
    
    fun decode(stream: InputStream): Frame {
        val header = stream.readNBytes(18)
        // ... 解析
        return Frame(...)
    }
}
```

## 2.4 请求-响应匹配

```kotlin
class RequestRegistry {
    private val pending = ConcurrentHashMap<Long, CompletableDeferred<Frame>>()
    
    suspend fun request(cmd: Int, body: ByteArray, timeout: Duration): Frame {
        val seqId = nextSeqId()
        val deferred = CompletableDeferred<Frame>()
        pending[seqId] = deferred
        
        try {
            connection.send(encode(cmd, seqId, body))
            return withTimeout(timeout) { deferred.await() }
        } finally {
            pending.remove(seqId)
        }
    }
    
    fun onResponse(frame: Frame) {
        pending.remove(frame.seqId)?.complete(frame)
    }
}
```

---

# 3. 本地存储

## 3.1 数据库设计 (SQLite)

### 消息表
```sql
CREATE TABLE local_message (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id         INTEGER NOT NULL,
    server_msg_id   INTEGER,
    client_msg_id   TEXT NOT NULL,
    visible_seq     INTEGER,
    sender_id       INTEGER NOT NULL,
    msg_type        INTEGER NOT NULL,
    content         BLOB NOT NULL,
    status          INTEGER NOT NULL,    -- 0:sending 1:success 2:failed 3:recalled
    send_time       INTEGER,
    create_time     INTEGER,
    is_outgoing     INTEGER,
    
    UNIQUE (conv_id, visible_seq),
    UNIQUE (server_msg_id),
    INDEX idx_client (client_msg_id),
    INDEX idx_conv_time (conv_id, create_time)
);
```

### 会话表
```sql
CREATE TABLE local_conversation (
    conv_id         INTEGER PRIMARY KEY,
    conv_type       INTEGER,
    name            TEXT,
    avatar          TEXT,
    last_msg_id     INTEGER,
    last_msg_preview TEXT,
    last_msg_time   INTEGER,
    
    -- 游标
    max_visible_seq INTEGER DEFAULT 0,
    read_visible_seq INTEGER DEFAULT 0,
    read_mention_seq INTEGER DEFAULT 0,
    
    is_pinned       INTEGER DEFAULT 0,
    is_muted        INTEGER DEFAULT 0,
    cleared_seq     INTEGER DEFAULT 0,
    draft           TEXT
);
```

### 同步进度
```sql
CREATE TABLE local_sync_state (
    conv_id INTEGER PRIMARY KEY,
    last_sync_seq INTEGER,
    last_sync_time INTEGER
);
```

## 3.2 索引策略

```
local_message:
  PK: id
  UK: (conv_id, visible_seq)  -- 主要查询
  UK: server_msg_id           -- 跨端定位
  IDX: client_msg_id          -- 自己发的合并
  IDX: (conv_id, create_time) -- 历史滚动

local_conversation:
  PK: conv_id
  IDX: last_msg_time          -- 会话列表排序
```

## 3.3 加密

```
- DB 整库加密: SQLCipher (AES-256)
- 密钥: Keychain (iOS) / Keystore (Android)
- 大文件: ��独加密（PBE）
```

## 3.4 容量管理

```
- 默认保留 30 天本地消息
- 超过自动清理
- 用户可手动"清理本地缓存"
- 大文件按 LRU 清理
```

---

# 4. 消息发送与重试

## 4.1 发送流程

```kotlin
suspend fun sendMessage(conv: Long, content: MessageContent): MessageResult {
    // 1. 生成 client_msg_id
    val clientMsgId = generateClientMsgId()
    
    // 2. 本地落库 (status=sending)
    val localMsg = LocalMessage(
        convId = conv,
        clientMsgId = clientMsgId,
        content = content,
        status = SENDING,
        sendTime = currentTimeMillis(),
        isOutgoing = true
    )
    db.insert(localMsg)
    
    // 3. UI 立即显示
    listeners.onMessageInserted(localMsg)
    
    // 4. 加入发送队列
    val result = sendQueue.send(localMsg)
    
    // 5. 更新本地状态
    when (result) {
        is Success -> {
            db.update(localMsg.copy(
                serverMsgId = result.serverMsgId,
                visibleSeq = result.seq,
                status = SUCCESS
            ))
        }
        is Failure -> {
            db.update(localMsg.copy(status = FAILED))
        }
    }
    
    listeners.onMessageStatusChanged(localMsg)
    return result
}
```

## 4.2 发送队列

```kotlin
class SendQueue {
    private val queue = Channel<LocalMessage>(capacity = 100)
    
    suspend fun start() {
        for (msg in queue) {
            sendWithRetry(msg)
        }
    }
    
    private suspend fun sendWithRetry(msg: LocalMessage): Result {
        val maxAttempts = 3
        var attempt = 0
        
        while (attempt < maxAttempts) {
            try {
                val resp = connection.request(
                    cmd = SEND_MSG,
                    body = msg.toProto(),
                    timeout = 10.seconds
                )
                return Success(resp)
            } catch (e: TimeoutException) {
                attempt++
                delay(backoff(attempt))
            } catch (e: NetworkException) {
                // 网络失败，等连接恢复
                connection.waitForConnected()
            } catch (e: ProtocolException) {
                // 业务错误，不重试
                return Failure(e)
            }
        }
        
        return Failure(MaxAttemptsExceeded)
    }
    
    private fun backoff(attempt: Int): Duration {
        return Duration.seconds(min(2.0.pow(attempt), 30.0).toLong())
    }
}
```

## 4.3 重试关键约束

```
✅ client_msg_id 不变
✅ 本地状态先持久化
✅ 重启后从 DB 恢复未完成消息
❌ 不要重新生成 ID
❌ 不要直接覆盖本地数据
```

## 4.4 失败消息处理

```kotlin
// App 启动时检查未完成消息
fun resumePendingMessages() {
    val pending = db.query("SELECT * FROM local_message WHERE status = ?", SENDING)
    for (msg in pending) {
        if (currentTimeMillis() - msg.sendTime > 5.minutes) {
            // 超过 5 分钟还在 sending，标记失败
            db.update(msg.copy(status = FAILED))
        } else {
            // 还在窗口内，继续重试
            sendQueue.send(msg)
        }
    }
}
```

## 4.5 用户手动重发

```kotlin
fun retryMessage(localId: Long) {
    val msg = db.get(localId)
    if (msg.status != FAILED) return
    
    db.update(msg.copy(
        status = SENDING,
        sendTime = currentTimeMillis()
    ))
    sendQueue.send(msg)
}
```

---

# 5. 消息接收与去重

## 5.1 消息来源

```
1. 实时通道 (在线推送)
2. 离线拉取 (上线同步)
3. 历史漫游 (滚动加载)
4. 多端同步 (其他端发的)
```

## 5.2 统一接收处理

```kotlin
fun onMessageReceived(msg: ReceivedMessage) {
    // 1. 去重检查
    if (isDuplicate(msg)) {
        return
    }
    
    // 2. 自己发的消息：合并到 local_message
    if (msg.senderId == myUserId) {
        mergeOutgoingMessage(msg)
        return
    }
    
    // 3. 别人发的：插入新消息
    insertIncomingMessage(msg)
    
    // 4. 更新会话
    updateConversation(msg)
    
    // 5. 通知 UI
    listeners.onMessageInserted(msg)
}

fun isDuplicate(msg: ReceivedMessage): Boolean {
    // 优先按 server_msg_id 去重
    if (db.exists("server_msg_id = ?", msg.serverMsgId)) {
        return true
    }
    // 兜底按 (conv, seq) 去重
    if (db.exists("conv_id = ? AND visible_seq = ?", msg.convId, msg.visibleSeq)) {
        return true
    }
    return false
}
```

## 5.3 自己发消息的合并

关键场景：手机发了一条消息，PC 端通过同步收到 → 不能再插一条新的。

```kotlin
fun mergeOutgoingMessage(msg: ReceivedMessage) {
    // 按 client_msg_id 找本地
    val local = db.findByClientMsgId(msg.clientMsgId)
    
    if (local != null) {
        // 合并：补充 server_msg_id 和 seq
        db.update(local.copy(
            serverMsgId = msg.serverMsgId,
            visibleSeq = msg.visibleSeq,
            status = SUCCESS
        ))
    } else {
        // 本地没有（其他端发的）：插入新记录
        db.insert(msg.toLocal())
    }
}
```

## 5.4 顺序保证

```kotlin
fun insertIncomingMessage(msg: ReceivedMessage) {
    // 1. 检查 seq 连续性
    val maxLocalSeq = db.queryMaxSeq(msg.convId)
    
    if (msg.visibleSeq > maxLocalSeq + 1) {
        // 有空洞，触发同步
        syncManager.syncRange(
            convId = msg.convId,
            from = maxLocalSeq + 1,
            to = msg.visibleSeq - 1
        )
    }
    
    // 2. 插入
    db.insert(msg.toLocal())
}
```

注意：实际上 IM 应该容忍 seq 空洞（撤回、不可见消息），不必每次都补拉。  
判断条件：本地已知 max_visible_seq vs 服务端 max_visible_seq。

---

# 6. 推拉协同同步

## 6.1 同步策略

```
推（轻量通知）→ 拉（精确数据）
```

服务端实时通道只发 `latest_seq`，客户端按需拉取。

## 6.2 同步触发时机

```
1. 应用启动
2. 网络连接建立
3. 收到 SYNC_NOTIFY 通知
4. 用户切换会话
5. 后台返回前台
6. 主动刷新
```

## 6.3 同步流程

```kotlin
class SyncManager {
    suspend fun fullSync() {
        // 1. 拉变更会话列表
        val changedConvs = api.getChangedConversations(
            sinceVersion = lastSyncVersion
        )
        
        // 2. 按会话拉增量
        val tasks = changedConvs.map { conv ->
            async {
                syncConversation(conv.convId, conv.maxSeq)
            }
        }
        
        // 3. 并行同步（限制并发）
        tasks.chunked(5).forEach { it.awaitAll() }
        
        // 4. 更新同步版本
        lastSyncVersion = response.version
    }
    
    suspend fun syncConversation(convId: Long, serverMaxSeq: Long) {
        val localMaxSeq = db.queryMaxSeq(convId)
        if (localMaxSeq >= serverMaxSeq) return
        
        var fromSeq = localMaxSeq + 1
        while (fromSeq <= serverMaxSeq) {
            val resp = api.pullMessages(
                convId = convId,
                sinceSeq = fromSeq - 1,
                limit = 200
            )
            
            db.batchInsert(resp.messages)
            
            if (!resp.hasMore) break
            fromSeq = resp.messages.last().visibleSeq + 1
        }
    }
}
```

## 6.4 历史漫游

```kotlin
class HistoryLoader {
    suspend fun loadOlder(convId: Long, beforeSeq: Long, limit: Int = 30): List<Message> {
        // 1. 先查本地
        val local = db.queryOlder(convId, beforeSeq, limit)
        if (local.size >= limit) return local
        
        // 2. 不够，从服务端拉
        val needed = limit - local.size
        val oldest = local.lastOrNull()?.visibleSeq ?: beforeSeq
        
        val remote = api.pullMessages(
            convId = convId,
            beforeSeq = oldest,
            limit = needed
        )
        
        // 3. 落库 + 返回
        db.batchInsert(remote.messages)
        return local + remote.messages
    }
}
```

## 6.5 同步性能优化

```
- 只同步活跃会话（最近 30 天有消息）
- 大群只拉最近 100 条，历史按需
- 多会话并发，限制并发数 5
- 失败重试，不阻塞其他
```

---

# 7. 离线消息处理

## 7.1 推送唤醒

```
1. App 后台/退出
2. 服务端检测离线
3. 调 APNs/FCM 推送轻量通知
4. 客户端被唤醒（iOS 静默推送 / Android 服务）
5. 启动同步
6. 必要时显示通知
```

## 7.2 后台同步限制

### iOS
```
- 静默推送有频率限制
- BGAppRefreshTask 短任务（30s）
- VoIP 推送（受限）
```

### Android
```
- FCM 高优先级推送
- WorkManager 后台任务
- 厂商通道（华为/小米等）
```

## 7.3 通知展示

```kotlin
fun showNotification(msg: ReceivedMessage) {
    // 不打扰检查
    if (conv.isMuted && !msg.isMention) return
    
    // 内容预览（隐私设置）
    val preview = if (settings.showPreview) {
        msg.content.preview()
    } else {
        "你收到一条新消息"
    }
    
    notificationManager.notify(
        title = msg.conversationName,
        body = preview,
        category = if (msg.isMention) "high" else "normal"
    )
}
```

## 7.4 通知聚合

```
1 个会话多条消息: "X 等 N 人发来 M 条新消息"
利用 thread_id (Android) / threadIdentifier (iOS)
```

---

# 8. 多端协同

## 8.1 已读同步

```kotlin
// 节流上报
class ReadReporter {
    private var pendingReports = mutableMapOf<Long, Long>()  // conv → maxRead
    private val flushScope = CoroutineScope(Dispatchers.IO)
    
    fun reportRead(convId: Long, readSeq: Long) {
        synchronized(pendingReports) {
            pendingReports[convId] = max(pendingReports[convId] ?: 0, readSeq)
        }
        scheduleFlush()
    }
    
    private fun scheduleFlush() {
        flushScope.launch {
            delay(2000)  // 2s 节流
            val toReport = synchronized(pendingReports) {
                val copy = pendingReports.toMap()
                pendingReports.clear()
                copy
            }
            if (toReport.isNotEmpty()) {
                api.batchReportRead(toReport)
            }
        }
    }
}

// 接收其他端的已读同步
fun onReadSync(convId: Long, readSeq: Long) {
    val local = db.queryConv(convId)
    if (readSeq > local.readVisibleSeq) {
        db.updateConv(convId, readVisibleSeq = readSeq)
        listeners.onUnreadChanged(convId)
    }
}
```

## 8.2 草稿同步（可选）

```
可选功能，非核心
通过自定义事件同步
```

## 8.3 设备切换

```
登录新设备:
  1. 服务端推送踢人消息（同设备类型）
  2. 老设备收到 → 显示提示 → 关闭连接
  3. 新设备开始全量同步
```

---

# 9. 网络质量自适应

## 9.1 网络监测

```kotlin
class NetworkMonitor {
    fun startMonitoring() {
        // Android: ConnectivityManager
        // iOS: NWPathMonitor
        
        onNetworkChanged { type ->
            when (type) {
                WIFI -> {
                    heartbeatInterval = 60.seconds
                    syncMode = AGGRESSIVE
                }
                CELLULAR -> {
                    heartbeatInterval = 45.seconds
                    syncMode = CONSERVATIVE
                }
                NONE -> {
                    pauseSync()
                }
            }
        }
    }
}
```

## 9.2 弱网识别

```
基于 RTT 和丢包率：
  P50 RTT < 200ms: 优秀
  200~500ms:       一般
  500~1000ms:      较差
  > 1000ms 或丢包 > 5%: 弱网

弱网策略:
  - 减小 batch size
  - 增加超时
  - 优先小消息
  - 暂停文件上传
```

## 9.3 网络切换

```kotlin
fun onNetworkChanged() {
    // QUIC 连接迁移会自动处理
    // WS 连接需要重连
    
    if (protocol == WS) {
        connection.reconnect()
    } else if (protocol == QUIC) {
        // QUIC 自动迁移，无需重连
        // 但要重新订阅 / 触发同步
        sync.scheduleResync()
    }
}
```

---

# 10. 错误处理

## 10.1 错误分类

| 类型 | 示例 | 处理 |
|---|---|---|
| 网络错误 | 超时/断开 | 自动重试 |
| 协议错误 | 解析失败 | 断开重连 |
| 业务错误 | 限流/封禁 | 提示用户 |
| 鉴权错误 | token 过期 | 重新登录 |
| 服务错误 | 5xx | 退避重试 |

## 10.2 错误码

```
0       成功
1xxx    客户端错误
2xxx    协议错误
3xxx    鉴权错误
4xxx    业务错误（限流、封禁、权限）
5xxx    服务错误
9xxx    未知错误
```

## 10.3 重试策略

```kotlin
fun shouldRetry(error: Throwable): Boolean {
    return when (error) {
        is NetworkTimeoutException -> true
        is NetworkUnavailableException -> true
        is ServerErrorException -> error.code in 500..599
        is RateLimitedException -> error.retryAfter > 0
        is BlockedException -> false
        is AuthenticationException -> false
        else -> false
    }
}
```

## 10.4 用户提示

```
不要把所有错误都弹给用户
- 网络问题：状态栏小提示
- 限流：消息上小图标 + tip
- 封禁：明确提示
- 服务故障：toast
```

---

# 11. 安全与隐私

## 11.1 传输加密

```
- TLS 1.3
- 证书 pinning（防中间人）
- 应用层加密（敏感字段）
```

## 11.2 本地存储加密

```
- SQLCipher 整库加密
- 密钥用平台 KeyStore 保护
- 不把密钥写文件
```

## 11.3 敏感信息

```
不要 log:
  - 消息正文
  - token / 密钥
  - 用户隐私字段

允许 log:
  - 元数据 (msg_id, seq, time)
  - 错误码
  - 性能指标
```

## 11.4 数据清除

```
退出登录:
  - 清空 token
  - 关闭连接
  - 可选：清空本地消息

卸载:
  - 系统自动清理
```

---

# 12. SDK 接口设计

## 12.1 初始化

```kotlin
val config = IMConfig.Builder()
    .appId("xxx")
    .endpoint("im.example.com")
    .deviceId(uniqueDeviceId)
    .logLevel(LogLevel.INFO)
    .build()

IMClient.init(config)
```

## 12.2 登录

```kotlin
suspend fun login(token: String): LoginResult

IMClient.login(token).onSuccess { user ->
    // 登录成功
}.onFailure { error ->
    // 处理错误
}
```

## 12.3 会话操作

```kotlin
val convs = IMClient.conversation
    .listAll()              // 所有会话
    .listRecent(20)         // 最近 20 个
    .get(convId)            // 单个会话

IMClient.conversation
    .markAsRead(convId)
    .pin(convId)
    .mute(convId, until)
    .clear(convId)
    .delete(convId)
```

## 12.4 消息操作

```kotlin
// 发送
val msg = MessageBuilder()
    .text("hello @张三")
    .mention(zhangsanId)
    .build()

IMClient.message.send(convId, msg)

// 历史
val messages = IMClient.message.loadHistory(convId, beforeSeq = 1000, limit = 30)

// 撤回
IMClient.message.recall(serverMsgId)

// 编辑
IMClient.message.edit(serverMsgId, newContent)
```

## 12.5 监听器

```kotlin
IMClient.addMessageListener { msg ->
    // 新消息
}

IMClient.addConnectionListener { state ->
    // 连接状态变化
}

IMClient.addConvUpdateListener { conv ->
    // 会话更新（未读、最后消息等）
}
```

## 12.6 错误回调

```kotlin
IMClient.onError { error ->
    when (error) {
        is AuthExpired -> reLogin()
        is RateLimited -> showTip(error.retryAfter)
        else -> log(error)
    }
}
```

---

**文档结束** | Version 1.0