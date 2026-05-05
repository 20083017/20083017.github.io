# IM Gateway 详细设计文档 v1.0

> 适用范围：千万并发 IM 接入网关  
> 单实例承载：5~10 万长连接  
> 集群规模：50~200 实例

---

## 目录

1. [职责与定位](#1-职责与定位)
2. [整体架构](#2-整体架构)
3. [连接管理](#3-连接管理)
4. [协议解析](#4-协议解析)
5. [QUIC 与连接迁移](#5-quic-与连接迁移)
6. [限流细节](#6-限流细节)
7. [心跳与保活](#7-心跳与保活)
8. [推送与下行链路](#8-推送与下行链路)
9. [优雅启停与故障处理](#9-优雅启停与故障处理)
10. [安全与防攻击](#10-安全与防攻击)
11. [性能调优](#11-性能调优)
12. [关键数据结构](#12-关键数据结构)

---

# 1. 职责与定位

## 1.1 核心职责

- 维护客户端长连接（WebSocket / QUIC）
- 协议解析、加解密、压缩
- 用户鉴权、会话维护
- 上行消息：解析后转发到业务层
- 下行消息：从业务层接收并推送到对应连接
- 连接级限流、防刷
- 心跳维护、断线检测
- QUIC 连接迁移
- 上报在线状态

## 1.2 不做什么

- 不做消息持久化（业务层负责）
- 不做消息路由决策（业务层 / 投递服务负责）
- 不做权限/风控决策（仅作信号上报）
- 不做内容审核

## 1.3 设计原则

- **单连接 = 单 goroutine/线程**（用户态调度）或 **epoll + worker pool**
- **零拷贝**：协议帧尽量直接转发到下游
- **本地优先**：限流/状态判定走本地内存
- **快速失败**：异常立即断开，不阻塞主循环
- **无状态可重启**：连接状态不持久化（断了就重连）

---

# 2. 整体架构

## 2.1 单��例内部模块

```
┌─────────────────────────────────────────────────┐
│  网络层 (netpoll / epoll / QUIC stack)           │
└──────────────┬──────────────────────────────────┘
               │
       ┌───────▼───────┐
       │ 连接接收器     │ ← TLS 握手 / QUIC 握手
       └───────┬───────┘
               │
       ┌───────▼───────┐
       │ 鉴权与会话建立  │ ← Login + Token 验证
       └───────┬───────┘
               │
       ┌───────▼───────────────────────────┐
       │ 连接管理器 ConnManager             │
       │ ┌───────────┬───────────┐         │
       │ │ ConnTable │ UserIndex │         │
       │ └───────────┴───────────┘         │
       └───────┬───────────────────────────┘
               │
       ┌───────▼───────────────────────────┐
       │ 帧解析器 + 限流器                   │
       └───────┬───────────────────────────┘
               │
       ┌───────▼───────────────────────────┐
       │ 上行调度 → 业务层 (RPC/MQ)         │
       └───────────────────────────────────┘

       ┌───────────────────────────────────┐
       │ 下行调度 ← 投递服务 (RPC/MQ)        │
       └───────┬───────────────────────────┘
               │
       ┌───────▼───────────────────────────┐
       │ 推送编码器 + 写出                   │
       └───────────────────────────────────┘
```

## 2.2 进程模型

推荐 Go / Rust / C++ 实现：
- Go: `gnet` / `netpoll` + goroutine pool
- Rust: `tokio` + `quinn` (QUIC)
- C++: 自研 epoll + 线程池

## 2.3 部署形态

- 单实例：16C32G，处理 5~10 万连接
- 端口：443 (TCP for WSS) + 443 (UDP for QUIC)
- 协议：WSS / HTTP3+WebTransport / 自研 QUIC

---

# 3. 连接管理

## 3.1 连接生命周期

```
[CONNECTING] → [HANDSHAKE] → [AUTHENTICATING] → [ESTABLISHED]
                                                      │
                                              ┌───────┼────────┐
                                              ▼       ▼        ▼
                                         [ACTIVE]  [IDLE]  [MIGRATING]
                                              │
                                              ▼
                                         [CLOSING] → [CLOSED]
```

## 3.2 连接表数据结构

### 主表 `ConnTable`
```go
type Connection struct {
    ConnID       uint64        // 全局唯一连接 ID
    UserID       int64
    DeviceID     string
    Protocol     uint8          // 1:WS 2:QUIC
    RemoteAddr   string
    
    Socket       net.Conn       // 或 quic.Stream
    ReadBuf      []byte
    WriteBuf     chan []byte    // 异步写
    
    LoginAt      int64
    LastActiveAt int64          // 最后活跃时间
    LastPingAt   int64
    
    State        uint8          // 状态机
    
    // 限流
    MsgBucket    *TokenBucket
    SignalBucket *TokenBucket
    
    // 关闭
    closeCh      chan struct{}
    closeOnce    sync.Once
}

type ConnTable struct {
    sync.RWMutex
    conns map[uint64]*Connection      // connID → conn
}
```

### 用户索引 `UserIndex`
```go
type UserIndex struct {
    sync.RWMutex
    // userId → [deviceId → connId]
    byUser map[int64]map[string]uint64
}
```

### 容量
```
单实例 10万连接：
- ConnTable:    10万 × 1KB = 100MB
- 缓冲区:        10万 × 64KB = 6.4GB（read+write buf）
- 总内存预算:    16~24GB（含 GC 余量）
```

## 3.3 连接 ID 生成

```go
ConnID = (instanceID << 48) | (timestampMS << 16) | sequence
```

- `instanceID` 16bit：网关实例 ID（来自服务发现）
- `timestampMS` 32bit：毫秒时间戳
- `sequence` 16bit：实例内自增

保证：
- 全局唯一
- 包含网关身份（便于排查）
- 有序

## 3.4 单用户多端策略

```go
// 同一 userId+deviceId 重复登录：踢老连接
existing := userIndex.Get(userId, deviceId)
if existing != nil {
    sendKick(existing, "logged_in_elsewhere")
    closeConnection(existing)
}

// 同一 userId 不同 device：共存
// 限制：单用户最多 5 个设备
if userIndex.DeviceCount(userId) >= 5 {
    sendKick(oldestDevice, "too_many_devices")
}
```

## 3.5 连接关闭

```go
func (c *Connection) Close(reason string) {
    c.closeOnce.Do(func() {
        // 1. 状态机切到 CLOSING
        c.State = CLOSING
        
        // 2. 通知业务层下线
        presenceClient.Offline(c.UserID, c.DeviceID, c.ConnID)
        
        // 3. 关闭网络
        c.Socket.Close()
        
        // 4. 移出表
        connTable.Remove(c.ConnID)
        userIndex.Remove(c.UserID, c.DeviceID)
        
        // 5. 释放资源
        close(c.closeCh)
        c.State = CLOSED
        
        // 6. 监控
        metrics.ConnClosed.Inc(reason)
    })
}
```

---

# 4. 协议解析

## 4.1 协议帧格式

```
+----+--------+--------+----------+----------+------------------+
| M  | Ver    | Cmd    | Flags    | SeqId    | Length           |
| 1B | 1B     | 2B     | 2B       | 8B       | 4B               |
+----+--------+--------+----------+----------+------------------+
| Body (Protobuf)                                                |
+----------------------------------------------------------------+

总头长: 18 字节
最大 Body: 1MB（超过断连）
```

## 4.2 Flags 位定义

```
bit 0:  COMPRESSED   (1 = body 经 zstd 压缩)
bit 1:  ENCRYPTED    (1 = 业务层加密)
bit 2:  PRIORITY     (1 = 高优先级)
bit 3:  ACK_REQUIRED (1 = 需要业务 ACK)
bit 4:  BATCH        (1 = body 包含多个子帧)
bit 5-15: 预留
```

## 4.3 解析流程

```go
func parseFrame(reader io.Reader) (*Frame, error) {
    header := make([]byte, 18)
    if _, err := io.ReadFull(reader, header); err != nil {
        return nil, err
    }
    
    if header[0] != 0x4D {
        return nil, ErrBadMagic
    }
    
    f := &Frame{
        Version: header[1],
        Cmd:     binary.BigEndian.Uint16(header[2:4]),
        Flags:   binary.BigEndian.Uint16(header[4:6]),
        SeqID:   binary.BigEndian.Uint64(header[6:14]),
        Length:  binary.BigEndian.Uint32(header[14:18]),
    }
    
    if f.Length > MAX_BODY_SIZE {
        return nil, ErrBodyTooLarge
    }
    
    f.Body = make([]byte, f.Length)
    if _, err := io.ReadFull(reader, f.Body); err != nil {
        return nil, err
    }
    
    if f.Flags & FLAG_COMPRESSED != 0 {
        f.Body, err = zstdDecompress(f.Body)
    }
    
    return f, nil
}
```

## 4.4 错误处理

| 错误 | 处理 |
|---|---|
| Magic 错 | 立即断连 |
| Version 不支持 | 返回 ERR_VERSION，断连 |
| Body 超限 | 返回 ERR_TOO_LARGE，断连 |
| 解压失败 | 返回 ERR_DECOMPRESS，断连 |
| Protobuf 解析失败 | 返回 ERR_PROTOCOL，记录但不断连 |
| 限流命中 | 返回 ERR_RATE_LIMIT，不断连 |

## 4.5 上下行队列

### 上行（接收）
```go
// 直接 RPC 转发到业务层（msg-write 服务）
func handleUplink(c *Connection, frame *Frame) {
    switch frame.Cmd {
    case CMD_SEND_MSG:
        resp, err := msgWriteClient.Send(ctx, &SendMsgReq{...})
        sendDownlink(c, buildAck(frame.SeqID, resp))
    case CMD_HEARTBEAT:
        sendPong(c)
    case CMD_READ_REPORT:
        // 异步转发，不等响应
        go counterClient.ReportRead(...)
    }
}
```

### 下行（推送）
```go
// 单连接异步写队列
func (c *Connection) sendAsync(data []byte) bool {
    select {
    case c.WriteBuf <- data:
        return true
    case <-time.After(100 * time.Millisecond):
        // 写超时 → 慢消费者，断开
        c.Close("slow_consumer")
        return false
    }
}
```

写缓冲队列大小：单连接 256~1024 条。  
满了即认为客户端处理不过来，主动断开。

---

# 5. QUIC 与连接迁移

## 5.1 双协议支持

```go
type GatewayConfig struct {
    WSPort   int  // 443 TCP
    QUICPort int  // 443 UDP
}

// 同 443 端口：UDP 走 QUIC，TCP 走 WSS
```

## 5.2 QUIC 连接 ID 设计

```
CID 格式 (16 bytes):
+--------+----------+------------+--------------------+
| Ver    | ServerID | Generation | Random + AES加密     |
| 1B     | 2B       | 1B         | 12B                 |
+--------+----------+------------+--------------------+

ServerID:    网关实例 ID（用于 LB 路由）
Generation:  CID 代际（扩缩容时区分）
后 12B:      加密随机数
```

加密用 LB 与 Gateway 共享密钥，AES-128-ECB。

## 5.3 CID 生成与发放

```go
func newCID(serverID uint16, gen uint8) []byte {
    cid := make([]byte, 16)
    cid[0] = CID_VERSION
    binary.BigEndian.PutUint16(cid[1:3], serverID)
    cid[3] = gen
    rand.Read(cid[4:16])
    
    // 加密整体 (除 version)
    aesEncrypt(sharedKey, cid[1:])
    return cid
}

// 握手后发放 8 个备用 CID
func onHandshakeComplete(conn *quic.Connection) {
    for i := 0; i < 8; i++ {
        conn.SendNewConnectionID(newCID(...))
    }
}
```

## 5.4 迁移检测

```go
func onPacketReceived(conn *quic.Connection, pkt *Packet) {
    if pkt.RemoteAddr != conn.RemoteAddr {
        // 新地址 → 启动路径验证
        conn.StartPathValidation(pkt.RemoteAddr)
    }
}

func onPathValidated(conn *quic.Connection, newAddr net.Addr) {
    log.Info("connection migrated", 
        "conn_id", conn.ConnID,
        "old_addr", conn.RemoteAddr,
        "new_addr", newAddr)
    
    conn.RemoteAddr = newAddr
    
    // 重要：业务状态保持不变
    // 不重新登录，不重新订阅
    metrics.MigrationSuccess.Inc()
}
```

## 5.5 LB 解 CID 路由（伪代码）

```c
// eBPF/XDP 在 LB 内核态运行
int xdp_quic_route(struct xdp_md *ctx) {
    // 提取 UDP payload 第一个字节判断是否 QUIC
    if (!is_quic(packet)) return XDP_PASS;
    
    // 提取 DCID
    uint8_t dcid[16];
    extract_dcid(packet, dcid);
    
    // AES 解密
    aes_decrypt_ecb(shared_key, dcid + 1, dcid + 1);
    
    // 提取 server_id
    uint16_t server_id = bpf_ntohs(*(uint16_t*)(dcid + 1));
    
    // 查路由表
    struct backend *be = lookup_backend(server_id);
    if (!be) return XDP_DROP;
    
    // 转发
    redirect_to(be);
    return XDP_REDIRECT;
}
```

## 5.6 网关扩缩容时 CID 处理

### 扩容
- 新网关启动后，分配新 ServerID
- 旧 CID 仍指向老网关，老连接不受影响
- 新连接 CID 含新 ServerID，落到新网关

### 缩容
1. 标记网关为"不接受新连接"
2. Dispatcher 不再返回该网关
3. 等待存量连接自然消亡或心跳超时
4. 30 分钟后强制下线

## 5.7 NAT Rebinding

NAT 端口映射变更（IP 不变）：

```go
// 同 IP 不同端口 → 轻量验证
func handleNATRebinding(conn *quic.Connection, newPort int) {
    if conn.RemoteIP == newPort.IP {
        // 简化路径验证
        conn.SendPathChallenge(quickValidation = true)
    }
}
```

---

# 6. 限流细节

## 6.1 限流维度（Gateway 本地）

| 维度 | 算法 | 阈值 | 超限处理 |
|---|---|---|---|
| 单 IP 连接数 | 计数 | 50 | 拒绝握手 |
| 单 IP 建连/秒 | 令牌桶 | 10/s | 拒绝握手 |
| 单连接消息频率 | 令牌桶 | 10/s 突发 30 | 丢包，10 次后断开 |
| 单连接信令频率 | 令牌桶 | 50/s | 丢包 |
| 单连接拉取频率 | 令牌桶 | 5/s | 返回 429 |
| 单连接出流量 | 滑动窗口 | 100KB/s | 限速 |
| 单连接入流量 | 滑动窗口 | 50KB/s | 断开 |

## 6.2 令牌桶实现

```go
type TokenBucket struct {
    capacity  int64
    rate      float64    // 令牌/秒
    tokens    int64      // 当前令牌
    lastTime  int64      // 上次更新
    mu        sync.Mutex
}

func (b *TokenBucket) TryAcquire(n int64) bool {
    b.mu.Lock()
    defer b.mu.Unlock()
    
    now := time.Now().UnixMilli()
    elapsed := float64(now - b.lastTime) / 1000.0
    
    b.tokens = min(b.capacity, b.tokens + int64(elapsed * b.rate))
    b.lastTime = now
    
    if b.tokens >= n {
        b.tokens -= n
        return true
    }
    return false
}
```

无锁版本（生产推荐）：

```go
type AtomicTokenBucket struct {
    capacity int64
    rate     int64
    state    atomic.Uint64   // 高 32 位 tokens, 低 32 位 timestamp
}

func (b *AtomicTokenBucket) TryAcquire(n int64) bool {
    for {
        old := b.state.Load()
        tokens := int64(old >> 32)
        last := int64(old & 0xFFFFFFFF)
        
        now := time.Now().Unix()
        elapsed := now - last
        tokens = min(b.capacity, tokens + elapsed * b.rate)
        
        if tokens < n {
            return false
        }
        
        newState := uint64(tokens - n) << 32 | uint64(now)
        if b.state.CompareAndSwap(old, newState) {
            return true
        }
    }
}
```

## 6.3 IP 限流

```go
type IPLimiter struct {
    sync.RWMutex
    connCount    map[string]int          // IP → 连接数
    connectRate  map[string]*TokenBucket // IP → 建连令牌桶
}

func (l *IPLimiter) AllowConnect(ip string) bool {
    l.RLock()
    count := l.connCount[ip]
    bucket := l.connectRate[ip]
    l.RUnlock()
    
    if count >= MAX_CONN_PER_IP {
        return false
    }
    if bucket != nil && !bucket.TryAcquire(1) {
        return false
    }
    return true
}
```

## 6.4 限流命中后的处理

```go
func handleFrame(c *Connection, f *Frame) {
    // 不同帧用不同桶
    var bucket *TokenBucket
    switch f.Cmd {
    case CMD_SEND_MSG:
        bucket = c.MsgBucket
    case CMD_HEARTBEAT, CMD_READ_REPORT:
        bucket = c.SignalBucket
    }
    
    if bucket != nil && !bucket.TryAcquire(1) {
        c.RateLimitHit++
        sendError(c, f.SeqID, ERR_RATE_LIMITED)
        
        // 连续命中 10 次 → 断开（疑似攻击）
        if c.RateLimitHit > 10 {
            c.Close("rate_limit_abuse")
            metrics.AbusiveConn.Inc()
        }
        return
    }
    
    c.RateLimitHit = 0
    processFrame(c, f)
}
```

## 6.5 全局协调（防雪崩）

接入层限流是本地，但要避免**集群层面的集体过载**：

- 网关每秒上报本地 QPS 到中心 Prometheus
- 中央通过配置中心动态下调阈值
- 紧急时全网关接收 `kill.rate_to=3` 配置，所有连接限速到 3/s

---

# 7. 心跳与保活

## 7.1 心跳协议

```protobuf
message Heartbeat {
  int64 client_ts = 1;     // 客户端时间戳
  int32 sequence = 2;       // 心跳序号
}

message HeartbeatAck {
  int64 client_ts = 1;
  int64 server_ts = 2;
}
```

## 7.2 心跳间隔策略

| 场景 | 客户端间隔 | 服务端超时 |
|---|---|---|
| WiFi 稳定 | 60s | 90s |
| 移动网络 | 30s | 45s |
| 弱网 | 15s | 30s |
| 后台 | 180~270s | 300s |

客户端根据网络状况动态调整。

## 7.3 服务端心跳检测

```go
// 全局心跳扫描器，每秒扫一次
func heartbeatChecker() {
    ticker := time.NewTicker(1 * time.Second)
    for range ticker.C {
        now := time.Now().Unix()
        connTable.Range(func(c *Connection) {
            if now - c.LastActiveAt > IDLE_TIMEOUT {
                c.Close("heartbeat_timeout")
            }
        })
    }
}
```

注意：用 **分桶轮询** 避免一次扫描全部连接：

```go
// 把 10 万连接分到 60 个桶，每秒扫 1 个桶
buckets[connID % 60].Range(...)
```

## 7.4 piggyback 优化

心跳包可以捎带：
- 已读上报（最大 read_seq）
- 客户端状态（前后台）
- 网络类型（WiFi/4G）

减少独立请求次数。

---

# 8. 推送与下行链路

## 8.1 投递服务 → Gateway

投递服务通过 RPC（如 gRPC）调用 Gateway：

```protobuf
service GatewayPush {
  rpc Push(PushRequest) returns (PushResponse);
  rpc BatchPush(BatchPushRequest) returns (BatchPushResponse);
}

message PushRequest {
  int64 user_id = 1;
  string device_id = 2;       // 可空，空 = 推所有设备
  bytes  frame = 3;            // 已编码的帧
  int32  priority = 4;
}
```

## 8.2 Gateway 内部分发

```go
func (g *Gateway) Push(req *PushRequest) error {
    // 1. 查本地连接表
    conns := userIndex.Get(req.UserID, req.DeviceID)
    if len(conns) == 0 {
        return ErrUserNotOnline   // 投递服务收到后走离线流程
    }
    
    // 2. 推送到每个设备
    for _, conn := range conns {
        if !conn.sendAsync(req.Frame) {
            // 慢消费者已断开，下次会更新状态
        }
    }
    return nil
}
```

## 8.3 批量推送优化

群消息要给 1000 个在线成员推：

```go
func (g *Gateway) BatchPush(req *BatchPushRequest) {
    // 按设备并行推
    var wg sync.WaitGroup
    sem := make(chan struct{}, 100) // 并发 100
    
    for _, target := range req.Targets {
        sem <- struct{}{}
        wg.Add(1)
        go func(t *Target) {
            defer wg.Done()
            defer func() { <-sem }()
            g.PushOne(t)
        }(target)
    }
    wg.Wait()
}
```

## 8.4 写缓冲管理

每个连接独立 channel：

```go
WriteBuf chan []byte  // size = 256
```

写流程：

```go
func (c *Connection) writeLoop() {
    batch := make([][]byte, 0, 16)
    timer := time.NewTimer(5 * time.Millisecond)
    
    for {
        select {
        case data := <-c.WriteBuf:
            batch = append(batch, data)
            // 批量聚合最多 5ms
            if len(batch) >= 16 {
                flush(c.Socket, batch)
                batch = batch[:0]
            }
        case <-timer.C:
            if len(batch) > 0 {
                flush(c.Socket, batch)
                batch = batch[:0]
            }
            timer.Reset(5 * time.Millisecond)
        case <-c.closeCh:
            return
        }
    }
}
```

## 8.5 慢消费者处理

```
WriteBuf 满 → sendAsync 立即返回 false
连续 3 次满 → 断开连接
监控指标: slow_consumer_count
```

---

# 9. 优雅启停与故障处理

## 9.1 启动流程

```
1. 加载配置（端口、密钥、阈值）
2. 连接服务发现（etcd），注册自己
3. 加载 SSL 证书 / QUIC 密钥
4. 监听端口（443 TCP + 443 UDP）
5. 启动各 worker（连接 / 心跳 / 限流统计）
6. 健康检查 endpoint 返回 200
7. 调度服务开始路由流量到本实例
```

## 9.2 优雅关闭

```
1. 健康检查返回 503（LB 摘除）
2. 拒绝新连接（仅 listen socket，已建连接不受影响）
3. 通知所有连接：发送 "server_shutdown" 提示
4. 等待 30 秒（让客户端主动断开 + 重连到其他网关）
5. 关闭存量连接
6. 等待业务请求结束（最多 60s）
7. 进程退出
```

```go
func (g *Gateway) Shutdown(ctx context.Context) {
    g.healthy = false
    g.listener.Close()
    
    // 通知所有客户端
    connTable.Range(func(c *Connection) {
        c.sendAsync(buildShutdownNotice())
    })
    
    select {
    case <-time.After(30 * time.Second):
    case <-ctx.Done():
    }
    
    connTable.Range(func(c *Connection) {
        c.Close("server_shutdown")
    })
}
```

## 9.3 故障自愈

| 故障 | 自愈机制 |
|---|---|
| 单连接卡死 | 心跳超时 → 关闭 |
| 写阻塞 | 写超时 100ms → 关闭 |
| 内存泄漏 | RSS 超阈值 → 触发 K8s 重启 |
| Goroutine 泄漏 | 监控 + alert |
| Socket 文件句柄耗尽 | ulimit + 监控 |

## 9.4 panic recovery

```go
func safeGo(fn func()) {
    go func() {
        defer func() {
            if r := recover(); r != nil {
                log.Error("panic", "stack", debug.Stack())
                metrics.PanicCount.Inc()
            }
        }()
        fn()
    }()
}
```

每个连接处理 goroutine 都用 safeGo 包裹。

---

# 10. 安全与防攻击

## 10.1 鉴权

```
1. 客户端先调用 Login API（HTTPS）获取 access_token
2. WebSocket / QUIC 握手时 Header 携带 token
3. Gateway 验证 token（JWT 本地验签 / 调 auth 服务）
4. 验证通过 → ESTABLISHED
   失败 → 立即断连
```

token 包含：
- userId
- deviceId
- expireAt
- signature

## 10.2 防攻击措施

### TLS 强制
```
TLS 1.3 only
强制 HTTPS / WSS
QUIC 自带 TLS 1.3
```

### DDoS 防御
- L4 LB 前置防火墙
- SYN cookies
- IP 限流
- 异常行为加入临时黑名单

### CC 攻击
- 单 IP 频率限流（建连 + 消息）
- 异常 token 惩罚（5 次失败 → IP 黑名单 1 小时）

### 重放攻击
- 业务层消息带 client_msg_id 幂等
- 重要操作带 nonce

### 协议混淆
- Magic 字节校验
- 版本号校验
- 异常立即断开

## 10.3 黑名单

```go
type Blacklist struct {
    sync.RWMutex
    bannedIPs    map[string]int64   // IP → expireAt
    bannedUsers  map[int64]int64    // userId → expireAt
}

// 定期从风控系统同步
func syncBlacklist() {
    ticker := time.NewTicker(30 * time.Second)
    for range ticker.C {
        list, _ := riskClient.GetBlacklist()
        blacklist.Replace(list)
    }
}
```

---

# 11. 性能调优

## 11.1 关键参数

### Linux 内核
```bash
# 文件句柄
ulimit -n 1000000

# TCP 参数
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 5
net.core.somaxconn = 32768
net.ipv4.tcp_max_syn_backlog = 32768
net.core.netdev_max_backlog = 65535

# 端口范围
net.ipv4.ip_local_port_range = 10000 65535

# UDP buffer (QUIC)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
```

### Go 参数
```go
runtime.GOMAXPROCS(runtime.NumCPU())
debug.SetGCPercent(50)  // 降低 GC 触发频率
debug.SetMaxStack(8 * 1024 * 1024)
```

### JVM 参数（如用 Java/Netty）
```
-XX:+UseG1GC
-XX:MaxGCPauseMillis=50
-XX:+ParallelRefProcEnabled
-Xms16g -Xmx16g
```

## 11.2 性能基线

| 指标 | 目标 |
|---|---|
| 单实例连接数 | 5~10 万 |
| 单实例消息转发 QPS | 50K |
| CPU 使用率 | < 60% |
| 内存使用 | < 24GB |
| P99 转发延迟 | < 5ms |
| 心跳成功率 | > 99.9% |
| 连接成功率 | > 99% |

## 11.3 Profiling

- pprof：CPU / Heap / Goroutine
- 线上常态化采样
- 异常时 dump

---

# 12. 关键数据结构

## 12.1 Connection（已在 §3.2 给出）

## 12.2 ConnTable 性能优化

千万连接的网关集群中，单实例 10 万连接的 map 操作要避免锁竞争。

### 分段锁
```go
const SHARDS = 256

type ShardedConnTable struct {
    shards [SHARDS]struct {
        sync.RWMutex
        m map[uint64]*Connection
    }
}

func (t *ShardedConnTable) Get(connID uint64) *Connection {
    s := &t.shards[connID % SHARDS]
    s.RLock()
    defer s.RUnlock()
    return s.m[connID]
}
```

## 12.3 内存池

```go
var bufPool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 4096)
    },
}

// 读 buffer 复用，避免 GC 压力
buf := bufPool.Get().([]byte)
defer bufPool.Put(buf)
```

---

# 文档维护

- 文档负责人：接入层架构组
- 评审周期：季度
- 关联文档：QUIC 网关运维手册、协议规范文档

*Version 1.0 | 最后更新：2026-05-04*