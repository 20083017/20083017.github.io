# 在线状态服务详细设计 v1.0

> 模块名：Presence Service  
> 适用：千万在线、百万 QPS 状态查询、亚秒级感知  
> 目标：高吞吐、低延迟、跨地域、最终一致

---

## 目录

1. 设计目标与挑战
2. 状态模型
3. 总体架构
4. 数据分片
5. 心跳机制
6. TTL 与过期策略
7. 路由查询
8. 订阅模型（在线/离线通知）
9. 跨地域设计
10. 容错与一致性
11. 性能优化
12. 监控指标

---

# 1. 设计目标与挑战

## 1.1 业务诉求

| 场景 | 要求 |
|---|---|
| 投递消息 | 查"用户在哪个 Gateway" |
| 显示在线 | 查"好友是否在线" |
| 状态推送 | 好友上下线实时通知 |
| 多端管理 | 知道用户有几个设备在线 |
| 多端互踢 | 同设备类型踢人 |

## 1.2 量级估算

```
在线用户:        100 万
心跳频率:        30~60s/次 → 1.6~3 万 QPS 心跳写
状态查询:        50 万 QPS（消息投递时查）
状态变更事件:    1 万/s（上下线）
订阅查询:        每用户 200 好友 × 部分订阅 → 大量
```

## 1.3 关键挑战

```
1. 心跳写压力大（持续不停）
2. 查询热点（大V好友很多）
3. 跨地域如何保证投递准确
4. 节点切主时状态丢失
5. 订阅放大（1 个用户上线，N 个好友收到通知）
```

## 1.4 设计目标

| 指标 | 目标 |
|---|---|
| 状态写入 QPS | 5 万/s |
| 状态查询 QPS | 100 万/s |
| 查询延迟 P99 | < 5ms |
| 状态过期检测 | < 60s |
| 上下线通知延迟 | < 3s |
| 单地域故障 | 状态自愈 < 2min |

---

# 2. 状态模型

## 2.1 状态层级

```
用户级状态:
  online / offline / away / busy / invisible
  
设备级状态:
  每个 (userId, deviceId) 独立维护
  路由信息: gatewayId / connId
  
聚合规则:
  用户 online ⇔ 至少一个设备 online
```

## 2.2 数据结构

### 设备级（核心）

```
key:   presence:dev:{userId}:{deviceId}
value: {
  gatewayId:  "gw-east-12",
  connId:     12345,
  loginTime:  1710000000,
  lastBeat:   1710000050,
  deviceType: "ios",
  appVersion: "1.0.0",
  ip:         "1.2.3.4",
  region:     "east"
}
TTL:   90s (心跳续约)
```

### 用户级聚合

```
key:   presence:user:{userId}
value: Hash {
  deviceId1: gatewayId1,
  deviceId2: gatewayId2,
  ...
}
TTL:   不设（随设备级变化）
```

### Gateway 级反查

```
key:   presence:gw:{gatewayId}
value: Set { (userId, deviceId), ... }
用途:  Gateway 挂掉时反查清理
```

## 2.3 用户自定义状态

```
key:   presence:custom:{userId}
value: { status: "busy", emoji: "📚", expire: ... }
```

业务可见的"状态"，不影响投递路由。

---

# 3. 总体架构

## 3.1 模块划分

```
┌──────────────────────────────────────────┐
│  Gateway (心跳来源)                       │
└──────────┬───────────────────────────────┘
           │ 心跳上报
           ▼
┌──────────────────────────────────────────┐
│  Presence Service (无状态)                │
│  ├─ Heartbeat Handler                    │
│  ├─ Query Handler                        │
│  ├─ Subscription Manager                 │
│  └─ Expire Detector                      │
└──────────┬───────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Redis Cluster (presence shard)          │
│  按 userId 分片                           │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Kafka: presence.event                   │
│  (上下线广播)                             │
└──────────────────────────────────────────┘
```

## 3.2 关键交互

```
1. 心跳:
   Gateway → Presence → Redis

2. 查询路由:
   Deliver → Presence → Redis → 返回 gatewayId

3. 订阅通知:
   Presence Expire Detector → Kafka → Subscription Manager → 推送

4. Gateway 主动上下线:
   Gateway → Presence → Redis (立即) + Kafka 事件
```

---

# 4. 数据分片

## 4.1 分片策略

```
按 userId hash 分片到 Redis Cluster

slot = CRC16(userId) % 16384
node = slot_to_node(slot)
```

同一用户的所有设备落同一槽，原子操作友好。

## 4.2 防热点

### 大 V 问题
某些用户被大量查询（明星、客服）→ 单 slot 热点。

### 解决方案

#### 方案 A：本地缓存
```
Presence 服务节点本地 LRU 缓存:
  user → presence (TTL 1s)

热点用户 99% 查询命中本地，不打 Redis
```

#### 方案 B：副本扩散
```
key: presence:user:{userId}:{0..15}
查询时随机选副本
写入时多副本写
```

通常**方案 A 足够**。

## 4.3 Redis 集群规划

```
节点数:        16 主 + 16 从
单节点内存:    16 GB
单节点 QPS:    每节点 8 万 (主+从负载)
总容量:        100 万在线 × 200B = 200 MB（极轻）
总 QPS:        16 × 8万 = 128 万

实际瓶颈不是容量，是 QPS
预留: 3 倍容量
```

---

# 5. 心跳机制

## 5.1 心跳路径

```
客户端 → Gateway (TCP/QUIC ping)
         │
         ▼
Gateway 本地维护 lastBeat
         │
         ▼ 每 N 秒批量
Gateway → Presence Service (RPC)
         │
         ▼
Presence → Redis EXPIRE / SET (Lua)
```

## 5.2 心跳协议

### 客户端到 Gateway
```
客户端每 30s 发 PING (协议层)
Gateway 收到 → 更新本地 lastBeat
```

### Gateway 到 Presence

不是每次心跳都打 Redis，会被打爆。

**做法：批量续约**

```go
// Gateway 内每 10 秒执行一次
func (g *Gateway) renewPresenceBatch() {
    activeConns := g.connMgr.GetActiveSince(time.Now().Add(-15 * time.Second))
    
    batch := make([]*RenewItem, 0, len(activeConns))
    for _, c := range activeConns {
        batch = append(batch, &RenewItem{
            UserID:   c.UserID,
            DeviceID: c.DeviceID,
            ConnID:   c.ConnID,
        })
    }
    
    g.presenceClient.BatchRenew(batch)
}
```

### Presence 批量处理

```go
func (p *Presence) BatchRenew(items []*RenewItem) {
    pipe := redis.Pipeline()
    for _, item := range items {
        key := fmt.Sprintf("presence:dev:%d:%s", item.UserID, item.DeviceID)
        pipe.Expire(key, 90*time.Second)
    }
    pipe.Exec()
}
```

**性能**：1 万 conn / 10s = 1 千 RPC/s，每个 RPC 携带 100 个续约 → 10 万 EXPIRE/s 通过 pipeline 高效完成。

## 5.3 首次登录写入

```lua
-- presence_login.lua
local userKey = KEYS[1]      -- presence:user:{uid}
local devKey  = KEYS[2]      -- presence:dev:{uid}:{did}
local gwKey   = KEYS[3]      -- presence:gw:{gw}
local devId   = ARGV[1]
local gwId    = ARGV[2]
local conn    = ARGV[3]
local now     = ARGV[4]
local ttl     = tonumber(ARGV[5])

-- 写设备级
redis.call('HMSET', devKey, 
  'gw', gwId, 
  'conn', conn, 
  'login', now, 
  'beat', now)
redis.call('EXPIRE', devKey, ttl)

-- 写用户级聚合
redis.call('HSET', userKey, devId, gwId)
redis.call('EXPIRE', userKey, ttl + 30)

-- 写 gateway 反查
redis.call('SADD', gwKey, devId .. '#' .. ARGV[1])
redis.call('EXPIRE', gwKey, 600)

return 1
```

## 5.4 心跳超时处理

```
Redis TTL 自动过期 → 设备记录消失
但 presence:user:{uid} 的 hash 字段不会自动清理
```

需要主动清理：见**第 6 节 TTL 与过期**。

---

# 6. TTL 与过期策略

## 6.1 TTL 设置

```
presence:dev:{uid}:{did}    TTL = 90s
presence:user:{uid}         TTL = 120s（略长，配合清理）
presence:gw:{gw}            TTL = 600s
```

心跳间隔 30s，3 次失败容忍 = 90s。

## 6.2 主动过期检测

仅靠 Redis TTL 不够，因为：
- `presence:user:{uid}` 是 Hash，里面的 device 字段不会随 device key 一起消失
- 需要业务感知"用户离线了"

**方案：Expire Detector 服务**

```go
// 每秒扫描一批用户级 hash
func (e *ExpireDetector) Run() {
    for {
        users := e.scanRecentlyActive(1000)
        
        for _, userId := range users {
            devices, _ := redis.HGetAll(fmt.Sprintf("presence:user:%d", userId))
            
            stillOnline := []string{}
            offlineDevs := []string{}
            
            for devId, _ := range devices {
                exists, _ := redis.Exists(fmt.Sprintf("presence:dev:%d:%s", userId, devId))
                if exists {
                    stillOnline = append(stillOnline, devId)
                } else {
                    offlineDevs = append(offlineDevs, devId)
                }
            }
            
            // 清理 user hash 里的死设备
            for _, devId := range offlineDevs {
                redis.HDel(fmt.Sprintf("presence:user:%d", userId), devId)
                e.publishOfflineEvent(userId, devId)
            }
            
            // 用户全部离线
            if len(stillOnline) == 0 && len(offlineDevs) > 0 {
                redis.Del(fmt.Sprintf("presence:user:%d", userId))
                e.publishUserOfflineEvent(userId)
            }
        }
        
        time.Sleep(1 * time.Second)
    }
}
```

## 6.3 替代方案：Keyspace Notifications

Redis 原生支持过期通知：

```
notify-keyspace-events Ex
```

订阅 `__keyevent@0__:expired`，收到 device key 过期事件 → 立即清理 user hash。

**优点**：实时  
**缺点**：通知不可靠（重启丢失），需配合扫描兜底

## 6.4 分布式扫描

百万用户单进程扫不完，分片扫：

```
Detector 实例数 = N
每个实例扫 hash(userId) % N == myInstanceId 的用户

按 Redis SCAN 游标 + 业务过滤
```

## 6.5 节点切换边界场景

**场景**：用户在 East 在线，East 崩溃，State 仍认为在线 → Deliver 投递到不存在的 Gateway。

**解决**：
1. Gateway 优雅退出时主动 DEL
2. Deliver 投递失败 → 强制刷新状态 → 重新查询
3. Expire Detector 兜底

---

# 7. 路由查询

## 7.1 单用户查询

```go
func (p *Presence) GetUser(userId int64) (*UserPresence, error) {
    // 1. 本地缓存
    if cached := p.localCache.Get(userId); cached != nil {
        return cached, nil
    }
    
    // 2. Redis
    devices, err := redis.HGetAll(fmt.Sprintf("presence:user:%d", userId))
    if err != nil {
        return nil, err
    }
    
    if len(devices) == 0 {
        return &UserPresence{Online: false}, nil
    }
    
    result := &UserPresence{
        UserID:  userId,
        Online:  true,
        Devices: make([]*DevicePresence, 0, len(devices)),
    }
    
    // 3. 批量取设备详情（pipeline）
    pipe := redis.Pipeline()
    cmds := make(map[string]*redis.MapStringStringCmd)
    for devId := range devices {
        key := fmt.Sprintf("presence:dev:%d:%s", userId, devId)
        cmds[devId] = pipe.HGetAll(key)
    }
    pipe.Exec()
    
    for devId, cmd := range cmds {
        if data, err := cmd.Result(); err == nil && len(data) > 0 {
            result.Devices = append(result.Devices, parseDevice(devId, data))
        }
    }
    
    // 4. 写本地缓存（短 TTL）
    p.localCache.Set(userId, result, 1*time.Second)
    
    return result, nil
}
```

## 7.2 批量查询（推荐 API）

消息广播时一次查多个用户：

```go
func (p *Presence) BatchGet(userIds []int64) (map[int64]*UserPresence, error) {
    // 1. 本地缓存命中
    result := make(map[int64]*UserPresence)
    miss := []int64{}
    
    for _, uid := range userIds {
        if cached := p.localCache.Get(uid); cached != nil {
            result[uid] = cached
        } else {
            miss = append(miss, uid)
        }
    }
    
    if len(miss) == 0 {
        return result, nil
    }
    
    // 2. Redis pipeline 批查
    pipe := redis.Pipeline()
    cmds := make([]*redis.MapStringStringCmd, len(miss))
    for i, uid := range miss {
        cmds[i] = pipe.HGetAll(fmt.Sprintf("presence:user:%d", uid))
    }
    pipe.Exec()
    
    for i, uid := range miss {
        devices, _ := cmds[i].Result()
        if len(devices) > 0 {
            up := &UserPresence{Online: true, ...}
            result[uid] = up
            p.localCache.Set(uid, up, 1*time.Second)
        } else {
            result[uid] = &UserPresence{Online: false}
        }
    }
    
    return result, nil
}
```

## 7.3 投递路径优化

```
Deliver 服务接收 fanout 事件 (多个 recipient)
   │
   ▼
BatchGet(recipients) → Map[uid → presence]
   │
   ▼
按 gatewayId 分组:
  gw-1: [uid1, uid2, uid3]
  gw-2: [uid4, uid5]
   │
   ▼
向每个 Gateway 单次 RPC（批量推送）
```

减少 RPC 次数。

## 7.4 缓存策略

```
本地缓存:
  Type:  LRU + TTL
  Size:  100 万条
  TTL:   1 秒
  
意义:
  消息突发时同一用户被查多次
  用户状态变化不频繁
  1 秒延迟可接受
```

---

# 8. 订阅模型

## 8.1 业务场景

```
- 好友列表显示在线状态
- 群成员在线状态
- 客服系统：客户上线提醒
- 多端同步：另一端登录通知
```

## 8.2 订阅 vs 轮询

### 轮询（简单）
```
客户端定期拉所有好友状态
- 优点：简单
- 缺点：QPS 高、不实时
```

### 订阅（推荐）
```
客户端订阅好友列表
状态变化时服务端主动推送
- 优点：实时、省 QPS
- 缺点：复杂度高
```

实战：**关键场景订阅 + 兜底轮询**。

## 8.3 订阅架构

```
┌────────────────────────────┐
│  Client                    │
│  - 订阅好友列表             │
│  - 接收状态变更             │
└──────────┬─────────────────┘
           │ subscribe(friend_ids)
           ▼
┌────────────────────────────┐
│  Subscription Manager      │
│  - 维护 user → subscribers │
│  - 维护 subscriber → users │
└──────────┬─────────────────┘
           │
           ▼
┌────────────────────────────┐
│  Kafka: presence.event     │
│  - 上下线事件流             │
└──────────┬─────────────────┘
           │
           ▼
┌────────────────────────────┐
│  Subscription Dispatcher   │
│  - 消费事件                 │
│  - 查找订阅者               │
│  - 推送给在线订阅者         │
└────────────────────────────┘
```

## 8.4 订阅数据结构

### 用户的订阅列表
```
key: presence:sub:{userId}
type: Set
value: { friendId1, friendId2, ... }
TTL: 跟随用户在线
```

### 用户的关注者（反向索引）
```
key: presence:watcher:{userId}
type: Set
value: { subscriber1, subscriber2, ... }
TTL: 长期保持
```

## 8.5 订阅流程

```go
// 用户上线时上报订阅
func (s *Subscription) Subscribe(userId int64, friendIds []int64) {
    // 1. 写正向
    redis.SAdd(fmt.Sprintf("presence:sub:%d", userId), friendIds)
    redis.Expire(fmt.Sprintf("presence:sub:%d", userId), 1*time.Hour)
    
    // 2. 写反向
    pipe := redis.Pipeline()
    for _, fid := range friendIds {
        pipe.SAdd(fmt.Sprintf("presence:watcher:%d", fid), userId)
        pipe.Expire(fmt.Sprintf("presence:watcher:%d", fid), 7*24*time.Hour)
    }
    pipe.Exec()
    
    // 3. 立即返回当前状态
    current, _ := s.presence.BatchGet(friendIds)
    s.notifyClient(userId, current)
}
```

## 8.6 状态变更广播

```go
// 用户上线
func (p *Presence) OnUserOnline(userId int64, deviceInfo *DeviceInfo) {
    // 1. 写状态
    p.writeOnline(userId, deviceInfo)
    
    // 2. 发事件到 Kafka
    p.kafka.Publish("presence.event", &PresenceEvent{
        Type:      "online",
        UserID:    userId,
        Device:    deviceInfo.DeviceID,
        Timestamp: time.Now().UnixMilli(),
    })
}

// Subscription Dispatcher 消费
func (d *Dispatcher) onPresenceEvent(evt *PresenceEvent) {
    // 1. 查谁订阅了
    watchers, _ := redis.SMembers(fmt.Sprintf("presence:watcher:%d", evt.UserID))
    
    if len(watchers) == 0 {
        return
    }
    
    // 2. 过滤在线订阅者
    presence, _ := d.presence.BatchGet(watchers)
    onlineWatchers := []int64{}
    for _, w := range watchers {
        if presence[w].Online {
            onlineWatchers = append(onlineWatchers, w)
        }
    }
    
    // 3. 按 Gateway 分组推送
    grouped := groupByGateway(onlineWatchers, presence)
    for gw, uids := range grouped {
        d.gatewayClient(gw).PushPresence(uids, evt)
    }
}
```

## 8.7 订阅放大问题

```
大 V 上下线 → 1000 万订阅者 → 推送爆炸
```

### 解决方案

#### 1. 大 V 不主动推送
```
大 V 状态默认隐藏
订阅者轮询查询（5 分钟一次）
```

#### 2. 优先级订阅
```
近期互动过的好友: 实时推送
其他好友:        延迟批量推送
```

#### 3. 限流
```
单用户状态变更: 1 分钟内最多通知 1 次
避免抖动场景频繁推送
```

#### 4. 去重抖动
```
用户 30 秒内反复上下线 → 合并为最后一次状态
```

```go
// debounce
func (d *Dispatcher) onPresenceEvent(evt *PresenceEvent) {
    key := fmt.Sprintf("debounce:%d", evt.UserID)
    
    // 30 秒内只触发一次
    if !redis.SetNX(key, "1", 30*time.Second) {
        // 已有 pending 通知
        return
    }
    
    time.AfterFunc(2*time.Second, func() {
        // 发送时取最终状态
        finalState := d.presence.GetUser(evt.UserID)
        d.broadcast(evt.UserID, finalState)
    })
}
```

---

# 9. 跨地域设计

## 9.1 跨地域查询难题

```
用户 A 在 East 在线
用户 B 在 South，给 A 发消息
South 的 Deliver 怎么知道 A 在 East？
```

## 9.2 方案对比

### 方案 A：全局状态中心
```
所有地域写一个全局 Redis
缺点：跨地域延迟、单点
```

### 方案 B：状态跨地域复制
```
每地域写本地，异步复制到其他地域
缺点：复制延迟期间状态不一致
```

### 方案 C：用户主区域路由（推荐）
```
用户主区域 (home_region) 全局已知
查询路由优先到主区域
状态只在主区域权威存储
```

## 9.3 推荐方案：主区域路由 + 转发

### 数据布局

```
全局元数据 (etcd / 全局 DB):
  user_id → home_region

各地域 Presence:
  仅维护主区域用户的状态
```

### 用户漫游接入

```
用户 home_region = East
出差到深圳，连接 South Gateway

South Gateway:
  收到登录请求
  查 user_id → home_region = East
  转发登录到 East Presence
  East Presence 写状态: device.gateway = "gw-south-X"
```

### 查询流程

```
South Deliver 要投递给 user A
  ↓
查 user_A → home_region = East
  ↓
RPC 到 East Presence
  ↓
返回 gateway = "gw-south-X" (实际在南方接入)
  ↓
South Deliver 直接调用 gw-south-X
```

## 9.4 跨地域 RPC 优化

```
South → East 查询: 50ms RTT
高频查询不可接受

优化:
  - South 本地缓存（1 秒 TTL）
  - 批量查询
  - 仅消息投递时查
```

## 9.5 主区域故障

```
East 整个挂掉

降级:
  - 用户重连到 South
  - South 临时接管，写本地 Presence
  - 标记 user.home_region = "south" (临时)

East 恢复:
  - 异步合并状态
  - 用户重连后修正
```

---

# 10. 容错与一致性

## 10.1 一致性级别

```
Presence 不需要强一致
最终一致即可:
  - 上下线感知 < 90s
  - 状态变更通知 < 3s
  - 投递失败可触发刷新
```

## 10.2 失效传播

```
Gateway 挂掉 (整个进程)
  ↓
该 Gateway 上所有用户状态 90s 后过期
  ↓
但消息可能投递到这个失效 Gateway → 失败
```

### 加速恢复

```
监控系统检测 Gateway 心跳停止
  ↓
立即调用 Presence: ForceCleanGateway(gwId)
  ↓
SMEMBERS presence:gw:{gw} → 所有 device
  ↓
批量 DEL 设备记录
  ↓
触发 offline 事件
```

```go
func (p *Presence) ForceCleanGateway(gwId string) {
    devices, _ := redis.SMembers(fmt.Sprintf("presence:gw:%s", gwId))
    
    for _, dev := range devices {
        userId, deviceId := parse(dev)
        
        redis.Del(fmt.Sprintf("presence:dev:%d:%s", userId, deviceId))
        redis.HDel(fmt.Sprintf("presence:user:%d", userId), deviceId)
        
        p.publishOfflineEvent(userId, deviceId)
    }
    
    redis.Del(fmt.Sprintf("presence:gw:%s", gwId))
}
```

## 10.3 投递失败的状态修正

```go
// Deliver 收到 Gateway NOT_FOUND
func (d *Deliver) onPushFailed(userId int64, gwId string, err error) {
    if err == ErrConnNotFound {
        // 强制刷新
        d.presence.Invalidate(userId)
        
        // 重新查询
        fresh, _ := d.presence.GetUser(userId)
        if fresh.Online && fresh.Gateway != gwId {
            d.retryPush(userId, fresh.Gateway)
        } else {
            // 真离线 → 进 inbox + push 通知
            d.handleOffline(userId)
        }
    }
}
```

## 10.4 双写竞态

```
场景: 同设备两次登录消息几乎同时到
旧登录: gw-A
新登录: gw-B

如果新先到，旧后到 → 状态变成 gw-A (错)
```

### 解决：版本号

```lua
-- Lua 脚本: 版本号 + 比较
local key = KEYS[1]
local newVer = tonumber(ARGV[1])
local newGw = ARGV[2]

local oldVer = tonumber(redis.call('HGET', key, 'ver') or 0)
if newVer > oldVer then
    redis.call('HMSET', key, 'ver', newVer, 'gw', newGw, ...)
    return 1
else
    return 0  -- 旧请求被忽略
end
```

版本号用客户端登录时间或递增 ID。

---

# 11. 性能优化

## 11.1 心跳合并

Gateway 不每次心跳都打 Presence，而是聚合 10s 一次。

```
1 万 Gateway × 10 万用户 / 30s 心跳 = 3.3 万 QPS
聚合后: 1 万 RPC / 10s = 1 千 RPC/s (每个含 3.3 万续约)
通过 pipeline → Redis QPS 仍是 3.3 万 EXPIRE，但减少了网络往返
```

## 11.2 本地缓存

```
Presence 服务节点:
  本地 LRU 100 万条
  TTL 1 秒
  
命中率: > 80%
减少 Redis QPS: 80%
```

## 11.3 Redis Pipeline

批量 HGET / HMSET / EXPIRE 用 pipeline。

```
单 RTT: 1ms
100 个命令逐个: 100ms
100 个命令 pipeline: 1.5ms
```

## 11.4 读写分离

```
心跳写: 主节点
查询读: 从节点（容忍 < 1s 延迟）
```

## 11.5 数据压缩

device 信息用紧凑序列化（Protobuf / MessagePack）。

```
JSON: 250 字节
Protobuf: 80 字节
```

---

# 12. 监控指标

## 12.1 关键指标

| 指标 | 类型 | 目标 |
|---|---|---|
| `presence_online_users` | Gauge | 当前在线 |
| `presence_heartbeat_qps` | Counter | 心跳速率 |
| `presence_query_qps{type}` | Counter | 查询速率 |
| `presence_query_latency` | Histogram | 查询延迟 |
| `presence_cache_hit_ratio` | Gauge | 本地缓存命中 |
| `presence_redis_lag` | Gauge | Redis 主从延迟 |
| `presence_event_publish_qps` | Counter | 事件发布速率 |
| `presence_subscribers_total` | Gauge | 订阅总数 |
| `presence_orphan_devices` | Gauge | 孤立设备记录 |

## 12.2 告警

```
- presence_query_latency P99 > 50ms (5min)
- presence_cache_hit_ratio < 50% (突降)
- presence_orphan_devices > 1000 (Detector 异常)
- Redis 不可用
```

## 12.3 大盘

```
Panel 1: 在线用户曲线
Panel 2: 心跳/查询 QPS
Panel 3: 查询延迟分布
Panel 4: 缓存命中率
Panel 5: 各 Gateway 在线分布
Panel 6: 上下线事件速率
```

---

# 附录：状态服务 API 设计

## A.1 RPC 接口

```protobuf
service PresenceService {
  // 上线
  rpc Online(OnlineReq) returns (OnlineResp);
  
  // 下线
  rpc Offline(OfflineReq) returns (OfflineResp);
  
  // 批量心跳续约
  rpc BatchRenew(BatchRenewReq) returns (BatchRenewResp);
  
  // 单用户查询
  rpc GetUser(GetUserReq) returns (UserPresence);
  
  // 批量查询
  rpc BatchGet(BatchGetReq) returns (BatchGetResp);
  
  // 订阅
  rpc Subscribe(SubscribeReq) returns (SubscribeResp);
  rpc Unsubscribe(UnsubscribeReq) returns (UnsubscribeResp);
  
  // 强制清理（运维）
  rpc ForceCleanGateway(ForceCleanReq) returns (ForceCleanResp);
}
```

## A.2 数据结构

```protobuf
message UserPresence {
  int64 user_id = 1;
  bool online = 2;
  repeated DevicePresence devices = 3;
  int64 last_active = 4;
}

message DevicePresence {
  string device_id = 1;
  string device_type = 2;
  string gateway_id = 3;
  int64 conn_id = 4;
  string region = 5;
  int64 login_time = 6;
  int64 last_beat = 7;
}
```

---

**文档结束** | Version 1.0