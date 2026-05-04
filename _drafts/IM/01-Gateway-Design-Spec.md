# Gateway 详细设计文档 v1.0

> 长连接接入网关 - 千万并发 IM 系统的"大门"  
> 关键词：连接管理 / 协议解析 / QUIC 迁移 / 限流

## 目录
1. [职责与定位](#1-职责与定位)
2. [整体架构](#2-整体架构)
3. [连接管理](#3-连接管理)
4. [协议解析](#4-协议解析)
5. [QUIC 连接迁移](#5-quic-连接迁移)
6. [限流细节](#6-限流细节)
7. [路由与投递](#7-路由与投递)
8. [心跳与保活](#8-心跳与保活)
9. [安全设计](#9-安全设计)
10. [故障与容灾](#10-故障与容灾)
11. [性能与调优](#11-性能与调优)
12. [关键数据结构](#12-关键数据结构)

---

# 1. 职责与定位

## 1.1 核心职责

```
┌──────────────────────────────────────┐
│            Gateway 职责               │
├──────────────────────────────────────┤
│ 1. 长连接终结 (TLS/QUIC/WS)           │
│ 2. 协议解析 (二进制 frame)             │
│ 3. 鉴权认证 (Token 校验)              │
│ 4. 限流防护 (本地令牌桶)               │
│ 5. 消息路由 (上行→业务/下行→客户端)     │
│ 6. 在线状态维护 (上报状态服务)          │
│ 7. 心跳保活                          │
│ 8. 连接迁移 (QUIC CID)                │
└──────────────────────────────────────┘
```

## 1.2 不该做的事
- ❌ 不做业务逻辑（消息内容处理、群成员管理等）
- ❌ 不直接读写主 DB
- ❌ 不做复杂风控判定（只做粗筛）
- ❌ 不缓存业务数据（除连接相关）

---

# 2. 整体架构

```
                    ┌─────────────────────┐
                    │      Client         │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   L4 LB (DPVS/      │
                    │   Katran/eBPF)      │  ← QUIC CID 路由
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     Gateway         │
                    ├─────────────────────┤
                    │ ┌─────────────────┐ │
                    │ │ Acceptor 线程池 │ │
                    │ ├─────────────────┤ │
                    │ │ IO 多路复用      │ │
                    │ ├─────────────────┤ │
                    │ │ 协议解析层       │ │
                    │ ├─────────────────┤ │
                    │ │ 限流/鉴权        │ │
                    │ ├─────────────────┤ │
                    │ │ 路由分发器       │ │
                    │ ├─────────────────┤ │
                    │ │ 连接表 (本地)    │ │
                    │ └─────────────────┘ │
                    └────┬────────────┬───┘
                         │            │
              ┌──────────▼──┐    ┌────▼──────────┐
              │ 业务服务集群 │    │ 状态服务      │
              │ (gRPC)     │    │ (Redis)       │
              └────────────┘    └───────────────┘
```

## 2.1 部署规格

| 项 | 配置 |
|---|---|
| 实例规格 | 16 核 / 32GB / 万兆网卡 |
| 单实例连接 | 50K~100K |
| 单实例 QPS | 50K (上行) / 100K (下行) |
| OS | Linux 5.x，开启 BBR |
| 运行时 | Go 1.22+ / C++ 自研 |
| 部署 | K8s StatefulSet 或裸金属 |

## 2.2 关键依赖

| 依赖 | 用途 |
|---|---|
| etcd | 服务发现 + 主备状态 + 配置 |
| Redis | 在线状态上报 |
| Kafka | 异步事件（连接事件、行为日志） |
| 业务服务 | gRPC 调用 |
| 监控 | Prometheus + OpenTelemetry |

---

# 3. 连接管理

## 3.1 连接表设计

```go
// 全局连接表（每个 Gateway 实例一份）
type ConnectionManager struct {
    // 主索引：connId → conn
    connsByID    sync.Map  // map[uint64]*Conn
    
    // 用户索引：userId → []connId  
    connsByUser  sync.Map  // map[int64][]uint64
    
    // 设备索引：(userId, deviceId) → connId
    connsByDevice sync.Map // map[string]uint64
    
    // 统计
    totalConns   atomic.Int64
}

type Conn struct {
    ID          uint64        // 单机递增
    UserID      int64
    DeviceID    string
    Protocol    Protocol      // ws/quic
    
    Socket      net.Conn      // 底层连接
    
    // 状态
    State       atomic.Int32  // 0:init 1:authed 2:closing
    LoginAt     int64
    LastActive  atomic.Int64
    
    // 限流（每连接独立）
    msgBucket   *TokenBucket
    sigBucket   *TokenBucket
    
    // 写队列
    writeChan   chan []byte   // 缓冲 256
    
    // 元数据
    ClientIP    string
    UserAgent   string
    AppVersion  string
    
    // QUIC 专属
    CID         []byte        // 当前活跃 CID
    Migrated    bool          // 是否发生过迁移
}
```

## 3.2 连接生命周期

```
[Accept] 
   ↓
[TLS/QUIC 握手]                      ← 5s 超时
   ↓
[读取 LOGIN 帧]                      ← 10s 超时
   ↓
[Token 校验] (调用 Auth Service)      ← 100ms 超时
   ↓
[挤号检测]                            ← 同一 device 已存在则踢
   ↓
[加入连接表]
   ↓
[上报 Presence]                       ← 异步
   ↓
[发送 LOGIN_ACK]
   ↓
[正常通信]   ←─── 心跳续约
   ↓
[CLOSE / ERROR / TIMEOUT]
   ↓
[清理连接表]
   ↓
[上报 Logout (Presence)]              ← 异步
```

## 3.3 单机连接上限

```go
// 启动时配置
const (
    MaxConnsPerInstance  = 100_000
    MaxConnsPerIP        = 50
    MaxConnsPerUser      = 5     // 多端登录
)

// 接受新连接前检查
func (cm *ConnectionManager) CanAccept(ip string) error {
    if cm.totalConns.Load() >= MaxConnsPerInstance {
        return ErrInstanceFull
    }
    if cm.connsByIP(ip) >= MaxConnsPerIP {
        return ErrIPFull
    }
    return nil
}
```

## 3.4 多端登录与挤号

```go
func (cm *ConnectionManager) Login(userId int64, deviceId string, conn *Conn) error {
    key := fmt.Sprintf("%d:%s", userId, deviceId)
    
    // CAS 替换：同 device 已有连接则踢掉
    if oldConnId, ok := cm.connsByDevice.Load(key); ok {
        oldConn := cm.connsByID[oldConnId]
        oldConn.SendKick(KickReasonOtherDeviceLogin)
        oldConn.Close()
    }
    
    // 检查同用户连接数
    userConns := cm.GetUserConns(userId)
    if len(userConns) >= MaxConnsPerUser {
        // 踢掉最老的
        oldest := findOldest(userConns)
        oldest.SendKick(KickReasonTooManyDevices)
        oldest.Close()
    }
    
    cm.connsByDevice.Store(key, conn.ID)
    cm.connsByUser.Append(userId, conn.ID)
    cm.connsByID.Store(conn.ID, conn)
    
    return nil
}
```

## 3.5 异地登录策略

```
策略选项（业务可配）：
A. 互不影响：多端可同时在线（推荐）
B. 单端互踢：手机登录 → PC 下线
C. 平台分组：手机+PC 各保留一个

实现：
  在 Login 时按策略检查 connsByUser
  踢出时发 KICK 帧 + 原因码
```

## 3.6 优雅关闭

```go
func (cm *ConnectionManager) GracefulShutdown(ctx context.Context) {
    // 1. 停止接受新连接
    cm.stopAccepting()
    
    // 2. 通知所有连接重连
    cm.connsByID.Range(func(_, v interface{}) bool {
        conn := v.(*Conn)
        conn.SendReconnect(ReasonShutdown, suggestedDelay=2)
        return true
    })
    
    // 3. 等待客户端主动断开（最多 30s）
    deadline := time.After(30 * time.Second)
    for cm.totalConns.Load() > 0 {
        select {
        case <-deadline:
            cm.forceCloseAll()
            return
        case <-time.After(100 * time.Millisecond):
        }
    }
}
```

---

# 4. 协议解析

## 4.1 协议栈

```
应用层:    IM Frame (Protobuf)
传输层:    WebSocket / QUIC stream
TLS:       1.3
传输:      TCP / UDP
```

## 4.2 帧格式（详细）

```
偏移   字段         长度    说明
─────────────────────────────────────
0      Magic        1B      0x4D ("M")
1      Version      1B      协议版本号
2-3    Cmd          2B      指令类型 (网络字节序)
4-5    Flags        2B      位标志
6-13   SeqId        8B      请求 ID
14-17  BodyLen      4B      Body 长度
18..   Body         变长     Protobuf 编码

Flags 位:
  bit 0: 是否压缩 (1=zstd)
  bit 1: 是否加密 (业务层加密)
  bit 2: 是否需要 ACK
  bit 3: 优先级 (0=normal 1=high)
  bit 4-15: 保留
```

## 4.3 Cmd 编码表

```
0x00xx  连接管理类
  0x0001 LOGIN
  0x0002 LOGOUT
  0x0003 HEARTBEAT
  0x0004 HEARTBEAT_ACK
  0x0005 KICK
  0x0006 RECONNECT_HINT

0x01xx  消息类
  0x0101 SEND_MSG
  0x0102 SEND_ACK
  0x0103 PUSH_MSG
  0x0104 RECALL
  0x0105 EDIT
  0x0106 READ_REPORT
  0x0107 READ_NOTIFY
  0x0108 TYPING

0x02xx  同步类
  0x0201 SYNC_PULL
  0x0202 SYNC_NOTIFY
  0x0203 GET_HISTORY

0x03xx  会话类
  0x0301 GET_CONV_LIST
  0x0302 GET_UNREAD

0x04xx  群组类
  0x0401 JOIN_GROUP
  0x0402 LEAVE_GROUP
  ...

0xFFxx  系统/调试
  0xFF01 PING
  0xFF02 SERVER_NOTICE
```

## 4.4 解析流程

```go
func (g *Gateway) HandleFrame(conn *Conn, raw []byte) error {
    // 1. 长度校验
    if len(raw) < HeaderSize {
        return ErrFrameTooShort
    }
    
    // 2. Magic 校验
    if raw[0] != MagicByte {
        return ErrBadMagic
    }
    
    // 3. 解析头
    header := parseHeader(raw[:HeaderSize])
    
    // 4. 版本兼容
    if header.Version > MaxSupportedVersion {
        return ErrUnsupportedVersion
    }
    
    // 5. Body 长度校验
    if header.BodyLen > MaxFrameSize {  // 1MB
        return ErrFrameTooLarge
    }
    if len(raw) < HeaderSize + int(header.BodyLen) {
        return ErrFrameIncomplete
    }
    
    body := raw[HeaderSize:HeaderSize+header.BodyLen]
    
    // 6. 解压（如果有）
    if header.Flags & FlagCompressed != 0 {
        body = zstdDecompress(body)
    }
    
    // 7. 限流检查
    if !conn.msgBucket.TryAcquire(1) {
        return g.sendRateLimited(conn, header.SeqId)
    }
    
    // 8. 鉴权检查（除了 LOGIN/HEARTBEAT）
    if header.Cmd != CmdLogin && header.Cmd != CmdHeartbeat {
        if conn.State.Load() != StateAuthed {
            return ErrNotAuthed
        }
    }
    
    // 9. 路由分发
    return g.dispatch(conn, header, body)
}
```

## 4.5 拆包/粘包处理

```go
// 基于长度前缀的拆包
type FrameDecoder struct {
    buf  bytes.Buffer
}

func (d *FrameDecoder) Decode(data []byte) ([][]byte, error) {
    d.buf.Write(data)
    
    var frames [][]byte
    for {
        if d.buf.Len() < HeaderSize {
            break  // 不够头长度，等下次
        }
        
        header := peekHeader(d.buf.Bytes())
        totalLen := HeaderSize + int(header.BodyLen)
        
        if d.buf.Len() < totalLen {
            break  // 不够整帧
        }
        
        frame := make([]byte, totalLen)
        d.buf.Read(frame)
        frames = append(frames, frame)
    }
    
    return frames, nil
}
```

## 4.6 写路径优化

```go
// 写合并：批量发送减少 syscall
func (c *Conn) WriteLoop() {
    var batch [][]byte
    timer := time.NewTimer(5 * time.Millisecond)
    
    for {
        select {
        case data := <-c.writeChan:
            batch = append(batch, data)
            if len(batch) >= 10 {
                c.flushBatch(batch)
                batch = nil
                timer.Reset(5 * time.Millisecond)
            }
        case <-timer.C:
            if len(batch) > 0 {
                c.flushBatch(batch)
                batch = nil
            }
            timer.Reset(5 * time.Millisecond)
        case <-c.closeChan:
            return
        }
    }
}

func (c *Conn) flushBatch(batch [][]byte) {
    // 用 net.Buffers.WriteTo 一次性写
    buffers := net.Buffers(batch)
    buffers.WriteTo(c.Socket)
}
```

## 4.7 客户端 SDK 协议处理（参考）

```
SDK 层职责:
  1. 维护本地 SeqId → callback 映射
  2. ACK 超时重试 (3 次, 指数退避)
  3. 收到 PUSH_MSG 后回 ACK (避免重复推送)
  4. 收到 KICK 处理重登流程
  5. 收到 RECONNECT_HINT 走重连
```

---

# 5. QUIC 连接迁移

## 5.1 CID 编码格式

```
| 1B Version | 2B ServerID | 1B Generation | 4B Salt | 8B Encrypted Random |
                                                        ↑ AES 加密整体

Version:    CID 格式版本 (升级用)
ServerID:   网关节点 ID (1-65535)
Generation: 节点代际 (扩缩容时区分)
Salt:       与 Random 一起加密的混淆数据
Random:     真随机数,防追踪
```

## 5.2 CID 加解密（LB ↔ Gateway 共享密钥）

```go
var cidKey = [32]byte{...} // 从配置中心拉取，定期轮转

func EncodeCID(serverID uint16, generation uint8) []byte {
    cid := make([]byte, 16)
    cid[0] = CIDVersion
    binary.BigEndian.PutUint16(cid[1:3], serverID)
    cid[3] = generation
    
    // 4-15 用随机数 + 盐
    rand.Read(cid[4:16])
    
    // AES-128 加密 4-15 字节
    block, _ := aes.NewCipher(cidKey[:16])
    block.Encrypt(cid[4:16], cid[4:16])  // 简化，实际用 AES-GCM/CTR
    
    return cid
}

func DecodeCID(cid []byte) (serverID uint16, gen uint8, ok bool) {
    if len(cid) < 16 || cid[0] != CIDVersion {
        return 0, 0, false
    }
    return binary.BigEndian.Uint16(cid[1:3]), cid[3], true
}
```

## 5.3 LB 路由实现（XDP/eBPF 伪代码）

```c
// XDP 程序：内核态解析 UDP 包，提取 CID，转发到对应后端
SEC("xdp")
int quic_router(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;
    
    // 解析以太网/IP/UDP头
    struct ethhdr *eth = data;
    struct iphdr  *ip  = data + sizeof(*eth);
    struct udphdr *udp = data + sizeof(*eth) + sizeof(*ip);
    
    // UDP payload 是 QUIC 包
    void *quic = (void *)(udp + 1);
    
    // 解析 QUIC short header (1 byte flag + DCID)
    if (quic + 1 + CID_LEN > data_end) return XDP_DROP;
    
    __u8 first_byte = *(__u8*)quic;
    if ((first_byte & 0x80) != 0) {
        // long header (握手包) → 哈希分配
        return hash_route(ip, udp);
    }
    
    // short header → 解 DCID
    __u8 *dcid = quic + 1;
    
    // 查路由表（BPF map）
    __u16 server_id = lookup_server_id(dcid);
    if (server_id == 0) return XDP_DROP;
    
    // 重写目标 MAC 转发
    return redirect_to_server(server_id);
}
```

## 5.4 连接迁移完整流程

```
[握手阶段]
  Server → Client: SCID = encoded_cid_pool[1..8]
                   NEW_CONNECTION_ID × 8

[正常通信]
  Client/Server 用 CID 通信
  
[网络切换检测]
  Client SDK 监听 NetworkChange
  ↓
  立即从新地址发包（用未使用的备用 CID）
  
[服务端处理]
  收到来自新四元组的包
  ↓
  CID 已知 → 启动路径验证
  ↓
  Send PATH_CHALLENGE (随机 8B)
  ↓
  Recv PATH_RESPONSE  → 验证通过
  ↓
  切换活跃路径
  ↓
  RETIRE_CONNECTION_ID 旧 CID
  ↓
  发放新备用 CID (NEW_CONNECTION_ID)
```

## 5.5 业务层无感处理

```go
// QUIC 库回调
func (g *Gateway) OnPathMigrated(connID uint64, oldAddr, newAddr net.Addr) {
    conn := g.connMgr.Get(connID)
    if conn == nil { return }
    
    conn.Migrated = true
    conn.RemoteAddr = newAddr
    
    // 不需要：
    // - 不重新登录
    // - 不重置心跳
    // - 不通知业务
    // 业务层完全无感
    
    // 上报埋点
    metrics.MigrationSuccess.Inc()
    log.Info("connection migrated", 
        "connID", connID, 
        "oldAddr", oldAddr,
        "newAddr", newAddr)
}
```

## 5.6 CID 池管理

```go
type CIDPool struct {
    pool     [][]byte  // 已发出的 CID
    retired  [][]byte  // 待清理的 CID
    minPool  int       // 最少预留数量
}

// 客户端使用了一个 CID，服务端补充
func (p *CIDPool) OnCIDUsed(usedCID []byte) {
    p.markActive(usedCID)
    
    if p.activeCIDs() < p.minPool {
        // 补发
        newCID := EncodeCID(serverID, generation)
        sendNewConnectionID(newCID)
    }
}

// 收到 RETIRE_CONNECTION_ID
func (p *CIDPool) OnRetire(cid []byte) {
    p.retired = append(p.retired, cid)
    // 30s 后真正释放（避免乱序包）
}
```

## 5.7 节点宕机处理

```
场景: ServerID=42 节点宕机

1. 健康检查发现 → 从 LB BPF map 移除 server_id=42
2. 后续指向 42 的 CID 包 → BPF 查询失败 → 丢包
3. 客户端检测到无响应 (3s)
4. 客户端尝试 0-RTT 恢复连接
5. 0-RTT 失败则全新握手
6. 新连接被 LB 哈希到健康节点
```

---

# 6. 限流细节

## 6.1 限流维度（Gateway 层）

| 维度 | 实现 | 默认阈值 |
|---|---|---|
| 单连接消息频率 | 令牌桶 (本地) | 10/s, 突发 30 |
| 单连接信令频率 | 令牌桶 (本地) | 50/s |
| 单连接出口带宽 | 滑动窗口 | 100KB/s |
| 单 IP 连接数 | 计数 | 50 |
| 单 IP 建连频率 | 令牌桶 (本地) | 10/s |
| 单 IP 消息频率 | 令牌桶 (本地+共享) | 100/s |
| 全局新连接 | 全实例计数 | 1000/s |

## 6.2 令牌桶实现（高性能）

```go
type TokenBucket struct {
    capacity   int64
    rate       int64    // tokens per second
    tokens     atomic.Int64
    lastRefill atomic.Int64  // unix nano
}

func (tb *TokenBucket) TryAcquire(n int64) bool {
    now := time.Now().UnixNano()
    
    for {
        last := tb.lastRefill.Load()
        elapsed := now - last
        
        // CAS 推进 lastRefill
        if elapsed > 0 {
            if !tb.lastRefill.CompareAndSwap(last, now) {
                continue  // 被其他线程抢先，重试
            }
            
            // 补充令牌
            add := elapsed * tb.rate / 1e9
            for {
                old := tb.tokens.Load()
                new := min(old + add, tb.capacity)
                if tb.tokens.CompareAndSwap(old, new) {
                    break
                }
            }
        }
        
        // 尝试扣减
        for {
            old := tb.tokens.Load()
            if old < n {
                return false
            }
            if tb.tokens.CompareAndSwap(old, old - n) {
                return true
            }
        }
    }
}
```

## 6.3 分级限流策略

```go
// 同一连接遭遇限流：
const (
    SoftLimit = 1.5  // 阈值的 1.5 倍 → 丢弃 + 警告
    HardLimit = 3.0  // 阈值的 3 倍 → 断开连接
)

func (g *Gateway) OnRateLimited(conn *Conn, severity float64) {
    switch {
    case severity < SoftLimit:
        // 软限：丢包，回 RATE_LIMITED 错误
        g.sendError(conn, ErrRateLimited, "slow down")
        
    case severity < HardLimit:
        // 中等：本连接加入"减速名单"，所有阈值 ×0.5
        conn.applyHalfSpeed(60 * time.Second)
        
    default:
        // 硬限：直接断开
        log.Warn("hard rate limit, closing", "userId", conn.UserID)
        conn.Close()
        // 上报风控
        g.reportToRisk(conn, "hard_rate_limit")
    }
}
```

## 6.4 IP 层限流

```go
type IPLimiter struct {
    // 全 Gateway 实例共享（基于 sync.Map）
    counters sync.Map  // ip → *atomic.Int64
    buckets  sync.Map  // ip → *TokenBucket
}

// 接受连接前
func (l *IPLimiter) CheckConnect(ip string) error {
    cnt := l.getOrCreateCounter(ip)
    if cnt.Load() >= MaxConnsPerIP {
        return ErrIPConnFull
    }
    
    bucket := l.getOrCreateBucket(ip, 10, 30)  // 10/s, 突发 30
    if !bucket.TryAcquire(1) {
        return ErrIPConnRateLimit
    }
    
    cnt.Add(1)
    return nil
}

// 连接关闭时
func (l *IPLimiter) Release(ip string) {
    if cnt, ok := l.counters.Load(ip); ok {
        cnt.(*atomic.Int64).Add(-1)
    }
}
```

## 6.5 跨 Gateway 共享限流（高维度）

某些限流（如单用户全局消息频率）需要跨实例共享：

```go
// 用户级限流走 Redis
func (g *Gateway) CheckUserRate(userID int64) bool {
    key := fmt.Sprintf("rate:user:%d:msg", userID)
    return redisLimiter.Check(key, 200, 60)  // 200/min
}

// 优化：本地缓存 1s
type LocalCache struct {
    blocked sync.Map  // userId → blockedUntil(unix)
}

func (g *Gateway) CheckUserRateOptimized(userID int64) bool {
    if until, ok := g.blockedCache.Load(userID); ok {
        if time.Now().Unix() < until.(int64) {
            return false  // 1s 内不再查 Redis
        }
    }
    
    if !g.CheckUserRate(userID) {
        g.blockedCache.Store(userID, time.Now().Unix() + 1)
        return false
    }
    return true
}
```

## 6.6 限流响应处理

```protobuf
message RateLimitedError {
  int32  code        = 1;       // 错误码
  string reason      = 2;       // 可读原因
  int32  retry_after = 3;       // 秒
  int32  limit       = 4;       // 当前阈值
  int32  current     = 5;       // 当前计数
}
```

客户端收到后：
- 显示 toast（可选）
- 按 retry_after 退避
- 不要立即重试

---

# 7. 路由与投递

## 7.1 上行路由（客户端 → 业务）

```go
func (g *Gateway) dispatch(conn *Conn, header *Header, body []byte) error {
    switch header.Cmd {
    case CmdSendMsg:
        return g.routeToBiz("msg-write", conn, body, header.SeqId)
    case CmdRecall:
        return g.routeToBiz("msg-recall", conn, body, header.SeqId)
    case CmdSyncPull:
        return g.routeToBiz("msg-sync", conn, body, header.SeqId)
    case CmdReadReport:
        return g.routeToBiz("counter-svc", conn, body, header.SeqId)
    // ...
    }
}

func (g *Gateway) routeToBiz(svc string, conn *Conn, body []byte, seqId uint64) error {
    // gRPC 调用业务服务
    ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
    defer cancel()
    
    // 注入元数据
    ctx = metadata.AppendToOutgoingContext(ctx,
        "user-id", strconv.FormatInt(conn.UserID, 10),
        "device-id", conn.DeviceID,
        "client-ip", conn.ClientIP,
        "trace-id", traceIdFromCtx(ctx),
    )
    
    resp, err := g.bizClient(svc).Invoke(ctx, body)
    if err != nil {
        // 失败回包
        return g.sendError(conn, mapError(err), seqId)
    }
    
    // 成功回包
    return g.sendResponse(conn, resp, seqId)
}
```

## 7.2 下行投递（业务 → 客户端）

下行投递有两种触发：

### 模式 A：业务服务主动 RPC 推送
```go
// Deliver 服务调用 Gateway 的 Push API
func (g *Gateway) Push(ctx context.Context, req *PushReq) (*PushResp, error) {
    conn := g.connMgr.GetByDevice(req.UserID, req.DeviceID)
    if conn == nil {
        return &PushResp{Code: ROUTE_NOT_FOUND}, nil
    }
    
    if conn.State.Load() != StateAuthed {
        return &PushResp{Code: NOT_AUTHED}, nil
    }
    
    frame := buildFrame(CmdPushMsg, req.Body)
    select {
    case conn.writeChan <- frame:
        return &PushResp{Code: OK}, nil
    case <-time.After(100 * time.Millisecond):
        return &PushResp{Code: WRITE_TIMEOUT}, nil
    }
}
```

### 模式 B：通过 Kafka 消费推送
```go
// Gateway 也可以订阅 Kafka，自己消费消息
// 优点：解耦
// 缺点：每个 Gateway 都要消费，浪费资源
// 通常用模式 A
```

## 7.3 投递失败处理

```go
func (d *Deliver) DeliverWithRetry(serverMsgId int64, userID int64) {
    devices := d.queryUserDevices(userID)
    
    for _, dev := range devices {
        gateway := d.statusSvc.GetGateway(userID, dev.DeviceID)
        if gateway == "" {
            // 离线 → 写 inbox + push
            continue
        }
        
        resp, err := d.gatewayClient(gateway).Push(...)
        switch {
        case err != nil || resp.Code == GATEWAY_DOWN:
            // 网关挂 → 重新查路由
            d.refreshRoute(userID, dev.DeviceID)
            d.retry(serverMsgId, userID, dev.DeviceID)
            
        case resp.Code == ROUTE_NOT_FOUND:
            // 用户已不在该网关 → 用户已掉线 → 走离线
            d.writeOffline(serverMsgId, userID, dev.DeviceID)
            
        case resp.Code == OK:
            metrics.DeliverSuccess.Inc()
        }
    }
}
```

---

# 8. 心跳与保活

## 8.1 心跳协议

```
客户端 → 服务端: HEARTBEAT (空 body 或 包含 last_received_seq)
服务端 → 客户端: HEARTBEAT_ACK (server_time + 可携带通知)

间隔: 客户端 30s 发送一次
超时: 服务端 60s 未收到 → 关闭连接
```

## 8.2 自适应心跳（移动端节电）

```go
// 客户端逻辑
func (sdk *SDK) AdaptiveHeartbeat() {
    interval := 30 * time.Second
    
    for {
        select {
        case <-time.After(interval):
            sdk.sendHeartbeat()
        case <-sdk.networkChange:
            // 网络变化重置
            interval = 30 * time.Second
        }
        
        // 根据网络质量调整
        if sdk.networkQuality == Poor {
            interval = 15 * time.Second
        } else if sdk.foreground == false {
            interval = 60 * time.Second  // 后台延长
        }
    }
}
```

## 8.3 服务端心跳超时

```go
func (g *Gateway) heartbeatChecker() {
    ticker := time.NewTicker(10 * time.Second)
    for range ticker.C {
        now := time.Now().Unix()
        g.connMgr.connsByID.Range(func(_, v interface{}) bool {
            conn := v.(*Conn)
            if now - conn.LastActive.Load() > 60 {
                log.Info("heartbeat timeout", "userID", conn.UserID)
                conn.Close()  // 触发清理
            }
            return true
        })
    }
}
```

## 8.4 心跳带 piggyback

心跳是高频信令，可以携带：
- 客户端最大已收 server_msg_id（用于服务端清理待 ACK 队列）
- 已读批量上报
- 网络质量统计

```protobuf
message Heartbeat {
  int64 last_received_msg_id = 1;
  repeated ReadReport reads = 2;
  NetworkInfo net_info = 3;
}
```

---

# 9. 安全设计

## 9.1 TLS 配置

```yaml
# Nginx / Envoy 前置 TLS
ssl_protocols: TLSv1.3 TLSv1.2
ssl_ciphers: ECDHE+AESGCM:ECDHE+CHACHA20
ssl_prefer_server_ciphers: on
ssl_session_cache: shared:SSL:50m
ssl_session_timeout: 1d
ssl_session_tickets: off
ocsp_stapling: on
```

## 9.2 鉴权流程

```
LOGIN 帧:
  {
    user_id, device_id, app_id, 
    token,            ← 由独立 Auth 服务签发的 JWT
    timestamp,        ← 防重放
    nonce,            ← 一次性
    sign              ← HMAC(token + timestamp + nonce, secret)
  }

Gateway 处理:
  1. 校验 timestamp 与服务器时间差 < 60s
  2. 校验 nonce 未使用 (Redis SET NX, 60s TTL)
  3. 校验 token 签名（公钥）
  4. 校验 token 过期
  5. 校验 token claim (user_id 一致)
  6. 通过 → State = Authed
```

## 9.3 防 DDoS

| 手段 | 措施 |
|---|---|
| SYN Flood | SYN Cookie + RST 限速 |
| 假连接 | 5s 内必须完成 TLS 握手 |
| 半开连接 | 单 IP 半开数限制 |
| 慢速攻击 | 读超时 30s |
| 资源耗尽 | 单实例最大连接数硬限 |
| 反射放大 | QUIC 路径验证强制开启 |

## 9.4 数据加密

```
传输层: TLS 1.3 强制
端到端 (可选): 业务层加密
  - 群: 协商组密钥
  - 私聊: Signal 协议 (X3DH + Double Ratchet)
媒体: 文件上传 OSS 时单独加密
```

## 9.5 防伪造与重放

```
所有上行请求必须带:
  client_msg_id (重放识别)
  timestamp     (时间窗口校验)
  
服务端:
  Redis SETNX 当 client_msg_id 已存在 → 重放或重试
  时间窗口 ±5min 之外 → 拒绝
```

---

# 10. 故障与容灾

## 10.1 故障矩阵

| 故障 | 影响 | 处理 |
|---|---|---|
| 单 Gateway 进程崩溃 | 该机连接全断 | K8s 重启 + 客户端重连 |
| 单 Gateway 慢 | 部分用户体验差 | LB 健康检查降权 |
| 业务服务挂 | 上行失败 | 客户端 retry，最多 3 次 |
| Redis 挂 | 状态查询失败 | 本地缓存兜底，30s 后清除 |
| LB 挂 | 整体不可达 | 多 LB 集群，DNS 切换 |
| 整集群挂 | 区域不可用 | 客户端 fallback 到其他集群 |

## 10.2 优雅降级

```go
// 配置中心动态开关
var (
    KillTyping     atomic.Bool  // 关闭"输入中"
    KillReadNotify atomic.Bool  // 关闭已读回执
    ReducedQPS     atomic.Bool  // 整体限流减半
)

func (g *Gateway) handleTyping(...) {
    if KillTyping.Load() {
        return nil  // 直接丢弃，不报错
    }
    // ...
}
```

## 10.3 客户端重连策略

```
首次失败:    1s 后重试
连续失败:    指数退避 1s → 2s → 4s → 8s → 16s (max 60s)
+ 抖动:      ±20% random
+ 总次数限:  无限重试，但提示用户
+ 触发条件:  网络变化 / 后台前台切换 → 立即重试
```

## 10.4 Gateway 自我保护

```go
// 内存压力大 → 拒绝新连接
func (g *Gateway) memoryPressureCheck() {
    var stats runtime.MemStats
    runtime.ReadMemStats(&stats)
    
    if stats.Alloc > MemThreshold {
        g.rejectNewConn.Store(true)
        log.Warn("memory pressure, rejecting new conns")
    }
}

// CPU 满载 → 减少处理
func (g *Gateway) cpuPressureCheck() {
    if cpuUsage() > 0.85 {
        g.rateLimitFactor.Store(0.5)  // 阈值减半
    }
}
```

---

# 11. 性能与调优

## 11.1 OS 调优

```bash
# /etc/sysctl.conf
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 600
net.ipv4.ip_local_port_range = 1024 65535
fs.file-max = 2000000
fs.nr_open = 2000000

# 用户限制
* soft nofile 1000000
* hard nofile 1000000

# BBR 拥塞控制
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq

# UDP buffer (QUIC)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
```

## 11.2 Go 运行时调优

```go
// main.go
func init() {
    runtime.GOMAXPROCS(runtime.NumCPU())
    debug.SetGCPercent(50)        // 更激进 GC
    debug.SetMemoryLimit(28 << 30) // 28GB 软上限
}
```

## 11.3 关键性能指标

| 指标 | 目标 |
|---|---|
| 单实例连接数 | 100K |
| 单实例 QPS（处理） | 50K |
| 单连接消息延迟（Gateway 内） | < 1ms |
| 单连接 CPU 占用 | < 0.001% |
| 内存/连接 | < 200KB |
| TLS 握手延迟 P99 | < 100ms |
| QUIC 0-RTT 比例 | > 50% |

## 11.4 性能压测脚本（参考）

```yaml
# 工具：k6 / locust / 自研
场景:
  - 100K 长连接保活测试
  - 50K QPS 消息上行
  - 100K QPS 消息下行
  - QUIC 切网络迁移延迟测试
  - 重连风暴模拟
  - 慢速攻击检测
```

---

# 12. 关键数据结构

## 12.1 服务发现注册

```yaml
# etcd: /im/gateway/instances/{instance_id}
{
  "instance_id": "gw-east-001",
  "server_id": 42,             # CID 编码用
  "host": "10.1.2.3",
  "port_quic": 443,
  "port_ws": 443,
  "region": "east",
  "az": "east-1a",
  "version": "v1.2.3",
  "started_at": 1710000000,
  "max_conns": 100000,
  "current_conns": 75432,
  "status": "healthy"
}
TTL: 30s, 心跳续约
```

## 12.2 投递路由元数据

```yaml
# Redis: presence:user:{userId}
{
  "ios:DEV001": {
    "gateway": "gw-east-001",
    "conn_id": 12345,
    "login_at": 1710000000,
    "last_active": 1710001234
  },
  "android:DEV002": {...}
}
TTL: 30s
```

## 12.3 配置项

```yaml
gateway:
  listen:
    quic: ":443"
    ws: ":443"
  tls:
    cert: "/etc/im/cert.pem"
    key: "/etc/im/key.pem"
  limits:
    max_conns_per_instance: 100000
    max_conns_per_ip: 50
    max_conns_per_user: 5
    max_frame_size: 1048576
    msg_rate_per_conn: 10
    sig_rate_per_conn: 50
  timeouts:
    tls_handshake: 5s
    login: 10s
    heartbeat: 60s
    write: 5s
  upstream:
    msg_write: "msg-write.svc:9000"
    msg_sync: "msg-sync.svc:9000"
    counter: "counter.svc:9000"
  cid:
    server_id: 42
    generation: 1
    rotation_interval: 24h
  observability:
    metrics_port: 9090
    pprof_port: 6060
    log_level: info
```

---

**文档结束**

*Version 1.0 | Gateway 详细设计*