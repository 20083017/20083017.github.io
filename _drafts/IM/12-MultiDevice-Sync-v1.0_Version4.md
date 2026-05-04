# 多设备消息同步详细方案 v1.0

> 适用：用户多端登录（手机/PC/Web）的消息同步  
> 目标：跨端一致、增量高效、断点续传、不丢不重

---

## 目录

1. 设计目标
2. 同步模型
3. 增量同步协议
4. 冲突解决
5. 断点续传
6. 多端状态同步
7. 历史消息漫游
8. 性能优化

---

# 1. 设计目标

## 1.1 用户期望

```
1. 任何设备发的消息,所有设备都能看到
2. 任何设备的已读,其他设备同步
3. 切换设备无感
4. 离线一段时间上线后能自动补齐
5. 不会重复或丢失
```

## 1.2 技术目标

```
- 同步延迟 P99 < 1s
- 支持 100 万会话/用户
- 离线 30 天可恢复
- 弱网友好
```

---

# 2. 同步模型

## 2.1 三大同步对象

| 对象 | 说明 | 同步方式 |
|---|---|---|
| 消息 | 收到/发出的消息 | 增量 seq |
| 已读游标 | read_seq | 推 + 拉 |
| 会话状态 | 置顶/免打扰/草稿 | 版本号 |

## 2.2 服务端权威

```
原则: 服务端是 source of truth
客户端:
  - 本地缓存
  - 本地修改先尝试,后向服务端校对
  - 冲突时服务端为准
```

## 2.3 同步触发时机

```
1. 应用启动
2. 长连接建立
3. 收到 SYNC_NOTIFY (服务端推送)
4. 后台 → 前台
5. 网络从断到通
6. 用户主动下拉刷新
```

---

# 3. 增量同步协议

## 3.1 同步标识

每个用户维护一个全局**同步 token**：

```
sync_token = (server_version, last_sync_time)

server_version: 单调递增的版本号
                每次会话变更/消息变更 +1
```

## 3.2 同步流程

```
Client                      Server
  │                           │
  │ ─── sync(token) ─────────→│
  │                           │
  │ ←── changes + new_token ──│
  │                           │
  │ apply changes             │
  │ save new_token            │
```

## 3.3 同步接口设计

### 请求

```protobuf
message SyncRequest {
  int64 user_id = 1;
  string device_id = 2;
  
  // 同步 token (上次返回的)
  string sync_token = 3;
  
  // 限制
  int32 max_conv = 4;        // 最多返回多少会话
  int32 max_msg_per_conv = 5; // 单会话最多消息
}
```

### 响应

```protobuf
message SyncResponse {
  string new_sync_token = 1;
  
  // 变更的会话列表（含元数据）
  repeated ConvChange conv_changes = 2;
  
  // 新消息（按会话归并）
  repeated ConvMessages messages = 3;
  
  // 新游标
  repeated CursorUpdate cursors = 4;
  
  // 还有更多变更
  bool has_more = 5;
}

message ConvChange {
  int64 conv_id = 1;
  int32 change_type = 2;  // 1:added 2:updated 3:removed
  ConvMeta meta = 3;
  int64 max_visible_seq = 4;
}
```

## 3.4 服务端实现

```python
def sync(user_id, sync_token):
    parsed = parse_token(sync_token)
    last_version = parsed.server_version
    
    # 1. 查变更的会话
    changed_convs = query_changed_convs(user_id, last_version)
    
    # 2. 查每个会话的新消息（按 read_seq ~ max_seq）
    messages = []
    for conv in changed_convs:
        cursor = get_cursor(user_id, conv.conv_id)
        msgs = query_messages_for_user(
            conv_id=conv.conv_id,
            user_id=user_id,
            from_seq=cursor.last_synced_seq + 1,
            to_seq=conv.max_visible_seq,
            limit=50
        )
        messages.append(ConvMessages(conv.conv_id, msgs))
    
    # 3. 查游标变更
    cursors = query_cursor_changes(user_id, last_version)
    
    # 4. 构造新 token
    new_version = current_max_version_for_user(user_id)
    new_token = build_token(new_version)
    
    return SyncResponse(
        new_sync_token=new_token,
        conv_changes=changed_convs,
        messages=messages,
        cursors=cursors,
        has_more=(len(messages) >= MAX_BATCH)
    )
```

## 3.5 客户端实现

```kotlin
class SyncManager {
    suspend fun fullSync() {
        val token = prefs.getString("sync_token", "")
        
        var hasMore = true
        while (hasMore) {
            val resp = api.sync(SyncRequest(
                userId = currentUser.id,
                deviceId = deviceId,
                syncToken = token,
                maxConv = 100,
                maxMsgPerConv = 50
            ))
            
            applySync(resp)
            
            prefs.put("sync_token", resp.newSyncToken)
            hasMore = resp.hasMore
        }
    }
    
    private fun applySync(resp: SyncResponse) {
        db.transaction {
            // 应用会话变更
            for (change in resp.convChanges) {
                when (change.changeType) {
                    ADDED -> insertConv(change.meta)
                    UPDATED -> updateConv(change.meta)
                    REMOVED -> deleteConv(change.convId)
                }
            }
            
            // 应用消息
            for (convMsgs in resp.messages) {
                for (msg in convMsgs.msgs) {
                    upsertMessage(msg)  // 按 server_msg_id 幂等
                }
            }
            
            // 应用游标
            for (cursor in resp.cursors) {
                upsertCursor(cursor)  // 取 GREATEST
            }
        }
        
        // 通知 UI
        notifyChanges()
    }
}
```

## 3.6 单会话增量

主同步只拉**变更的会话列表**，单个会话进入时再拉详细消息：

```
GET /messages?conv_id=C&since_seq=1000&limit=30
```

避免一次拉太多。

---

# 4. 冲突解决

## 4.1 可能的冲突

| 场景 | 冲突 | 解决 |
|---|---|---|
| A 端读到 seq 100, B 端读到 seq 50 | read_seq 不同 | GREATEST |
| A 端置顶, B 端取消置顶 | 设置冲突 | LWW (last write wins) |
| A 端编辑消息, B 端撤回 | 操作冲突 | 服务端按时间排序 |
| A 端发消息但本地未同步 | 本地有 server 没 | 重发 (clientMsgId 幂等) |

## 4.2 单调推进

```
read_seq:    GREATEST (取大)
max_seq:     GREATEST (取大)
sync_token:  按 version 比较,取大
```

## 4.3 LWW（最后写入获胜）

```
会话设置 (置顶/免打扰):
  每次更新带 timestamp
  服务端: WHERE updated_at > current_updated_at
  避免旧请求覆盖新请求
```

## 4.4 操作冲突

```
A 端撤回, B 端编辑同一条消息:
  服务端按到达顺序处理
  后到达的可能失败 (前置条件不满足)
  例: 已撤回的不能编辑
```

## 4.5 客户端时钟问题

```
不依赖客户端时间
所有 timestamp 用服务端
客户端时间仅作显示参考
```

---

# 5. 断点续传

## 5.1 离线场景

```
用户离线 30 天 → 重新上线
本地 sync_token 很老
服务端要返回 30 天变更?
```

## 5.2 分页同步

```
首次同步:
  返回最多 100 个变更会话
  has_more=true
  
循环拉取:
  直到 has_more=false

每页用新 token,失败可重试
```

## 5.3 完整重置

```
sync_token 失效（如太久未同步）:
  服务端返回 INVALID_TOKEN
  客户端清空本地，全量同步
```

```python
def sync(user_id, sync_token):
    if not is_valid_token(sync_token):
        raise InvalidToken
    
    if token_age > 90 days:
        raise TokenTooOld  # 客户端走全量
```

## 5.4 全量同步

```
客户端无 token / token 失效:
  1. 拉会话列表 (最近 N 个)
  2. 每个会话拉最近 M 条消息
  3. 拉所有游标
  4. 设置新 token
```

## 5.5 进度持久化

```
每页同步成功 → 立即保存 token
中断后下次启动从最新 token 继续
```

---

# 6. 多端状态同步

## 6.1 已读同步

```
A 手机读到 seq=1050:
  POST /report_read {conv: C, seq: 1050}
  
服务端:
  GREATEST 更新 cursor
  Kafka: read.event
  
B PC 收到:
  实时通道推送 read sync
  本地更新 cursor
```

详见前文未读计数设计。

## 6.2 设备登录通知

```
A 手机登录:
  服务端记录设备
  推送给其他端: "新设备登录"
  
其他端 UI 显示
```

## 6.3 草稿同步（可选）

```
A 手机输入草稿:
  本地保存
  节流 5s 上报服务端
  
B PC 拉到草稿,显示"在 A 端正在输入..."
```

非关键功能，按需。

## 6.4 设备列表

```
GET /devices
返回:
  当前所有登录设备
  各自的最后活跃时间
  当前设备标记
  
用户可: 远程登出某设备
```

---

# 7. 历史消息漫游

## 7.1 需求

```
新设备登录 → 看到历史消息 (云端拉)
切换设备 → 历史一致
本地清空缓存 → 可重新拉
```

## 7.2 漫游协议

```
GET /history?conv=C&before_seq=1000&limit=30

返回:
  [seq=970~999] (倒序)
  has_more: true/false
```

## 7.3 漫游 vs 同步

```
同步 (sync): 拉新增/变更
漫游 (roam): 拉历史

漫游不影响 sync_token
漫游消息按 seq 范围查
```

## 7.4 漫游限制

```
- 默认保留 30 天 / 1 年（业务定）
- 单次 limit ≤ 200
- 频率限制
```

## 7.5 实现

```python
def get_history(user_id, conv_id, before_seq, limit):
    # 权限校验
    if not is_member(user_id, conv_id):
        raise NoPermission
    
    # 用户加群前的消息不可见
    cursor = get_cursor(user_id, conv_id)
    
    msgs = db.query("""
        SELECT * FROM im_message 
        WHERE conv_id = ? 
          AND visible_seq < ? 
          AND visible_seq >= ?
          AND status = 0
        ORDER BY visible_seq DESC 
        LIMIT ?
    """, conv_id, before_seq, cursor.joined_at_seq, limit)
    
    return msgs
```

---

# 8. 性能优化

## 8.1 同步频率

```
长连接在线:
  服务端有变更主动推 SYNC_NOTIFY
  客户端响应式拉

无长连接:
  定时拉 (每 30s)
  应用启动拉
```

## 8.2 推送压缩

```
SYNC_NOTIFY 只通知"有变更"
不带详细内容
客户端按需拉
```

## 8.3 批量优化

```
sync 接口返回:
  - 多会话合并
  - 单会话多消息合并
  - gzip 压缩
```

## 8.4 服务端缓存

```
近期变更走 Redis (latest_changes:{userId})
冷数据走 DB
```

## 8.5 客户端去重

```
按 server_msg_id 唯一性插入 (UNIQUE KEY)
重复推送/同步不会插入两次
```

## 8.6 弱网处理

```
- 减小 batch
- 增加超时
- 失败重试
- 部分成功保留 token
```

---

**文档结束** | Version 1.0