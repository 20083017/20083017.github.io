# IM 客户端 SDK 设计文档 v1.0

> 适用平台: iOS / Android / Web / Electron / 小程序  
> 设计目标: 协议无感、本地一致、弱网鲁棒、跨端体验一致

---

## 目录

1. [SDK 架构](#1-sdk-架构)
2. [协议处理层](#2-协议处理层)
3. [连接管理](#3-连接管理)
4. [本地存储](#4-本地存储)
5. [消息收发](#5-消息收发)
6. [推拉协同](#6-推拉协同)
7. [消息合并与去重](#7-消息合并与去重)
8. [离线与重连](#8-离线与重连)
9. [性能优化](#9-性能优化)
10. [API 设计](#10-api-设计)

---

# 1. SDK 架构

## 1.1 分层

```
┌─────────────────────────────────────────┐
│  应用层 API                              │
│  send / on_message / fetch_history ...   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  业务层                                  │
│  Conversation / Message / Sync / Read    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  本地存储                                │
│  SQLite / IndexedDB / Realm              │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  传输层                                  │
│  Protocol Codec / WebSocket / QUIC       │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  网络层                                  │
│  Connection / Reconnect / Heartbeat      │
└─────────────────────────────────────────┘
```

## 1.2 核心模块

| 模块 | 职责 |
|---|---|
| `ConnectionManager` | 长连接管理、协议选择、重连 |
| `ProtocolCodec` | 编解码、加解密、压缩 |
| `MessageManager` | 消息收发、合并、去重 |
| `SyncManager` | 增量同步、补拉、对账 |
| `ConversationManager` | 会话管理、未读、置顶 |
| `LocalStore` | SQLite 持久化 |
| `EventBus` | 事件分发到 UI |
| `LogManager` | 日志收集与上报 |
| `ConfigManager` | 配置同步、灰度 |

## 1.3 设计原则

- **本地优先**：UI 显示永远基于本地 DB
- **异步上报**：UI 操作立即响应，网络异步
- **乐观更新**：发送即显示"sending"，回执后更新状态
- **去重为王**：每个去重点都不能省
- **协议无关**：业务层不感知 WS/QUIC

---

# 2. 协议处理层

## 2.1 协议帧编解码

参考主规范 §3.2 的协议格式。SDK 实现：

```typescript
class ProtocolCodec {
    encode(cmd: number, body: Uint8Array, opts?: EncodeOpts): Uint8Array {
        const seqId = this.nextSeqId();
        let flags = 0;
        let bodyToSend = body;
        
        if (opts?.compress && body.length > 4096) {
            bodyToSend = zstdCompress(body);
            flags |= FLAG_COMPRESSED;
        }
        
        const buf = new ArrayBuffer(18 + bodyToSend.length);
        const view = new DataView(buf);
        view.setUint8(0, 0x4D);
        view.setUint8(1, PROTO_VERSION);
        view.setUint16(2, cmd);
        view.setUint16(4, flags);
        view.setBigUint64(6, BigInt(seqId));
        view.setUint32(14, bodyToSend.length);
        new Uint8Array(buf, 18).set(bodyToSend);
        return new Uint8Array(buf);
    }
    
    decode(data: Uint8Array): Frame {
        const view = new DataView(data.buffer);
        if (view.getUint8(0) !== 0x4D) throw new Error("bad magic");
        
        const version = view.getUint8(1);
        const cmd = view.getUint16(2);
        const flags = view.getUint16(4);
        const seqId = view.getBigUint64(6);
        const length = view.getUint32(14);
        
        let body = data.subarray(18, 18 + length);
        if (flags & FLAG_COMPRESSED) {
            body = zstdDecompress(body);
        }
        
        return { version, cmd, flags, seqId, body };
    }
}
```

## 2.2 请求-响应匹配

```typescript
class RequestManager {
    private pending = new Map<bigint, PendingRequest>();
    
    async request<T>(cmd: number, body: Uint8Array, timeout = 10000): Promise<T> {
        const seqId = this.codec.nextSeqId();
        const frame = this.codec.encode(cmd, body);
        
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(seqId);
                reject(new TimeoutError());
            }, timeout);
            
            this.pending.set(seqId, { resolve, reject, timer });
            this.connection.send(frame);
        });
    }
    
    onResponse(frame: Frame) {
        const req = this.pending.get(frame.seqId);
        if (!req) return;
        clearTimeout(req.timer);
        this.pending.delete(frame.seqId);
        req.resolve(this.parseResponse(frame));
    }
}
```

## 2.3 服务器推送处理

```typescript
class PushHandler {
    onPush(frame: Frame) {
        switch (frame.cmd) {
            case CMD_MSG_PUSH:
                this.messageManager.onMessage(decodeMsg(frame.body));
                break;
            case CMD_SYNC_NOTIFY:
                this.syncManager.onSyncNotify(decode(frame.body));
                break;
            case CMD_READ_NOTIFY:
                this.conversationManager.onReadUpdate(...);
                break;
            case CMD_KICK:
                this.connectionManager.kicked(...);
                break;
        }
    }
}
```

## 2.4 协议升级与兼容

```typescript
// 客户端在 LOGIN 时上报支持的版本
{
    "client_version": "3.5.0",
    "proto_version": 2,
    "features": ["quic", "compression", "batch_send"]
}

// 服务端返回当前支持的功能集
{
    "proto_version": 2,
    "enabled_features": [...]
}
```

客户端根据 `enabled_features` 决定走哪些功能。

---

# 3. 连接管理

## 3.1 协议选择策略

```typescript
class ConnectionStrategy {
    async connect(): Promise<Connection> {
        // 1. 先查上次成功的协议
        const lastSuccess = this.storage.getLastProtocol();
        
        // 2. 并行尝试 QUIC + WSS (Happy Eyeballs)
        const promises = [
            this.tryQUIC(),
            sleep(200).then(() => this.tryWSS()),  // WSS 延后 200ms
        ];
        
        // 3. 谁先成功用谁
        const conn = await Promise.race(promises);
        
        // 4. 缓存成功协议
        this.storage.setLastProtocol(conn.protocol);
        return conn;
    }
}
```

## 3.2 重连策略

```typescript
class Reconnector {
    private attempt = 0;
    private maxBackoff = 30000;
    
    async reconnect() {
        while (!this.connected) {
            const delay = this.computeBackoff();
            await sleep(delay);
            
            try {
                await this.connect();
                this.attempt = 0;
                this.eventBus.emit('reconnected');
            } catch (e) {
                this.attempt++;
            }
        }
    }
    
    private computeBackoff(): number {
        // 指数退避 + 抖动
        const base = Math.min(
            this.maxBackoff,
            1000 * Math.pow(2, this.attempt)
        );
        return base / 2 + Math.random() * base / 2;
    }
}
```

## 3.3 心跳

```typescript
class HeartbeatManager {
    private interval = 30000;
    private timeoutTimer: any;
    
    start() {
        this.timer = setInterval(() => this.ping(), this.interval);
    }
    
    private async ping() {
        try {
            const start = Date.now();
            await this.codec.request(CMD_HEARTBEAT, encode({
                client_ts: start,
                sequence: this.seq++
            }));
            const rtt = Date.now() - start;
            
            // 自适应：RTT 高时降低间隔
            this.adjustInterval(rtt);
        } catch (e) {
            this.connection.close('heartbeat_failed');
        }
    }
    
    private adjustInterval(rtt: number) {
        if (rtt < 100) {
            this.interval = 60000;  // 网络好，降频
        } else if (rtt > 500) {
            this.interval = 15000;  // 弱网，加频
        }
    }
}
```

## 3.4 连接状态机

```
DISCONNECTED → CONNECTING → AUTHENTICATING → CONNECTED
       ▲                                          │
       │                                          ▼
       └────────────────────────────────── DISCONNECTING
                                                  │
                                                  ▼
                                              KICKED
```

每次状态变化通�� EventBus 通知 UI：
```typescript
eventBus.emit('connection_state', { from, to });
```

## 3.5 多端互踢

```typescript
onPush(frame) {
    if (frame.cmd === CMD_KICK) {
        const reason = decode(frame.body).reason;
        if (reason === 'logged_in_elsewhere') {
            this.eventBus.emit('kicked_off', reason);
            this.cleanup();
            // 不自动重连，等用户手动
        }
    }
}
```

---

# 4. 本地存储

## 4.1 数据库表设计

### conversations 表
```sql
CREATE TABLE conversations (
  conv_id           INTEGER PRIMARY KEY,
  conv_type         INTEGER,              -- 1:single 2:group 3:channel
  name              TEXT,
  avatar            TEXT,
  last_msg_id       INTEGER,
  last_msg_preview  TEXT,
  last_msg_time     INTEGER,
  
  max_visible_seq   INTEGER DEFAULT 0,    -- 已知最大 seq
  read_visible_seq  INTEGER DEFAULT 0,
  read_mention_seq  INTEGER DEFAULT 0,
  
  unread_count      INTEGER DEFAULT 0,
  mention_unread    INTEGER DEFAULT 0,
  
  is_muted          INTEGER DEFAULT 0,
  is_pinned         INTEGER DEFAULT 0,
  
  draft             TEXT,
  updated_at        INTEGER
);

CREATE INDEX idx_conv_updated ON conversations(updated_at DESC);
```

### messages 表
```sql
CREATE TABLE messages (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  conv_id         INTEGER NOT NULL,
  visible_seq     INTEGER,                -- 服务端可见 seq
  global_seq      INTEGER,                -- 全局 seq
  server_msg_id   INTEGER,                -- 服务端 ID
  client_msg_id   TEXT,                   -- 客户端 ID
  
  sender_id       INTEGER,
  msg_type        INTEGER,
  content         TEXT,                   -- JSON
  
  status          INTEGER DEFAULT 0,      -- 0:sending 1:success 2:failed 3:recalled
  send_time       INTEGER,
  recv_time       INTEGER,
  
  has_mention     INTEGER DEFAULT 0,
  is_mention_me   INTEGER DEFAULT 0,
  
  reply_to_id     INTEGER,
  
  UNIQUE(conv_id, visible_seq),
  UNIQUE(server_msg_id)
);

CREATE INDEX idx_msg_conv_seq ON messages(conv_id, visible_seq DESC);
CREATE INDEX idx_msg_client_id ON messages(client_msg_id);
CREATE INDEX idx_msg_status ON messages(status) WHERE status = 0;  -- 找未发送
```

### sync_state 表
```sql
CREATE TABLE sync_state (
  key             TEXT PRIMARY KEY,
  value           TEXT
);

-- 例:
-- key='global_event_seq', value='12345'
-- key='last_sync_time', value='1710000000'
```

### local_outbox 表（本地待发消息）
```sql
CREATE TABLE local_outbox (
  client_msg_id   TEXT PRIMARY KEY,
  conv_id         INTEGER,
  payload         TEXT,         -- 完整请求 body
  retry_count     INTEGER DEFAULT 0,
  next_retry_at   INTEGER,
  created_at      INTEGER
);
```

## 4.2 存储引擎

| 平台 | 引擎 |
|---|---|
| iOS | SQLite + GRDB |
| Android | SQLite + Room |
| Web | IndexedDB（自封装） |
| Electron | better-sqlite3 |
| 小程序 | 平台 KV / IndexedDB |

## 4.3 加密存储

```typescript
// 敏感字段（消息内容）AES 加密
const encryptedContent = aesEncrypt(content, deviceKey);
db.insert('messages', { content: encryptedContent });

// 设备密钥本地 Keychain / Keystore 存储
```

## 4.4 容量管理

```typescript
class StorageManager {
    async cleanup() {
        const dbSize = await this.getDBSize();
        if (dbSize > MAX_DB_SIZE) {
            // 清理 30 天前的非置顶会话消息
            await db.exec(`
                DELETE FROM messages 
                WHERE recv_time < ? 
                AND conv_id NOT IN (SELECT conv_id FROM conversations WHERE is_pinned=1)
            `, [Date.now() - 30 * 86400 * 1000]);
            
            // VACUUM 回收空间
            await db.exec('VACUUM');
        }
    }
}
```

---

# 5. 消息收发

## 5.1 发送消息

### 完整流程

```typescript
async sendMessage(convId: number, content: MessageContent): Promise<Message> {
    // 1. 生成 clientMsgId
    const clientMsgId = generateClientMsgId();
    
    // 2. 构造消息对象
    const msg: Message = {
        clientMsgId,
        convId,
        senderId: this.userId,
        content,
        status: 'sending',
        sendTime: Date.now(),
    };
    
    // 3. 立即写本地 DB（乐观更新）
    await this.store.insertMessage(msg);
    
    // 4. 通知 UI
    this.eventBus.emit('message_added', msg);
    
    // 5. 写本地 outbox（防进程退出丢消息）
    await this.store.insertOutbox(msg);
    
    // 6. 异步发送
    this.sendInternal(msg);
    
    return msg;
}

private async sendInternal(msg: Message) {
    try {
        const resp = await this.codec.request(CMD_SEND_MSG, encode({
            client_msg_id: msg.clientMsgId,
            conv_id: msg.convId,
            content: msg.content,
        }), 15000);
        
        // 更新本地状态
        await this.store.updateMessage(msg.clientMsgId, {
            serverMsgId: resp.server_msg_id,
            visibleSeq: resp.visible_seq,
            status: 'success',
            recvTime: resp.server_time,
        });
        
        await this.store.deleteOutbox(msg.clientMsgId);
        this.eventBus.emit('message_updated', msg);
        
    } catch (e) {
        if (e instanceof RateLimitError) {
            await this.store.updateMessage(msg.clientMsgId, {
                status: 'failed',
                failReason: 'rate_limited'
            });
        } else if (e instanceof TimeoutError || e instanceof NetworkError) {
            // 超时不立即标失败，等重连后从 outbox 重发
            this.scheduleRetry(msg);
        } else {
            await this.store.updateMessage(msg.clientMsgId, {
                status: 'failed',
                failReason: e.message
            });
        }
    }
}
```

### clientMsgId 生成

```typescript
function generateClientMsgId(): string {
    // 设备ID + 本地自增 + 时间戳
    const localSeq = ++this.localSeq;
    return `${this.deviceId}-${Date.now()}-${localSeq}`;
}

// localSeq 持久化到 IndexedDB / SQLite
// 进程重启后从 max + 1000 继续（防冲突）
```

### 重试机制

```typescript
class OutboxRetrier {
    async retryAll() {
        if (!this.connected) return;
        
        const pending = await this.store.getOutbox(now);
        for (const item of pending) {
            try {
                await this.sendInternal(item);
            } catch (e) {
                item.retryCount++;
                if (item.retryCount > 5) {
                    // 标失败，停止重试
                    await this.store.updateMessage(item.clientMsgId, {
                        status: 'failed'
                    });
                    await this.store.deleteOutbox(item.clientMsgId);
                } else {
                    // 指数退避
                    const delay = Math.min(60000, 1000 * Math.pow(2, item.retryCount));
                    item.nextRetryAt = now + delay;
                    await this.store.updateOutbox(item);
                }
            }
        }
    }
}

// 重连成功 → retryAll
// 每分钟扫描一次 outbox
```

## 5.2 接收消息

### 推送处理

```typescript
async onMessagePush(push: MsgPush) {
    // 1. 去重
    if (await this.store.messageExists(push.serverMsgId)) {
        return;  // 已经有了
    }
    
    // 2. 检查是否是自己发的回流（多端同步）
    if (push.senderId === this.userId && push.clientMsgId) {
        const existing = await this.store.findByClientMsgId(push.clientMsgId);
        if (existing) {
            // 合并：把本地 sending 消息更新为 success
            await this.store.updateMessage(push.clientMsgId, {
                serverMsgId: push.serverMsgId,
                visibleSeq: push.visibleSeq,
                status: 'success',
            });
            return;
        }
    }
    
    // 3. 检查 seq 连续性
    const conv = await this.store.getConversation(push.convId);
    const expectedSeq = conv.maxVisibleSeq + 1;
    
    if (push.visibleSeq > expectedSeq) {
        // 有空洞，触发补拉
        this.syncManager.fetchRange(
            push.convId, 
            conv.maxVisibleSeq, 
            push.visibleSeq
        );
    }
    
    // 4. 入库
    await this.store.insertMessage({
        ...push,
        status: 'success',
        recvTime: Date.now(),
    });
    
    // 5. 更新会话
    await this.store.updateConversation(push.convId, {
        maxVisibleSeq: Math.max(conv.maxVisibleSeq, push.visibleSeq),
        lastMsg: this.makePreview(push),
        lastMsgTime: push.sendTime,
        unreadCount: this.computeUnread(conv, push),
    });
    
    // 6. 通知 UI
    this.eventBus.emit('message_received', push);
    
    // 7. @ 处理
    if (this.isMentionMe(push)) {
        this.eventBus.emit('mentioned', push);
    }
}
```

## 5.3 消息状态显示

| 状态 | UI |
|---|---|
| `sending` | 灰色转圈 |
| `success` | 已送达 ✓ |
| `read` | 已读 ✓✓ |
| `failed` | 红色感叹号 + 重发按钮 |
| `recalled` | "X 撤回了一条消息" |

---

# 6. 推拉协同

## 6.1 协同模型

```
[实时通道]                        [拉取通道]
    │                                  │
    ▼                                  ▼
推送通知 (轻量, conv+seq)          按需拉取
    │                                  │
    └────────┬─────────────────────────┘
             ▼
       本地按 seq 去重合并
```

## 6.2 拉取策略

### 启动时同步
```typescript
async onLogin() {
    // 1. 拉取活跃会话变更列表
    const lastEventSeq = await this.store.getSyncState('global_event_seq');
    const events = await this.codec.request(CMD_SYNC_PULL, encode({
        since_event_seq: lastEventSeq
    }));
    
    // 2. 对比每个会话的 maxSeq
    for (const ev of events.conversations) {
        const local = await this.store.getConversation(ev.convId);
        if (!local || ev.maxVisibleSeq > local.maxVisibleSeq) {
            // 拉取该会话增量
            await this.fetchConvIncremental(ev.convId, local?.maxVisibleSeq || 0);
        }
    }
    
    // 3. 更新游标
    await this.store.setSyncState('global_event_seq', events.maxEventSeq);
}
```

### 进入会话时检查
```typescript
async openConversation(convId: number) {
    // 立即从本地加载
    const messages = await this.store.getRecentMessages(convId, 50);
    this.eventBus.emit('conversation_opened', { convId, messages });
    
    // 后台对账
    const local = await this.store.getConversation(convId);
    const server = await this.codec.request(CMD_GET_CONV_META, encode({
        conv_id: convId
    }));
    
    if (server.maxVisibleSeq > local.maxVisibleSeq) {
        await this.fetchConvIncremental(convId, local.maxVisibleSeq);
    }
}
```

### 增量拉取
```typescript
async fetchConvIncremental(convId: number, sinceSeq: number, limit = 200) {
    while (true) {
        const resp = await this.codec.request(CMD_PULL_MSG, encode({
            conv_id: convId,
            since_seq: sinceSeq,
            limit
        }));
        
        for (const msg of resp.messages) {
            await this.processIncomingMessage(msg);
        }
        
        if (!resp.hasMore || resp.messages.length === 0) break;
        sinceSeq = resp.messages[resp.messages.length - 1].visibleSeq;
    }
}
```

### 历史漫游
```typescript
async loadHistory(convId: number, beforeSeq: number, limit = 30) {
    // 先查本地
    const local = await this.store.getMessagesBefore(convId, beforeSeq, limit);
    if (local.length >= limit) return local;
    
    // 不够则查云端
    const remote = await this.codec.request(CMD_HISTORY, encode({
        conv_id: convId,
        before_seq: local.length > 0 
            ? local[local.length - 1].visibleSeq 
            : beforeSeq,
        limit: limit - local.length
    }));
    
    for (const msg of remote.messages) {
        await this.store.insertMessage(msg);
    }
    
    return [...local, ...remote.messages];
}
```

## 6.3 推送通知 vs 拉取的边界

| 场景 | 用什么 |
|---|---|
| 在线收新消息 | 推送（实时） |
| 推送丢失检测 | 心跳时对比 maxSeq，差则拉 |
| 启动同步 | 拉取（推不可靠） |
| 历史漫游 | 拉取 |
| 进入会话校对 | 拉取 |
| 多端同步 | 推送 + 拉取双保险 |

---

# 7. 消息合并与去重

## 7.1 去重维度

```typescript
// 优先级
const DEDUP_KEYS = [
    'serverMsgId',           // 服务端唯一 ID
    'convId+visibleSeq',     // 会话内 seq
    'clientMsgId',           // 自己发的消息
];
```

## 7.2 自己发消息的合并

```
本地状态:
  [clientMsgId=X, status=sending]
  
服务端 ack 回来:
  按 clientMsgId=X 查找
  → 找到 → 更新为 success + 补充 serverMsgId/seq
  → 没找到 → 直接插入（可能本地清过）

多端同步推回来:
  按 clientMsgId=X 查找
  → 找到 → 跳过（已经有了）
  → 没找到 → 按 serverMsgId 查
    → 找到 → 跳过
    → 没找到 → 插入
```

## 7.3 通用插入逻辑

```typescript
async upsertMessage(msg: Message) {
    // 1. 按 clientMsgId 找（自己发的）
    if (msg.clientMsgId) {
        const existing = await db.query(
            'SELECT * FROM messages WHERE client_msg_id = ?',
            [msg.clientMsgId]
        );
        if (existing) {
            return this.mergeMessage(existing, msg);
        }
    }
    
    // 2. 按 serverMsgId 找
    const existing = await db.query(
        'SELECT * FROM messages WHERE server_msg_id = ?',
        [msg.serverMsgId]
    );
    if (existing) {
        return this.mergeMessage(existing, msg);
    }
    
    // 3. 都没有，插入
    await db.exec(
        'INSERT OR IGNORE INTO messages (...) VALUES (...)',
        [...]
    );
}

private mergeMessage(existing, incoming) {
    // 服务端字段以 incoming 为准（有更全数据）
    // 本地状态以 existing 为准（如已读状态）
    return {
        ...existing,
        serverMsgId: incoming.serverMsgId || existing.serverMsgId,
        visibleSeq: incoming.visibleSeq || existing.visibleSeq,
        status: existing.status === 'sending' ? 'success' : existing.status,
        // ...
    };
}
```

## 7.4 撤回处理

```typescript
async onRecall(serverMsgId: number, operatorId: number) {
    await db.exec(`
        UPDATE messages 
        SET status = 'recalled', 
            content = json_set(content, '$.recalled', json_object('by', ?))
        WHERE server_msg_id = ?
    `, [operatorId, serverMsgId]);
    
    this.eventBus.emit('message_recalled', { serverMsgId });
}
```

UI 渲染时 `status='recalled'` 显示为系统消息。

## 7.5 编辑处理

```typescript
async onEdit(serverMsgId: number, newContent: any, version: number) {
    const existing = await db.query(
        'SELECT version FROM messages WHERE server_msg_id = ?',
        [serverMsgId]
    );
    
    if (existing && existing.version >= version) {
        return;  // 已经是新版或更新版,忽略
    }
    
    await db.exec(`
        UPDATE messages 
        SET content = ?, version = ?, edited = 1
        WHERE server_msg_id = ?
    `, [newContent, version, serverMsgId]);
}
```

---

# 8. 离线与重连

## 8.1 离线检测

```typescript
class NetworkMonitor {
    constructor() {
        // iOS: NWPathMonitor
        // Android: ConnectivityManager
        // Web: navigator.onLine + visibilitychange
        
        this.subscribeNetworkChange((status) => {
            if (status.online) {
                this.connectionManager.reconnect();
            } else {
                this.connectionManager.markOffline();
            }
        });
    }
}
```

## 8.2 重连后同步

```typescript
async onReconnected() {
    // 1. 拉取离线期间的会话变更
    await this.syncManager.syncAll();
    
    // 2. 重发本地 outbox 里的消息
    await this.outboxRetrier.retryAll();
    
    // 3. 重新订阅状态
    await this.subscribeOnline();
    
    // 4. 通知 UI
    this.eventBus.emit('back_online');
}
```

## 8.3 弱网优化

```typescript
class WeakNetworkOptimizer {
    onWeakNetwork() {
        // 1. 心跳频率提高
        this.heartbeat.setInterval(15000);
        
        // 2. 启用消息批量发送
        this.batchSender.enable();
        
        // 3. 暂停非关键请求（如已读上报合并）
        this.readReporter.batchMode();
        
        // 4. UI 提示"网络较慢"
        this.eventBus.emit('weak_network');
    }
}
```

## 8.4 后台 / 前台切换

```typescript
class LifecycleManager {
    onAppBackground() {
        // 1. 心跳间隔加大
        this.heartbeat.setInterval(180000);
        
        // 2. 暂停非必要任��
        this.syncManager.pauseNonCritical();
    }
    
    onAppForeground() {
        // 1. 立即同步
        this.syncManager.syncAll();
        
        // 2. 心跳恢复
        this.heartbeat.setInterval(30000);
        
        // 3. 重连（如果断了）
        if (!this.connected) this.reconnect();
    }
}
```

---

# 9. 性能优化

## 9.1 批量操作

### 批量插入
```typescript
async batchInsertMessages(msgs: Message[]) {
    await db.transaction(async (tx) => {
        const stmt = tx.prepare('INSERT OR IGNORE INTO messages (...) VALUES (...)');
        for (const msg of msgs) {
            stmt.run(...);
        }
    });
}
```

### 已读批量上报
```typescript
class ReadReporter {
    private pending = new Map<number, number>(); // convId → maxSeq
    private timer: any;
    
    report(convId: number, seq: number) {
        const cur = this.pending.get(convId) || 0;
        this.pending.set(convId, Math.max(cur, seq));
        
        if (!this.timer) {
            this.timer = setTimeout(() => this.flush(), 2000);
        }
    }
    
    private async flush() {
        const reports = Array.from(this.pending.entries());
        this.pending.clear();
        this.timer = null;
        
        await this.codec.request(CMD_READ_REPORT, encode({
            items: reports.map(([convId, seq]) => ({ convId, seq }))
        }));
    }
}
```

## 9.2 UI 渲染优化

- 虚拟列表（VirtualList）
- 图片懒加载 + 占位
- 消息分页加载（每次 30 条）
- 滚动时不更新本地未读

## 9.3 内存管理

```typescript
class MessageCache {
    private cache = new LRUCache<number, Message[]>({ max: 50 });
    
    // 内存只缓存最近打开的 50 个会话的消息
    // 其他会话从 DB 按需加载
}
```

## 9.4 启动优化

```
1. 立即用本地数据渲染会话列表 (< 100ms)
2. UI 可交互后再启动同步
3. 同步分阶段：先头 20 个活跃会话，再全量
4. 大量历史消息懒加载
```

---

# 10. API 设计

## 10.1 核心 API

```typescript
class IMClient {
    // 连接
    async login(token: string): Promise<void>;
    async logout(): Promise<void>;
    
    // 消息
    async sendMessage(convId: number, content: any): Promise<Message>;
    async recallMessage(serverMsgId: number): Promise<void>;
    async editMessage(serverMsgId: number, newContent: any): Promise<void>;
    async resendMessage(clientMsgId: string): Promise<Message>;
    
    // 会话
    async getConversations(opts?: GetConvOpts): Promise<Conversation[]>;
    async openConversation(convId: number): Promise<void>;
    async closeConversation(convId: number): Promise<void>;
    async getMessages(convId: number, beforeSeq?: number, limit?: number): Promise<Message[]>;
    
    // 已读
    async markAsRead(convId: number, seq?: number): Promise<void>;
    async getUnreadCount(): Promise<{total: number, byConv: Map<number, number>}>;
    
    // 群组
    async createGroup(opts: CreateGroupOpts): Promise<Group>;
    async joinGroup(groupId: number): Promise<void>;
    async leaveGroup(groupId: number): Promise<void>;
    async getGroupMembers(groupId: number): Promise<Member[]>;
    
    // 文件
    async uploadFile(file: File, opts?: UploadOpts): Promise<FileInfo>;
    
    // 事件
    on(event: string, handler: Function): void;
    off(event: string, handler: Function): void;
}
```

## 10.2 事件清单

| 事件 | 时机 |
|---|---|
| `connection_state` | 连接状态变化 |
| `message_received` | 收到新消息 |
| `message_sent` | 自己消息发送成功 |
| `message_failed` | 发送失败 |
| `message_recalled` | 消息被撤回 |
| `message_edited` | 消息被编辑 |
| `mentioned` | 被 @ |
| `read_update` | 对方已读状态更新 |
| `conversation_updated` | 会话信息变更 |
| `unread_changed` | 未读数变化 |
| `group_member_changed` | 群成员变动 |
| `kicked_off` | 被多端踢下线 |
| `back_online` | 重连成功 |
| `weak_network` | 弱网检测 |

## 10.3 错误码

```typescript
enum ErrorCode {
    OK = 0,
    NETWORK_ERROR = 1001,
    TIMEOUT = 1002,
    AUTH_FAILED = 2001,
    TOKEN_EXPIRED = 2002,
    KICKED = 2003,
    RATE_LIMITED = 3001,
    BLOCKED = 3002,
    NOT_IN_GROUP = 4001,
    PERMISSION_DENIED = 4002,
    CONTENT_TOO_LONG = 5001,
    CONTENT_REJECTED = 5002,
}
```

---

# 文档维护

- 文档负责人：客户端架构组
- 评审周期：版本发布前
- 关联文档：协议规范、API 接口文档

*Version 1.0 | 最后更新：2026-05-04*