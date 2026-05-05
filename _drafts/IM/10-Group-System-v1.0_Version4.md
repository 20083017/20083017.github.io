# 群组系统详细设计 v1.0

> 适用：千人群、万人群、十万人群、百万订阅频道  
> 目标：成员管理高效、消息分发可控、权限严格

---

## 目录

1. 群组分级
2. 数据模型
3. 成员管理
4. 权限模型
5. 消息分发策略
6. 大群优化
7. 频道与超大群
8. 群操作流程

---

# 1. 群组分级

## 1.1 分级定义

| 等级 | 成员数 | 称呼 | 分发模式 | 典型场景 |
|---|---|---|---|---|
| L1 | ≤ 200 | 普通群 | 写扩散 | 朋友群 |
| L2 | 201~2000 | 中群 | 写扩散到活跃 | 部门群 |
| L3 | 2001~10000 | 大群 | 混合 | 兴趣群 |
| L4 | 10001~100000 | 超大群 | 读扩散 | 社区群 |
| L5 | > 100000 | 频道 | 订阅 + 推送 | 公告频道 |

## 1.2 分级策略影响

```
L1: 全员写 inbox + 实时推送
L2: 活跃成员写 inbox + 实时推送
L3: 不写 inbox,客户端拉取 + 实时推送活跃
L4: 完全读扩散,不主动推
L5: 订阅模型,主播推送给订阅者
```

---

# 2. 数据模型

## 2.1 群表

```sql
CREATE TABLE im_group (
  group_id        BIGINT PRIMARY KEY,
  app_id          INT NOT NULL,
  name            VARCHAR(64) NOT NULL,
  avatar          VARCHAR(256),
  description     TEXT,
  
  group_type      TINYINT NOT NULL,      -- 1:normal 2:channel 3:bot
  group_level     TINYINT NOT NULL,      -- L1~L5
  member_count    INT DEFAULT 0,
  max_member      INT NOT NULL,
  
  owner_id        BIGINT NOT NULL,
  
  -- 设置
  join_mode       TINYINT,               -- 0:open 1:approval 2:invite
  msg_mode        TINYINT,               -- 0:all_can_send 1:only_admin
  
  -- 状态
  status          TINYINT DEFAULT 0,     -- 0:normal 1:disbanded 2:frozen
  
  created_at      BIGINT NOT NULL,
  updated_at      BIGINT NOT NULL
);
```

## 2.2 群成员表

```sql
CREATE TABLE group_member (
  group_id        BIGINT NOT NULL,
  user_id         BIGINT NOT NULL,
  
  role            TINYINT DEFAULT 0,     -- 0:member 1:admin 2:owner
  nickname        VARCHAR(64),           -- 群昵称
  
  joined_seq      BIGINT,                -- 加入时的 visible_seq
  joined_at       BIGINT NOT NULL,
  
  -- 状态
  status          TINYINT DEFAULT 0,     -- 0:active 1:muted 2:left
  mute_until      BIGINT,                -- 禁言到期
  
  -- 用户视角
  is_pinned       TINYINT DEFAULT 0,
  is_muted        TINYINT DEFAULT 0,     -- 用户对群的免打扰
  
  PRIMARY KEY (group_id, user_id),
  KEY idx_user (user_id, status)
) PARTITION BY HASH(group_id) PARTITIONS 64;
```

## 2.3 用户加入的群（反向索引）

```sql
CREATE TABLE user_groups (
  user_id     BIGINT NOT NULL,
  group_id    BIGINT NOT NULL,
  joined_at   BIGINT NOT NULL,
  PRIMARY KEY (user_id, group_id)
) PARTITION BY HASH(user_id) PARTITIONS 256;
```

## 2.4 Redis 缓存

```
group:meta:{group_id}        Hash    群基本信息
group:members:{group_id}     Set     成员列表（小群）
group:admins:{group_id}      Set     管理员
group:active:{group_id}      ZSet    活跃成员（按最后活跃时间）
user:groups:{user_id}        Set     用户加入的群
```

---

# 3. 成员管理

## 3.1 加入群组

### 主动加入（开放群）

```python
def join_group(user_id, group_id):
    # 1. 校验
    group = get_group(group_id)
    if group.status != NORMAL:
        raise GroupNotAvailable
    if group.member_count >= group.max_member:
        raise GroupFull
    if group.join_mode == APPROVAL:
        return submit_join_request(user_id, group_id)
    
    # 2. 风控
    if risk.is_blocked(user_id):
        raise Blocked
    
    # 3. 加入
    with db.transaction():
        max_seq = get_max_visible_seq(group_id)
        db.insert("group_member", {
            "group_id": group_id,
            "user_id": user_id,
            "role": MEMBER,
            "joined_seq": max_seq,
            "joined_at": now()
        })
        db.insert("user_groups", {...})
        db.update("im_group SET member_count = member_count + 1")
    
    # 4. 发系统消息
    send_system_message(group_id, f"{user_name} 加入了群聊")
    
    # 5. 刷缓存
    redis.sadd(f"group:members:{group_id}", user_id)
    redis.sadd(f"user:groups:{user_id}", group_id)
```

### 被邀请加入

```python
def invite_to_group(inviter_id, group_id, invitee_ids):
    # 1. 权限校验
    if not can_invite(inviter_id, group_id):
        raise NoPermission
    
    # 2. 限流
    rate_limit_check(f"invite:{inviter_id}", 100, "1h")
    
    # 3. 批量邀请
    for invitee_id in invitee_ids:
        if group.join_mode == INVITE_REQUIRES_APPROVAL:
            send_invite_card(invitee_id, group_id)
        else:
            join_group_directly(invitee_id, group_id)
```

### 批量加入（万人群批量导入）

```python
def batch_join(group_id, user_ids):
    # 分批,避免单次事务过大
    batch_size = 100
    for batch in chunk(user_ids, batch_size):
        with db.transaction():
            db.batch_insert("group_member", batch_records)
            db.batch_insert("user_groups", batch_records)
            db.update(f"im_group SET member_count = member_count + {len(batch)}")
        
        # 系统消息合并(不要每人一条)
    
    # 1 条合并的系统消息
    send_system_message(
        group_id, 
        f"{inviter} 邀请 {len(user_ids)} 人加入了群聊"
    )
```

## 3.2 退出群组

```python
def leave_group(user_id, group_id):
    with db.transaction():
        db.delete("group_member WHERE group_id=? AND user_id=?")
        db.delete("user_groups WHERE ...")
        db.update("im_group SET member_count = member_count - 1")
    
    redis.srem(f"group:members:{group_id}", user_id)
    redis.srem(f"user:groups:{user_id}", group_id)
    
    # 系统消息
    send_system_message(group_id, f"{user_name} 退出了群聊")
```

## 3.3 踢出成员

```python
def kick_member(operator_id, group_id, target_id):
    # 权限: 仅 owner/admin 可踢
    if not is_admin(operator_id, group_id):
        raise NoPermission
    
    # admin 不能踢 admin (除非 owner)
    if is_admin(target_id, group_id) and not is_owner(operator_id, group_id):
        raise NoPermission
    
    leave_group(target_id, group_id)
    send_system_message(group_id, f"{target} 被 {operator} 移出群聊")
```

## 3.4 成员列表查询

### 小群（< 1000）

```python
def get_members_small(group_id):
    return redis.smembers(f"group:members:{group_id}")
```

### 大群

```python
def get_members_large(group_id, page=0, size=50):
    # Redis ZSet 按角色 + 加入时间分页
    return redis.zrange(
        f"group:members_zset:{group_id}",
        page * size,
        (page + 1) * size - 1
    )
```

### 万人群

```
不返回完整列表，只返回:
  - 总人数
  - 管理员列表
  - 当前用户附近的成员
  - 搜索接口（按昵称）
```

## 3.5 成员搜索

```python
def search_members(group_id, keyword):
    # 大群用 ES
    return es.search(
        index="group_member_index",
        body={
            "query": {
                "bool": {
                    "filter": [{"term": {"group_id": group_id}}],
                    "must": [{"match": {"nickname": keyword}}]
                }
            }
        }
    )
```

---

# 4. 权限模型

## 4.1 角色

| 角色 | 权限 |
|---|---|
| **Owner** (群主) | 全部权限，唯一 |
| **Admin** (管理员) | 除 解散群、转让、修改群主外 |
| **Member** (普通成员) | 发消息、退群 |

## 4.2 权限矩阵

| 操作 | Member | Admin | Owner |
|---|:---:|:---:|:---:|
| 发消息 | ✅ | ✅ | ✅ |
| 邀请新人 | ✅ * | ✅ | ✅ |
| 踢人 | ❌ | ✅ ** | ✅ |
| @所有人 | ❌ | ✅ | ✅ |
| 修改群名 | ❌ | ✅ | ✅ |
| 修改群头像 | ❌ | ✅ | ✅ |
| 设置公告 | ❌ | ✅ | ✅ |
| 禁言成员 | ❌ | ✅ ** | ✅ |
| 全员禁言 | ❌ | ✅ | ✅ |
| 任命管理员 | ❌ | ❌ | ✅ |
| 转让群主 | ❌ | ❌ | ✅ |
| 解散群 | ❌ | ❌ | ✅ |

```
* 视群设置而定
** 不能操作其他 Admin
```

## 4.3 权限校验

```python
class PermissionChecker:
    def can_send_message(self, user_id, group_id):
        member = get_member(group_id, user_id)
        if not member or member.status == LEFT:
            return False
        if member.status == MUTED:
            if member.mute_until > now():
                return False
        if group.msg_mode == ONLY_ADMIN and member.role == MEMBER:
            return False
        if group.all_muted and member.role == MEMBER:
            return False
        return True
    
    def can_kick(self, operator_id, group_id, target_id):
        op = get_member(group_id, operator_id)
        target = get_member(group_id, target_id)
        
        if op.role == MEMBER:
            return False
        if target.role == OWNER:
            return False
        if target.role == ADMIN and op.role != OWNER:
            return False
        return True
```

## 4.4 禁言

### 单人禁言

```python
def mute_member(operator_id, group_id, target_id, duration_seconds):
    if not can_mute(operator_id, group_id, target_id):
        raise NoPermission
    
    mute_until = now() + duration_seconds * 1000
    
    db.update("group_member SET status=1, mute_until=? WHERE ...")
    redis.zadd(f"group:muted:{group_id}", mute_until, target_id)
    
    send_system_message(...)
```

### 全员禁言

```python
def mute_all(operator_id, group_id, enabled):
    if not is_admin(operator_id, group_id):
        raise NoPermission
    
    db.update("im_group SET all_muted=? WHERE group_id=?", enabled)
    redis.set(f"group:all_muted:{group_id}", enabled)
```

---

# 5. 消息分发策略

## 5.1 分发模式总览

```
小群 (L1):     全员写扩散 + 实时推送
中群 (L2):     活跃写扩散 + 实时推送活跃 + 离线只 push
大群 (L3):     不写扩散 + 客户端拉 + 实时推送活跃
超大群 (L4):    完全读扩散 + 仅在线成员通知
频道 (L5):     订阅模型,主播推送
```

## 5.2 写扩散（L1 小群）

```
A 发消息到 100 人小群:
  1. 消息入库 (im_message)
  2. Kafka: msg.fanout
  3. InboxWriter 给 100 个成员各写一条 inbox
  4. Deliver 给在线成员实时推送
  5. Push 给离线成员发 push
```

## 5.3 写扩散到活跃成员（L2 中群）

```
A 发消息到 1000 人中群:
  1. 消息入库
  2. 活跃成员 (近 7 天访问) 写 inbox
     - 通常活跃成员 < 30%
  3. 不活跃成员: 不写 inbox
     - 上线后主动拉取
  4. 在线成员实时推
```

```python
def fanout_medium_group(group_id, msg):
    active = redis.zrangebyscore(
        f"group:active:{group_id}",
        now() - 7*86400*1000,
        now()
    )
    
    for batch in chunk(active, 100):
        kafka.send("msg.inbox", batch_payload)
    
    # 在线推送
    online = filter_online(active)
    for user in online:
        push_to_gateway(user, msg)
```

## 5.4 读扩散（L4 超大群）

```
A 发消息到 5 万人大群:
  1. 消息入库 (im_message)
  2. 更新 group_meta.max_visible_seq
  3. 不写 inbox
  4. Kafka: notify_active_members (只通知)
  5. 在线成员: Deliver 实时推送
  6. 离线成员: 上线后通过 max_seq 对比发现新消息
  7. 客户端按 group_id + sinceSeq 拉取消息
```

## 5.5 客户端拉取协议

```
客户端打开群聊页面:
  GET /messages?group_id=G&since_seq=1000&limit=30
  
返回:
  {
    "messages": [...],
    "max_seq": 1050,
    "has_more": true
  }
```

## 5.6 推送优化

### 大群推送限速

```
万人群消息频率上限: 5 条/秒
超过 → 后续消息排队/丢弃
```

### 大群 push 抑制

```
普通群: 给离线成员发 push
万人群: 默认免打扰,不发 push（除非 @）
百万人群/频道: 完全不发 push（订阅成功才发）
```

### push 合并

```
1 秒窗口内同群多条消息:
  合并为 1 个 push: "X 条新消息"
```

---

# 6. 大群优化

## 6.1 成员列表分页

```
不返回完整列表,只:
  - 总人数
  - 管理员
  - 最近活跃 100 人
  - 搜索接口
```

## 6.2 在线成员统计

```
不要 GET 全量在线成员
:
  GET 在线 admin
  GET 在线总数(基于在线状态服务统计)
```

## 6.3 @所有人 不展开

```
@all 标记 mention_all=true
不写 mention_index
查询时 UNION
```

## 6.4 成员加群 seq 锚定

```
新成员只能看加群之后的消息
SELECT * FROM message WHERE group_id=? AND visible_seq > joined_seq
```

## 6.5 系统消息合并

```
1000 人在 1 分钟内加群:
  不要发 1000 条 "X 加入了群聊"
  合并为: "1000 人加入了群聊"
```

## 6.6 群成员变更同步

```
小群: 实时全量推送
大群: 通知变更类型,客户端按需拉
```

---

# 7. 频道与超大群

## 7.1 频道（L5）

```
特点:
  - 百万订阅者
  - 仅频道主/管理员可发
  - 单向传播
  - 严格防刷
```

## 7.2 订阅模型

```sql
CREATE TABLE channel_subscriber (
  channel_id  BIGINT,
  user_id     BIGINT,
  subscribed_at BIGINT,
  notification_level TINYINT,  -- 0:silent 1:default 2:high
  PRIMARY KEY (channel_id, user_id)
) PARTITION BY HASH(user_id);
```

## 7.3 频道消息分发

```
两阶段 fanout:

Stage 1 (轻量):
  写入消息 → Kafka: channel.broadcast

Stage 2 (分页 fanout):
  消费 channel.broadcast
  分页拉订阅者列表 (1000/页)
  每页生成 N 条 push 事件 (加盐分区)
  逐页推到下一级 topic (msg.push.channel)
```

```python
def broadcast_channel_msg(channel_id, msg):
    cursor = 0
    while True:
        subs, cursor = scan_subscribers(channel_id, cursor, limit=1000)
        if not subs:
            break
        
        for batch in chunk(subs, 100):
            kafka.send("msg.push.channel", {
                "channel_id": channel_id,
                "msg_id": msg.id,
                "users": batch
            })
        
        # 限速,避免一条消息把集群打爆
        time.sleep(0.1)
```

## 7.4 频道推送策略

```
高优 (notification_level=2): 实时推
默认 (notification_level=1): 折叠合并
静音 (notification_level=0): 不推
```

---

# 8. 群操作流程

## 8.1 创建群

```
1. 校验创建权限/限流
2. 分配 group_id (雪花)
3. INSERT im_group
4. INSERT group_member (创建者 = owner)
5. 邀请初始成员（异步）
6. 发系统消息 "群聊创建"
7. 返回 group_id
```

## 8.2 转让群主

```
仅 Owner 可操作:
  1. 校验目标在群内
  2. 事务:
     UPDATE group_member SET role=ADMIN WHERE owner
     UPDATE group_member SET role=OWNER WHERE target
     UPDATE im_group SET owner_id = target
  3. 系统消息: "群主已转让给 X"
```

## 8.3 解散群

```
仅 Owner 可操作:
  1. 软删除: UPDATE im_group SET status=1
  2. 异步清理 member, inbox
  3. 推送通知: "群已解散"
  4. 群消息保留 N 天供取证
```

---

**文档结束** | Version 1.0