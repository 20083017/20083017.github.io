# 客户端 SDK 设计文档 v1.0

> IM 客户端 SDK - 协议处理 / 本地存储 / 消息合并 / 推拉协同  
> 关键词：长连接管理 / 离线缓存 / 多端同步 / 弱网优化

## 目录
1. [SDK 架构与职责](#1-sdk-架构与职责)
2. [模块设计](#2-模块设计)
3. [协议处理层](#3-协议处理层)
4. [连接管理](#4-连接管理)
5. [本地存储](#5-本地存储)
6. [消息收发与合并](#6-消息收发与合并)
7. [推拉协同同步](#7-推拉协同同步)
8. [离线与弱网](#8-离线与弱网)
9. [多端同步](#9-多端同步)
10. [API 设计](#10-api-设计)
11. [性能优化](#11-性能优化)
12. [跨平台实现](#12-跨平台实现)

---

# 1. SDK 架构与职责

## 1.1 SDK 在系统中的定位

```
┌──────────────────────────────────────┐
│         上层 App (UI)                 │
└──────────┬───────────────────────────┘
           │ SDK API
┌──────────▼───────────────────────────┐
│         IM SDK                        │
│  ┌────────┐ ┌────────┐ ┌──────────┐  │
│  │ 协议层  │ │ 业务层  │ │ 存储层    │  │
│  └────────┘ └────────┘ └──────────┘  │
│  ┌��───────┐ ┌────────┐ ┌──────────┐  │
│  │ 网络层  │ │ 同步层  │ │ 工具层    │  │
│  └────────┘ └────────┘ └──────────┘  │
└──────────┬───────────────────────────┘
           │ TLS/QUIC/WS
┌──────────▼───────────────────────────┐
│       IM Gateway                      │
└──────────────────────────────────────┘
```

## 1.2 核心职责

| 职责 | 说明 |
|---|---|
| 长连接管理 | 建连、保活、重连、迁移 |
| 协议编解码 | 二进制 frame ↔ Protobuf ↔ Model |
| 消息收发 | 上行发送 + 下行接收 |
| 本地存储 | SQLite/CoreData，离线消息缓存 |
| 同步引擎 | 推拉协同、增量同步、断点续传 |
| 多端一致 | clientMsgId 合并、seq 去重 |
| 推送整合 | APNs/FCM 唤醒 + 拉取 |
| 弱网优化 | 重试、退避、压缩、合并 |
| 安全 | 鉴权、E2E 加密（可选） |
| 可观测 | 埋点、日志、性能上报 |

## 1.3 SDK 不该做的

- ❌ 不做 UI（保持业务无关）
- ❌ 不存储敏感凭证（明文）
- ❌ 不做业务规则（如群权限）
- ❌ 不直接访问第三方服务

---

# 2. 模块设计

## 2.1 模块图

```
┌──────────────────────────────────────────────────┐
│                  Public API                       │
└──┬──────────┬──────────┬──────────┬──────────────┘
   │          │          │          │
┌──▼─────┐ ┌──▼──────┐ ┌─▼──────┐ ┌▼───────┐
│ Auth   │ │ Message │ │ Convo  │ │ Group  │  业务模块
│ Module │ │ Module  │ │ Module │ │ Module │
└──┬─────┘ └──┬──────┘ └─┬──────┘ └┬───────┘
   │          │          │         │
   └──────┬───┴──────────┴─────────┘
          │
┌─────────▼──────────────┐
│      Sync Engine       │  ← 推拉协同核心
└─────────┬──────────────┘
          │
┌─────────▼──────────────┐    ┌─────────────────┐
│  Connection Manager    │←───│ Network Detector│
└─────────┬──────────────┘    └─────────────────┘
          │
┌─���───────▼──────────────┐
│   Protocol Codec       │  ← Frame 编解码
└─────────┬──────────────┘
          │
┌─────────▼──────────────┐
│  Transport (WS/QUIC)   │
└────────────────────────┘

┌────────────────────────┐
│   Local Storage        │  ← SQLite/CoreData
└────────────────────────┘

┌────────────────────────┐
│   Utilities            │  日志/加密/压缩
└────────────────────────┘
```

## 2.2 线程模型

```
主线程 (UI):              不做 IO，只调用 SDK API
SDK 工作线程 (1 个):       事件循环、状态机
网络 IO 线程 (1-2 个):    Socket 读写
DB 线程 (1 个):           SQLite 写入串行化
回调线程池 (4 个):         上层回调

线程间通信: 消息队列 + 锁
```

## 2.3 状态机

```
[Idle] ──login()──→ [Connecting]
                          │
                    握手成功
                          ↓
                    [Authenticating]
                          │
                    认证成功
                          ↓
                    [Connected] ←──┐
                          │         │ 重连成功
                    心跳正常         │
                    断开/异常        │
                          ↓         │
                    [Reconnecting] ─┘
                          │
                    超过最大重试
                          ↓
                    [Disconnected]
                          │
                    logout() / 错误
                          ↓
                       [Idle]
```

---

# 3. 协议处理层

## 3.1 帧编解码

```kotlin
// Kotlin (Android)
class FrameCodec {
    companion object {
        const val MAGIC = 0x4D.toByte()
        const val HEADER_SIZE = 18
        const val MAX_FRAME = 1024 * 1024  // 1MB
    }
    
    fun encode(cmd: Int, seqId: Long, body: ByteArray, flags: Int = 0): ByteArray {
        val buf = ByteBuffer.allocate(HEADER_SIZE + body.size)
        buf.put(MAGIC)
        buf.put(VERSION.toByte())
        buf.putShort(cmd.toShort())
        buf.putShort(flags.toShort())
        buf.putLong(seqId)
        buf.putInt(body.size)
        buf.put(body)
        return buf.array()
    }
    
    fun decode(data: ByteArray): Frame {
        require(data.size >= HEADER_SIZE) { "frame too short" }
        require(data[0] == MAGIC) { "bad magic" }
        
        val buf = ByteBuffer.wrap(data)
        buf.position(1)
        val version = buf.get()
        val cmd = buf.short.toInt() and 0xFFFF
        val flags = buf.short.toInt() and 0xFFFF
        val seqId = buf.long
        val bodyLen = buf.int
        
        require(bodyLen <= MAX_FRAME) { "frame too large" }
        require(data.size >= HEADER_SIZE + bodyLen) { "incomplete" }
        
        var body = data.copyOfRange(HEADER_SIZE, HEADER_SIZE + bodyLen)
        
        // 解压
        if (flags and FLAG_COMPRESSED != 0) {
            body = ZstdDecompressor.decompress(body)
        }
        
        return Frame(version, cmd, flags, seqId, body)
    }
}
```

## 3.2 拆包/粘包处理

```kotlin
class FrameDecoder {
    private val buffer = ByteArrayOutputStream()
    
    @Synchronized
    fun feed(data: ByteArray): List<Frame> {
        buffer.write(data)
        val frames = mutableListOf<Frame>()
        
        while (true) {
            val bytes = buffer.toByteArray()
            if (bytes.size < HEADER_SIZE) break
            
            val bodyLen = ByteBuffer.wrap(bytes, 14, 4).int
            val totalLen = HEADER_SIZE + bodyLen
            
            if (bytes.size < totalLen) break  // 不够整帧
            
            frames.add(FrameCodec.decode(bytes.copyOf(totalLen)))
            
            // 重置 buffer 为剩余字节
            buffer.reset()
            if (bytes.size > totalLen) {
                buffer.write(bytes, totalLen, bytes.size - totalLen)
            }
        }
        
        return frames
    }
}
```

## 3.3 SeqId → Callback 映射

```kotlin
class RequestRouter {
    private val pending = ConcurrentHashMap<Long, PendingRequest>()
    private val seqGen = AtomicLong(1)
    
    fun send(cmd: Int, body: ByteArray, callback: (Result<ByteArray>) -> Unit, timeoutMs: Long = 10000) {
        val seqId = seqGen.incrementAndGet()
        val frame = FrameCodec.encode(cmd, seqId, body)
        
        pending[seqId] = PendingRequest(callback, System.currentTimeMillis() + timeoutMs)
        connection.write(frame)
    }
    
    fun handleResponse(frame: Frame) {
        val req = pending.remove(frame.seqId)
        req?.callback?.invoke(Result.success(frame.body))
    }
    
    // 定时清理超时
    fun checkTimeout() {
        val now = System.currentTimeMillis()
        pending.entries.removeIf { (_, req) ->
            if (now > req.expireAt) {
                req.callback(Result.failure(TimeoutException()))
                true
            } else false
        }
    }
}
```

## 3.4 推送消息处理（无 SeqId）

```kotlin
class PushHandler {
    fun handlePush(frame: Frame) {
        when (frame.cmd) {
            CMD_PUSH_MSG -> {
                val push = MsgPush.parseFrom(frame.body)
                messageManager.onMessageReceived(push)
                
                // 发送 ACK
                if (frame.flags and FLAG_NEED_ACK != 0) {
                    sendAck(push.serverMsgId)
                }
            }
            CMD_SYNC_NOTIFY -> {
                val notify = SyncNotify.parseFrom(frame.body)
                syncEngine.onNotify(notify.convId, notify.latestSeq)
            }
            CMD_KICK -> {
                val kick = KickReason.parseFrom(frame.body)
                onKicked(kick.reason)
            }
            // ...
        }
    }
}
```

---

# 4. 连接管理

## 4.1 接入流程

```kotlin
suspend fun connect(): Result<Unit> {
    // 1. 拉取接入入口
    val endpoints = dispatcher.getEndpoints(userId, deviceId)
    
    // 2. Happy Eyeballs: 并行尝试 QUIC 和 WSS
    val winner = parallelTry(endpoints) { endpoint ->
        when (endpoint.protocol) {
            "quic" -> connectQuic(endpoint)
            "wss" -> connectWss(endpoint)
        }
    }
    
    if (winner == null) return Result.failure(...)
    
    // 3. 鉴权登录
    val token = authManager.getToken()
    val loginResp = sendLogin(token)
    
    if (!loginResp.success) {
        winner.close()
        return Result.failure(...)
    }
    
    // 4. 状态切换
    state = State.CONNECTED
    
    // 5. 启动心跳
    startHeartbeat()
    
    // 6. 触发增量同步
    syncEngine.triggerFullSync()
    
    return Result.success(Unit)
}
```

## 4.2 协议探测与降级

```kotlin
// QUIC 优先 + WSS 兜底
class ConnectionStrategy {
    suspend fun connect(): Connection {
        // 1. 尝试缓存的最佳协议
        val cached = preferences.getString("preferred_protocol", "quic")
        
        try {
            return when (cached) {
                "quic" -> connectQuic()
                else -> connectWss()
            }
        } catch (e: ConnectException) {
            // 2. 降级
            return when (cached) {
                "quic" -> {
                    log.warn("QUIC failed, fallback to WSS")
                    preferences.putString("preferred_protocol", "wss")
                    connectWss()
                }
                else -> throw e
            }
        }
    }
}
```

## 4.3 重连策略

```kotlin
class ReconnectStrategy {
    private var attempt = 0
    private val maxBackoff = 60_000L
    
    fun nextDelay(): Long {
        val base = (1L shl attempt.coerceAtMost(6)) * 1000L  // 1, 2, 4, 8, 16, 32, 64
        val capped = base.coerceAtMost(maxBackoff)
        val jitter = (Math.random() * capped * 0.2).toLong()  // ±20%
        attempt++
        return capped + jitter
    }
    
    fun reset() {
        attempt = 0
    }
}

// 使用
suspend fun reconnectLoop() {
    while (state == State.RECONNECTING) {
        val delay = strategy.nextDelay()
        delay(delay)
        
        try {
            connect()
            strategy.reset()
            return
        } catch (e: Exception) {
            log.warn("reconnect failed", e)
        }
    }
}
```

## 4.4 网络变化触发

```kotlin
// Android
class NetworkMonitor(context: Context) {
    private val cm = context.getSystemService(ConnectivityManager::class.java)
    
    init {
        cm.registerDefaultNetworkCallback(object : NetworkCallback() {
            override fun onAvailable(network: Network) {
                onNetworkChanged()
            }
            override fun onLost(network: Network) {
                onNetworkChanged()
            }
        })
    }
    
    private fun onNetworkChanged() {
        // QUIC: 自动连接迁移，无需重连
        if (currentProtocol == "quic" && connection.isAlive()) {
            return
        }
        
        // WSS: 强制重连
        connectionManager.disconnect()
        connectionManager.scheduleReconnect(0)  // 立即
    }
}
```

## 4.5 心跳

```kotlin
class Heartbeat {
    private var interval = 30_000L
    
    fun start() {
        coroutineScope.launch {
            while (isActive) {
                delay(interval)
                
                try {
                    val rtt = measureTimeMillis {
                        sendHeartbeat()
                    }
                    
                    // 自适应调整
                    interval = when {
                        rtt < 100 -> 60_000L      // 网络好，降低频率
                        rtt < 500 -> 30_000L
                        else -> 15_000L           // 网络差，提高频率
                    }
                    
                    if (isAppInBackground()) {
                        interval = (interval * 2).coerceAtMost(180_000L)  // 后台延长
                    }
                } catch (e: Exception) {
                    onHeartbeatTimeout()
                }
            }
        }
    }
}
```

---

# 5. 本地存储

## 5.1 存储引擎选型

| 平台 | 推荐 |
|---|---|
| Android | SQLite (Room) / SQLDelight |
| iOS | SQLite (FMDB / GRDB) / CoreData |
| Web | IndexedDB |
| Desktop | SQLite |

**SQLite 是跨平台一致性最佳选择**。

## 5.2 数据库 Schema

```sql
-- 消息本地表
CREATE TABLE local_message (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  conv_id         INTEGER NOT NULL,
  client_msg_id   TEXT NOT NULL,
  server_msg_id   INTEGER,
  global_seq      INTEGER,
  visible_seq     INTEGER,
  sender_id       INTEGER,
  msg_type        INTEGER,
  content         BLOB,                  -- Protobuf 序列化
  send_status     INTEGER DEFAULT 0,     -- 0:sending 1:sent 2:failed 3:received
  read_status     INTEGER DEFAULT 0,     -- 0:unread 1:read
  send_time       INTEGER,
  receive_time    INTEGER,
  
  UNIQUE(conv_id, server_msg_id),
  UNIQUE(client_msg_id)
);

CREATE INDEX idx_conv_seq ON local_message(conv_id, visible_seq DESC);
CREATE INDEX idx_conv_time ON local_message(conv_id, send_time DESC);
CREATE INDEX idx_send_status ON local_message(send_status);

-- 会话本地表
CREATE TABLE local_conversation (
  conv_id              INTEGER PRIMARY KEY,
  conv_type            INTEGER,
  conv_name            TEXT,
  conv_avatar          TEXT,
  
  last_msg_id          INTEGER,
  last_msg_preview     TEXT,
  last_msg_time        INTEGER,
  
  max_visible_seq      INTEGER DEFAULT 0,    -- 本地最大已知 seq
  read_visible_seq     INTEGER DEFAULT 0,
  read_mention_seq     INTEGER DEFAULT 0,
  joined_at_seq        INTEGER DEFAULT 0,
  
  unread_count         INTEGER DEFAULT 0,    -- 缓存值，从 max-read 算
  unread_mention       INTEGER DEFAULT 0,
  
  is_muted             INTEGER DEFAULT 0,
  is_pinned            INTEGER DEFAULT 0,
  draft                TEXT,
  
  updated_at           INTEGER
);

CREATE INDEX idx_updated ON local_conversation(updated_at DESC);

-- 用户本地表
CREATE TABLE local_user (
  user_id     INTEGER PRIMARY KEY,
  nickname    TEXT,
  avatar      TEXT,
  remark      TEXT,
  updated_at  INTEGER
);

-- 群成员
CREATE TABLE local_group_member (
  group_id   INTEGER,
  user_id    INTEGER,
  role       INTEGER,
  PRIMARY KEY (group_id, user_id)
);

-- @我列表（缓存）
CREATE TABLE local_mention (
  server_msg_id  INTEGER PRIMARY KEY,
  conv_id        INTEGER,
  msg_seq        INTEGER,
  sender_id      INTEGER,
  preview        TEXT,
  is_read        INTEGER DEFAULT 0,
  created_at     INTEGER
);

CREATE INDEX idx_mention_unread ON local_mention(is_read, created_at DESC);

-- 同步进度
CREATE TABLE sync_state (
  key    TEXT PRIMARY KEY,
  value  TEXT
);
-- key: "last_sync_event_seq", "global_max_event"
```

## 5.3 数据访问层（DAO）

```kotlin
@Dao
interface MessageDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(msg: LocalMessage): Long
    
    @Update
    suspend fun update(msg: LocalMessage)
    
    @Query("SELECT * FROM local_message WHERE conv_id = :convId ORDER BY visible_seq DESC LIMIT :limit OFFSET :offset")
    suspend fun loadRecent(convId: Long, limit: Int, offset: Int): List<LocalMessage>
    
    @Query("SELECT * FROM local_message WHERE conv_id = :convId AND visible_seq > :sinceSeq ORDER BY visible_seq")
    suspend fun loadAfter(convId: Long, sinceSeq: Long): List<LocalMessage>
    
    @Query("SELECT MAX(visible_seq) FROM local_message WHERE conv_id = :convId")
    suspend fun getMaxSeq(convId: Long): Long?
    
    @Query("SELECT * FROM local_message WHERE client_msg_id = :clientMsgId LIMIT 1")
    suspend fun findByClientMsgId(clientMsgId: String): LocalMessage?
    
    @Query("SELECT * FROM local_message WHERE send_status = 0 AND send_time < :before")
    suspend fun findStuckSending(before: Long): List<LocalMessage>
}
```

## 5.4 写入串行化

SQLite 写入需要串行化（避免锁等待）：

```kotlin
class MessageRepository {
    private val writeChannel = Channel<WriteOp>(capacity = Channel.UNLIMITED)
    
    init {
        coroutineScope.launch(Dispatchers.IO) {
            for (op in writeChannel) {
                op.execute()
            }
        }
    }
    
    suspend fun insertMessage(msg: LocalMessage) {
        val op = InsertOp(msg)
        writeChannel.send(op)
        op.await()
    }
}
```

## 5.5 数据库迁移

```kotlin
// Room migration 例子
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(database: SupportSQLiteDatabase) {
        database.execSQL("ALTER TABLE local_message ADD COLUMN reply_to_id INTEGER")
    }
}
```

## 5.6 本地存储清理

```kotlin
class StorageCleaner {
    // 按时间清理：保留最近 90 天
    suspend fun cleanByTime() {
        val cutoff = System.currentTimeMillis() - 90L * 86400_000
        db.messageDao().deleteOlderThan(cutoff)
    }
    
    // 按容量清理：超过 500MB 清理最老的
    suspend fun cleanBySize(targetBytes: Long = 500 * 1024 * 1024) {
        val current = getDbSize()
        if (current < targetBytes) return
        
        // 按会话保留最近 N 条
        val convs = db.conversationDao().getAll()
        for (conv in convs) {
            db.messageDao().keepRecent(conv.convId, limit = 1000)
        }
    }
}
```

## 5.7 加密存储

```kotlin
// SQLCipher (Android)
val passphrase = SQLiteDatabase.getBytes("user-key".toCharArray())
val factory = SupportFactory(passphrase)
Room.databaseBuilder(...).openHelperFactory(factory).build()

// iOS: SQLite + SQLCipher 类似
```

---

# 6. 消息收发与合并

## 6.1 发送消息流程

```kotlin
suspend fun sendMessage(convId: Long, content: MessageContent): Result<Long> {
    // 1. 生成 clientMsgId
    val clientMsgId = generateClientMsgId()
    
    // 2. 本地落库 (sending 状态)
    val localMsg = LocalMessage(
        clientMsgId = clientMsgId,
        convId = convId,
        senderId = currentUserId,
        content = content.toByteArray(),
        sendStatus = SendStatus.SENDING,
        sendTime = System.currentTimeMillis()
    )
    val localId = db.messageDao().insert(localMsg)
    
    // 3. 立即触发 UI 刷新（乐观更新）
    onMessageInserted(localMsg)
    
    // 4. 发送到服务端
    try {
        val resp = withTimeout(10_000) {
            connectionManager.sendRequest<SendMsgReq, SendMsgResp>(
                CMD_SEND_MSG,
                SendMsgReq.newBuilder()
                    .setClientMsgId(clientMsgId)
                    .setConvId(convId)
                    .setContent(ByteString.copyFrom(content.toByteArray()))
                    .build()
            )
        }
        
        // 5. 更新本地状态
        db.messageDao().update(localMsg.copy(
            serverMsgId = resp.serverMsgId,
            visibleSeq = resp.visibleSeq,
            sendStatus = SendStatus.SENT
        ))
        
        // 6. 通知 UI
        onMessageSent(localMsg, resp)
        return Result.success(resp.serverMsgId)
        
    } catch (e: Exception) {
        // 7. 标记失败，进入重试队列
        db.messageDao().update(localMsg.copy(sendStatus = SendStatus.FAILED))
        retryQueue.enqueue(localMsg)
        return Result.failure(e)
    }
}
```

## 6.2 接收消息流程

```kotlin
fun onMessageReceived(push: MsgPush) {
    coroutineScope.launch(Dispatchers.IO) {
        // 1. 检查是否是自己发的（多端同步回流）
        if (push.senderId == currentUserId) {
            handleSelfMessageSync(push)
            return@launch
        }
        
        // 2. 去重检查
        val existing = db.messageDao().findByServerMsgId(push.serverMsgId)
        if (existing != null) {
            return@launch  // 已存在，跳过
        }
        
        // 3. 检查 seq 是否连续
        val convId = push.convId
        val localMaxSeq = db.messageDao().getMaxSeq(convId) ?: 0
        
        if (push.visibleSeq > localMaxSeq + 1) {
            // 有空洞，触发增量拉取
            syncEngine.triggerSync(convId, sinceSeq = localMaxSeq)
        }
        
        // 4. 插入本地
        val msg = LocalMessage(
            convId = push.convId,
            serverMsgId = push.serverMsgId,
            visibleSeq = push.visibleSeq,
            senderId = push.senderId,
            content = push.content.toByteArray(),
            sendStatus = SendStatus.RECEIVED,
            receiveTime = System.currentTimeMillis()
        )
        db.messageDao().insert(msg)
        
        // 5. 更新会话
        updateConversation(convId, msg)
        
        // 6. 处理 mention
        if (containsMention(push, currentUserId)) {
            handleMention(push)
        }
        
        // 7. 通知 UI
        onMessageInserted(msg)
        
        // 8. 发送 ACK（可选）
        sendAck(push.serverMsgId)
    }
}
```

## 6.3 自己发的消息回流（多端同步）

```kotlin
suspend fun handleSelfMessageSync(push: MsgPush) {
    // 通过 clientMsgId 查找本地是否有
    val clientMsgId = push.clientMsgId
    val existing = db.messageDao().findByClientMsgId(clientMsgId)
    
    if (existing != null) {
        // 本地已有，更新服务端 ID
        db.messageDao().update(existing.copy(
            serverMsgId = push.serverMsgId,
            visibleSeq = push.visibleSeq,
            sendStatus = SendStatus.SENT
        ))
    } else {
        // 本地没有（来自另一台设备），新建
        val msg = LocalMessage(
            clientMsgId = clientMsgId,
            convId = push.convId,
            serverMsgId = push.serverMsgId,
            visibleSeq = push.visibleSeq,
            senderId = currentUserId,
            content = push.content.toByteArray(),
            sendStatus = SendStatus.SENT
        )
        db.messageDao().insert(msg)
    }
}
```

## 6.4 重试队列

```kotlin
class RetryQueue {
    private val queue = ConcurrentLinkedQueue<LocalMessage>()
    
    init {
        coroutineScope.launch {
            while (isActive) {
                delay(5000)
                processQueue()
            }
        }
    }
    
    suspend fun processQueue() {
        if (!connectionManager.isConnected()) return
        
        val batch = mutableListOf<LocalMessage>()
        repeat(10) {
            queue.poll()?.let { batch.add(it) }
        }
        
        for (msg in batch) {
            try {
                resendMessage(msg)
            } catch (e: Exception) {
                if (msg.retryCount < 3) {
                    queue.offer(msg.copy(retryCount = msg.retryCount + 1))
                } else {
                    // 永久失败，标记
                    db.messageDao().update(msg.copy(sendStatus = SendStatus.FAILED_FINAL))
                }
            }
        }
    }
}
```

## 6.5 消息合并显示（UI 层逻辑示意）

```
连续消息合并:
  - 同一发送者 + 1 分钟内 + 连续 → 合并显示头像
  
时间分隔:
  - 与上一条相隔 > 5 分钟 → 显示时间分隔线
  - 跨天 → 显示日期
  
撤回显示:
  - "X 撤回了一条消息"

引用回复:
  - 显示原消息预览
```

---

# 7. 推拉协同同步

## 7.1 同步模型

```
推（Push）:    服务端实时通知"有新消息"（轻量，可丢）
拉（Pull）:    客户端按 seq 主动拉增量（可靠，最终一致）

最终一致性靠拉，实时性靠推
```

## 7.2 同步引擎核心逻辑

```kotlin
class SyncEngine {
    
    // 触发场景
    enum class Trigger {
        APP_LAUNCH,       // 启动
        APP_FOREGROUND,   // 切前台
        RECONNECTED,      // 重连成功
        PUSH_NOTIFY,      // 收到推送通知
        SEQ_GAP,          // 检测到 seq 空洞
        MANUAL,           // 用户下拉
    }
    
    suspend fun triggerSync(trigger: Trigger) {
        when (trigger) {
            APP_LAUNCH, RECONNECTED -> fullSync()
            APP_FOREGROUND -> incrementalSync()
            PUSH_NOTIFY -> incrementalSync()
            SEQ_GAP -> gapFill()
            MANUAL -> incrementalSync()
        }
    }
    
    // 1. 全量同步：拉变更会*
