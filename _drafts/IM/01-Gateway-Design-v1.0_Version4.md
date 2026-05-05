# Gateway 详细设计文档 v1.0

> 上游文档：IM 系统技术设计规范  
> 适用范围：长连接接入网关（WebSocket / QUIC）  
> 单实例目标：10 万并发连接 / 5 万 QPS 消息转发

---

## 目录

1. 总体架构
2. 连接生命周期管理
3. 协议解析与编解码
4. QUIC 连接迁移
5. 限流细节
6. 心跳与保活
7. 消息路由
8. 多端互踢与会话管理
9. 容错与故障处理
10. 监控指标
11. 性能优化
12. 部署与配置

---

# 1. 总体架构

## 1.1 模块划分

```
┌─────────────────────────────────────────────┐
│              Gateway 进程                    │
├─────────────────────────────────────────────┤
│  Listener (TCP/QUIC)                        │
│    ├─ TLS Handshake                         │
│    └─ Protocol Detect                       │
├─────────────────────────────────────────────┤
│  Connection Manager                         │
│    ├─ Connection Table                      │
│    ├─ Auth Module                           │
│    └─ Heartbeat Module                      │
├─────────────────────────────────────────────┤
│  Protocol Codec                             │
│    ├─ Frame Parser                          │
│    ├─ Protobuf Decoder                      │
│    └─ Compression                           │
├─────────────────────────────────────────────┤
│  Rate Limiter (Local)                       │
├─────────────────────────────────────────────┤
│  Router                                     │
│    ├─ Upstream RPC Client                   │
│    └─ Downstream Push                       │
├─────────────────────────────────────────────┤
│  Metrics / Tracing / Log                    │
└─────────────────────────────────────────────┘
```

## 1.2 进程模型

- 主进程：监听 + accept
- IO 线程池：N = CPU 核数（处理读写）
- Worker 线程池：M = 2×CPU（处理业务转发）
- 单连接绑定到单 IO 线程（避免锁竞争）

## 1.3 关键数据结构

```go
type Connection struct {
    ConnID      uint64           // 连接全局 ID
    UserID      int64
    DeviceID    string
    AppID       int32
    Protocol    Protocol         // WS/QUIC
    Socket      net.Conn         // 或 quic.Stream
    
    LoginTime   int64
    LastHeartbeat int64
    Status      ConnStatus       // CONNECTING/AUTHED/CLOSED
    
    SendChan    chan []byte      // 发送队列（带背压）
    
    // 限流
    MsgBucket   *TokenBucket
    SignalBucket *TokenBucket
    InBytes     *SlidingWindow
    
    // 业务
    SessionInfo *Session
    Subs        []int64          // 订阅的 conv_id（按需）
    
    mu sync.RWMutex
}

type ConnectionManager struct {
    byConnID  *sync.Map           // ConnID → *Connection
    byUser    *sync.Map           // UserID → []*Connection (多端)
    
    counters  Counters
}
```

---

# 2. 连接生命周期管理

## 2.1 状态机

```
[INIT]
  │ accept
  ▼
[CONNECTED]
  │ TLS handshake OK
  ▼
[TLS_DONE]
  │ LOGIN frame
  ▼
[AUTHENTICATING]
  │ token verified
  ▼
[AUTHED] ←──────┐
  │             │ heartbeat / msg
  ├─────────────┘
  │ LOGOUT / timeout / error
  ▼
[CLOSING]
  │ flush / cleanup
  ▼
[CLOSED]
```

## 2.2 接入流程

```
1. accept 连接 (TCP/QUIC)
2. TLS handshake (1-RTT 或 0-RTT)
3. 等待客户端 LOGIN frame (10s 超时)
4. 鉴权:
   - 解析 token (JWT/自有)
   - 调用 auth-service 验证
   - 返回 user_id / device_id
5. 注册到 ConnectionManager
   - byConnID[connId] = conn
   - byUser[userId] += conn
6. 上报到 status shard:
   SET presence:dev:{user}:{device} {gw,connId} EX 30
7. 通知其他端 (多端登录)
8. 进入消息处理循环
```

## 2.3 鉴权细节

```go
func (g *Gateway) authenticate(req *LoginReq) (*Identity, error) {
    // 1. 本地缓存
    if id := g.authCache.Get(req.Token); id != nil {
        return id, nil
    }
    
    // 2. 远程验证（带超时）
    ctx, cancel := context.WithTimeout(g.ctx, 500*time.Millisecond)
    defer cancel()
    
    id, err := g.authClient.Verify(ctx, req.Token)
    if err != nil {
        return nil, err
    }
    
    // 3. 缓存（短 TTL，token 撤销时仍有窗口）
    g.authCache.Set(req.Token, id, 60*time.Second)
    return id, nil
}
```

## 2.4 多端登录策略

| 策略 | 说明 |
|---|---|
| **同设备类型互踢** | 新 iOS 登录踢旧 iOS |
| **不同设备共存** | iOS + Android + PC 可同时在线 |
| **PC 与 Web 互踢** | PC 在线时 Web 受限 |

实现：

```go
func (m *ConnectionManager) Register(c *Connection) {
    existing := m.byUser.Load(c.UserID)
    
    for _, old := range existing {
        if shouldKick(old, c) {
            old.Send(KickFrame{Reason: "new_login"})
            old.Close()
        }
    }
    
    m.byUser.Append(c.UserID, c)
}
```

## 2.5 连接关闭

### 主动关闭（正常）
```
1. 收到 LOGOUT frame
2. 发送 LOGOUT_ACK
3. 标记 status = CLOSING
4. flush SendChan
5. 关闭底层 socket
6. 从 ConnectionManager 移除
7. DELETE presence:dev:{user}:{device}
8. 异步通知 status shard
```

### 异常关闭
```
触发条件:
  - 心跳超时 (60s)
  - 读写错误
  - 协议错误
  - 客户端 RST

处理:
  - 不发 LOGOUT（已断）
  - 走清理流程
  - 记录原因到 metric
```

### 优雅下线（运维）
```
1. 配置中心下发 drain 标记
2. Gateway 停止接受新连接（LB 摘除）
3. 现有连接发 RECONNECT 提示
4. 等待 30s 让客户端切换
5. 强制关闭剩余连接
6. 进程退出
```

---

# 3. 协议解析与编解码

## 3.1 帧格式

```
+----+--------+--------+----------+----------+------------------+
| M  | Ver    | Cmd    | Flags    | SeqId    | Length           |
| 1B | 1B     | 2B     | 2B       | 8B       | 4B               |
+----+--------+--------+----------+----------+------------------+
| Body (Protobuf, max 1MB)                                       |
+---------------------------------------------------------------+

总头部: 18 字节
```

### Flags 位定义
```
bit 0:  压缩 (0=none, 1=gzip)
bit 1:  加密 (0=none, 1=app-level)
bit 2:  优先级 (0=normal, 1=high)
bit 3-7: 保留
```

## 3.2 解析流程

```go
func (c *Connection) readLoop() {
    reader := bufio.NewReaderSize(c.socket, 64*1024)
    
    for {
        // 1. 读头部 18 字节
        var header [18]byte
        if _, err := io.ReadFull(reader, header[:]); err != nil {
            c.closeWithError(err)
            return
        }
        
        // 2. 校验 Magic
        if header[0] != 0x4D {
            c.closeWithError(ErrBadMagic)
            return
        }
        
        // 3. 解析头部
        ver := header[1]
        cmd := binary.BigEndian.Uint16(header[2:4])
        flags := binary.BigEndian.Uint16(header[4:6])
        seqId := binary.BigEndian.Uint64(header[6:14])
        length := binary.BigEndian.Uint32(header[14:18])
        
        // 4. 校验长度
        if length > MaxFrameSize {
            c.closeWithError(ErrFrameTooLarge)
            return
        }
        
        // 5. 读 body
        body := make([]byte, length)
        if _, err := io.ReadFull(reader, body); err != nil {
            c.closeWithError(err)
            return
        }
        
        // 6. 解压
        if flags & FlagCompressed != 0 {
            body = decompress(body)
        }
        
        // 7. 限流（消息维度）
        if !c.MsgBucket.Allow(1) {
            c.sendErr(seqId, ErrRateLimited)
            continue
        }
        
        // 8. 投递到业务处理
        c.dispatch(cmd, seqId, body)
    }
}
```

## 3.3 写入流程

```go
func (c *Connection) writeLoop() {
    writer := bufio.NewWriterSize(c.socket, 256*1024)
    flushTimer := time.NewTicker(5 * time.Millisecond)
    
    for {
        select {
        case msg, ok := <-c.SendChan:
            if !ok {
                return  // 已关闭
            }
            if _, err := writer.Write(msg); err != nil {
                c.closeWithError(err)
                return
            }
            
            // 累积发送（小消息合并）
            if len(c.SendChan) == 0 || writer.Buffered() > 32*1024 {
                writer.Flush()
            }
            
        case <-flushTimer.C:
            if writer.Buffered() > 0 {
                writer.Flush()
            }
            
        case <-c.closeChan:
            writer.Flush()
            return
        }
    }
}
```

## 3.4 背压控制

```go
SendChan capacity = 256 frames

// 发送时检查
func (c *Connection) Send(frame []byte) error {
    select {
    case c.SendChan <- frame:
        return nil
    case <-time.After(100 * time.Millisecond):
        // 发送队列堵塞，可能客户端慢
        return ErrSendBlocked
    }
}

// 慢客户端策略
当 SendChan 堵塞超过 3 次 → 关闭连接
避免单个慢客户端拖累内存
```

## 3.5 大消息处理

```
单帧最大 1MB
> 1MB 的消息：
  - 文件/图片走 HTTP 上传到对象存储
  - IM 消息只带 URL + 元数据
  - Gateway 不传输大文件
```

---

# 4. QUIC 连接迁移

## 4.1 CID 设计

```
Connection ID 格式 (16 bytes):
+-------+----------+------------+----------------+
| Ver   | ServerID | Generation | Encrypted      |
| 1B    | 2B       | 1B         | 12B            |
+-------+----------+------------+----------------+

整体用 AES-128 加密（LB 与 Gateway 共享密钥）
```

## 4.2 CID 生成

```go
func (g *Gateway) generateCID() ConnectionID {
    plaintext := make([]byte, 16)
    plaintext[0] = ProtocolVersion
    binary.BigEndian.PutUint16(plaintext[1:3], g.serverID)
    plaintext[3] = g.generation
    rand.Read(plaintext[4:])  // 12 字节随机
    
    // 加密
    ciphertext := g.aesBlock.Encrypt(plaintext)
    return ciphertext
}
```

## 4.3 LB 解析（eBPF/XDP）

```c
// 简化的 eBPF 程序逻辑
SEC("xdp")
int route_quic(struct xdp_md *ctx) {
    // 1. 解析 UDP 包
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;
    
    // 2. 跳到 UDP payload
    struct quic_header *qh = parse_quic(data);
    
    // 3. 提取 DCID (long header 或 short header)
    __u8 dcid[16];
    extract_dcid(qh, dcid);
    
    // 4. 解密 (AES 在 eBPF 不易，可由 LB 代理做)
    // 或：使用未加密的 server_id 字段（牺牲一点隐私）
    __u16 server_id = decrypt_and_extract(dcid);
    
    // 5. 查路由表
    __u32 *backend_ip = bpf_map_lookup_elem(&route_map, &server_id);
    
    // 6. 重定向
    return bpf_redirect(*backend_ip, 0);
}
```

实际实现可参考：
- Cloudflare quiche + Katran
- Envoy QUIC + 自定义 cluster

## 4.4 备用 CID 池

```go
// 握手完成后立即发送备用 CID
func (s *Session) sendNewConnectionIDs(count int) {
    for i := 0; i < count; i++ {
        cid := s.gateway.generateCID()
        token := generateStatelessResetToken(cid)
        s.cidPool[cid] = token
        
        s.queue.Send(&NewConnectionIDFrame{
            SequenceNumber: s.nextCIDSeq,
            ConnectionID:   cid,
            ResetToken:     token,
        })
        s.nextCIDSeq++
    }
}

// 启动时发 8 个备用 CID
const InitialCIDPoolSize = 8
```

## 4.5 路径验证

```go
func (s *Session) handlePacketFromNewPath(addr net.Addr, frame Frame) {
    if s.activePath.Equal(addr) {
        s.handleNormal(frame)
        return
    }
    
    // 检测到新路径
    if !s.knownCIDs.Contains(frame.DCID) {
        return  // 未知 CID，丢弃
    }
    
    // 启动路径验证
    challenge := generateRandom8Bytes()
    s.pendingPaths[addr] = &PendingPath{
        Challenge: challenge,
        Started:   time.Now(),
    }
    
    s.sendOnPath(addr, &PathChallengeFrame{Data: challenge})
    
    // 超时 5s 未收到 response → 验证失败
}

func (s *Session) handlePathResponse(addr net.Addr, resp *PathResponseFrame) {
    pending := s.pendingPaths[addr]
    if pending == nil {
        return
    }
    
    if !bytes.Equal(pending.Challenge, resp.Data) {
        return
    }
    
    // 验证通过，切换路径
    s.activePath = addr
    delete(s.pendingPaths, addr)
    
    // 通知业务层"路径变更但连接不变"
    s.metrics.PathMigration.Inc()
    
    // 弃用旧 CID
    s.retireOldCIDs()
}
```

## 4.6 防 NAT Rebinding 误判

```go
// NAT rebinding：IP 不变，端口变了
// 处理：
//   - 视为路径变更，走路径验证
//   - 但不增加迁移计数（区别于真实迁移）

func (s *Session) classifyMigration(oldAddr, newAddr net.Addr) string {
    if oldAddr.IP.Equal(newAddr.IP) {
        return "nat_rebinding"
    }
    if sameSubnet(oldAddr.IP, newAddr.IP) {
        return "minor_migration"
    }
    return "full_migration"  // 真正的网络切换
}
```

---

# 5. 限流细节

## 5.1 多层限流

```
连接级:
  ├─ 消息频率 (10/s, 突发 30)
  ├─ 信令频率 (50/s)
  ├─ 入流量带宽 (50KB/s)
  └─ 出流量带宽 (100KB/s)

实例级:
  ├─ 总连接数 (100K)
  ├─ 建连速率 (1000/s)
  └─ 总消息 QPS (50K)

IP 级 (本地缓存):
  ├─ 同 IP 连接数 (50)
  └─ 同 IP 建连速率 (10/s)
```

## 5.2 令牌桶实现

```go
type TokenBucket struct {
    capacity    int64
    rate        int64  // tokens per second
    tokens      int64
    lastRefill  int64  // unix nano
    mu          sync.Mutex
}

func (tb *TokenBucket) Allow(n int64) bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now().UnixNano()
    elapsed := now - tb.lastRefill
    
    // 补充令牌
    tb.tokens = min(tb.capacity, tb.tokens + elapsed*tb.rate/1e9)
    tb.lastRefill = now
    
    if tb.tokens >= n {
        tb.tokens -= n
        return true
    }
    return false
}
```

## 5.3 IP 限流（本地 LRU）

```go
type IPLimiter struct {
    cache *lru.Cache  // IP → *TokenBucket
    
    // 配置
    connRate     int64
    connBurst    int64
    msgRate      int64
    msgBurst     int64
}

func (l *IPLimiter) AllowConnect(ip string) bool {
    bucket := l.getOrCreate(ip + ":conn", l.connRate, l.connBurst)
    return bucket.Allow(1)
}

// 内存: 100万 IP × 100B = 100MB，足够
// LRU 清理 30 分钟未活跃 IP
```

## 5.4 限流响应

```protobuf
message ErrorResp {
  int32 code = 1;
  string message = 2;
  int32 retry_after_ms = 3;  // 建议重试间隔
}
```

```go
func (c *Connection) sendRateLimited(seqId uint64, retryAfter time.Duration) {
    c.Send(&ErrorFrame{
        SeqId:        seqId,
        Code:         ERR_RATE_LIMITED,
        Message:      "rate limited",
        RetryAfterMs: int32(retryAfter.Milliseconds()),
    })
}
```

## 5.5 连续超限处置

```go
连续 10 次超限 (1 分钟内):
  → 触发"风控提示"事件
  → 上报 user.behavior topic
  → 服务端可能临时封禁

连续 100 次超限:
  → 立即关闭连接
  → 1 分钟内拒绝该 IP/User 重连
```

## 5.6 全局保护开关

```go
// 通过配置中心（etcd）下发
type RateLimitConfig struct {
    Enabled         bool
    GlobalQPSLimit  int64
    PerUserMsgRate  int64
    PerConnMsgRate  int64
    EmergencyMode   bool   // 紧急模式：阈值减半
}

// Watch 配置变化
go g.config.Watch("rate_limit", func(c *RateLimitConfig) {
    g.applyRateLimit(c)
})
```

---

# 6. 心跳与保活

## 6.1 心跳协议

```
客户端 → 服务端: HEARTBEAT (Cmd=0x0003)
                带 client_time, last_recv_seq

服务端 → 客户端: HEARTBEAT_ACK
                带 server_time, server_msgs_pending
```

## 6.2 心跳间隔

| 网络环境 | 间隔 |
|---|---|
| WiFi 良好 | 60s |
| 移动网络 | 45s |
| 弱网 | 30s |
| 后台 | 平台限制（iOS ~30min） |

客户端自适应调整，服务端 60s 超时。

## 6.3 服务端检测

```go
// 每个 connection 关联心跳定时器
func (c *Connection) heartbeatLoop() {
    ticker := time.NewTicker(10 * time.Second)
    defer ticker.Stop()
    
    for {
        select {
        case <-ticker.C:
            elapsed := time.Now().UnixNano() - c.LastHeartbeat
            if elapsed > 60*int64(time.Second) {
                c.closeWithError(ErrHeartbeatTimeout)
                return
            }
            
        case <-c.closeChan:
            return
        }
    }
}
```

## 6.4 心跳与 NAT

```
NAT 超时通常 30s ~ 5min
心跳间隔 < NAT 超时 / 2

iOS 后台限制：
  - 普通 socket 几分钟就被回收
  - 用 silent push 唤醒应用
  - 或用 VoIP push（受限）
```

## 6.5 携带数据

心跳可以 piggyback 一些低优数据：

```protobuf
message Heartbeat {
  int64 client_time = 1;
  int64 last_recv_seq = 2;          // 已收到的最大 seq
  repeated int64 read_reports = 3;   // 批量已读
  string typing_in_conv = 4;         // 正在输入
}
```

---

# 7. 消息路由

## 7.1 上行消息（C → S）

```go
func (g *Gateway) handleSendMsg(c *Connection, req *SendMsgReq) {
    // 1. 风控前置
    if g.risk.IsBlocked(c.UserID) {
        c.sendErr(ERR_BLOCKED)
        return
    }
    
    // 2. 业务校验
    if err := validate(req); err != nil {
        c.sendErr(ERR_INVALID)
        return
    }
    
    // 3. 转发到 MsgWrite 服务
    ctx, _ := context.WithTimeout(g.ctx, 2*time.Second)
    resp, err := g.msgWriteClient.Send(ctx, &SendReq{
        UserID:      c.UserID,
        DeviceID:    c.DeviceID,
        ClientMsgID: req.ClientMsgID,
        ConvID:      req.ConvID,
        Content:     req.Content,
    })
    
    // 4. 返回 ACK
    if err != nil {
        c.sendErr(ERR_INTERNAL)
        return
    }
    c.Send(&SendMsgResp{
        ClientMsgID:  req.ClientMsgID,
        ServerMsgID:  resp.ServerMsgID,
        Seq:          resp.VisibleSeq,
    })
}
```

## 7.2 下行推送（S → C）

```go
// Deliver 服务调用 Gateway gRPC
service Gateway {
  rpc Push(PushReq) returns (PushResp);
}

func (g *Gateway) Push(ctx context.Context, req *PushReq) (*PushResp, error) {
    // 1. 查找连接
    conns := g.connMgr.GetByUser(req.UserID)
    if len(conns) == 0 {
        return &PushResp{Status: "NOT_FOUND"}, nil
    }
    
    // 2. 按设备过滤
    var targets []*Connection
    for _, c := range conns {
        if matchDevice(c, req.TargetDevices) {
            targets = append(targets, c)
        }
    }
    
    // 3. 推送
    success := 0
    for _, c := range targets {
        if err := c.Send(req.Frame); err != nil {
            continue
        }
        success++
    }
    
    if success == 0 {
        return &PushResp{Status: "ALL_FAILED"}, nil
    }
    return &PushResp{Status: "OK", DeliveredTo: int32(success)}, nil
}
```

## 7.3 路由失效处理

```go
// Deliver 收到 NOT_FOUND/ALL_FAILED:
//   → 强制刷新 status shard
//   → 若仍无在线 → 进 inbox + push
```

---

# 8. 多端互踢与会话管理

## 8.1 设备类型

```
device_type: "ios" | "android" | "pc" | "web" | "mac"
```

## 8.2 互踢规则

```go
func shouldKick(old, new *Connection) bool {
    if old.DeviceType == new.DeviceType {
        // 同类型互踢
        return true
    }
    
    // PC 与 Web 互斥（业务规则）
    if (old.DeviceType == "pc" && new.DeviceType == "web") ||
       (old.DeviceType == "web" && new.DeviceType == "pc") {
        return true
    }
    
    return false
}
```

## 8.3 踢人流程

```
1. 旧连接发 KICK frame (reason="new_login_same_device")
2. 客户端收到 → 显示"账号在其他设备登录"
3. 旧连接 5s 后自动关闭
4. 状态服务清理旧设备记录
```

---

# 9. 容错与故障处理

## 9.1 上游 RPC 故障

```go
// 重试策略
type RetryConfig struct {
    MaxAttempts: 2
    InitialBackoff: 50ms
    MaxBackoff: 200ms
    RetryableErrors: [UNAVAILABLE, DEADLINE_EXCEEDED]
}

// 熔断
type CircuitBreaker struct {
    Threshold:      50%   // 失败率
    Window:         10s
    MinRequests:    20
    OpenTimeout:    5s
}
```

## 9.2 内存压力

```
连接数 > 80%: 拒绝新连接，返回 SERVICE_UNAVAILABLE
连接数 > 90%: 主动关闭最不活跃的 1% 连接
内存 > 80%:   触发 GC，警告
内存 > 90%:   拒绝新连接
```

## 9.3 panic 隔离

```go
func (c *Connection) safeDispatch(fn func()) {
    defer func() {
        if r := recover(); r != nil {
            log.Errorf("panic in conn %d: %v", c.ConnID, r)
            c.metrics.Panic.Inc()
            c.closeWithError(ErrInternal)
        }
    }()
    fn()
}
```

## 9.4 优雅关闭

```go
func (g *Gateway) Shutdown(ctx context.Context) error {
    // 1. 标记 not ready (LB 摘除)
    g.health.SetNotReady()
    
    // 2. 等待 LB 摘除生效 (10s)
    time.Sleep(10 * time.Second)
    
    // 3. 通知所有连接迁移
    g.connMgr.Each(func(c *Connection) {
        c.Send(&ReconnectFrame{Reason: "graceful_shutdown"})
    })
    
    // 4. 等待客户端切换 (30s)
    time.Sleep(30 * time.Second)
    
    // 5. 强制关闭剩余连接
    g.connMgr.CloseAll()
    
    // 6. 关闭 listener
    g.listener.Close()
    
    return nil
}
```

---

# 10. 监控指标

## 10.1 关键指标

| 指标 | 类型 | 用途 |
|---|---|---|
| `gateway_connections_active` | Gauge | 当前连接数 |
| `gateway_connections_total` | Counter | 总建连数 |
| `gateway_handshake_duration` | Histogram | 握手耗时 |
| `gateway_auth_duration` | Histogram | 鉴权耗时 |
| `gateway_msg_recv_total{cmd}` | Counter | 接收消息数 |
| `gateway_msg_send_total` | Counter | 发送消息数 |
| `gateway_msg_latency` | Histogram | 端到端消息延迟 |
| `gateway_rate_limited_total{reason}` | Counter | 限流触发 |
| `gateway_quic_migration{result}` | Counter | QUIC 迁移结果 |
| `gateway_send_blocked_total` | Counter | 发送背压 |
| `gateway_heartbeat_timeout_total` | Counter | 心跳超时 |
| `gateway_panic_total` | Counter | panic 次数 |

## 10.2 SLO

```
连接成功率 > 99.9%
单机 P99 延迟 < 5ms (网关内部)
QUIC 迁移成功率 > 95%
心跳超时率 < 0.1%
```

---

# 11. 性能优化

## 11.1 内存优化

```
- sync.Pool 复用 frame buffer
- 连接对象池化
- 避免 string ↔ []byte 转换
- 使用 unsafe.String (Go 1.20+)
```

## 11.2 网络优化

```
- TCP_NODELAY = true（禁 Nagle）
- SO_REUSEPORT 多进程监听
- 写入合并（5ms flush）
- 零拷贝 sendfile（大对象）
```

## 11.3 锁优化

```
- 连接表分桶（256 个 sync.Map）
- 连接级状态用 atomic
- 避免长时间持锁
- 读多写少用 sync.RWMutex
```

## 11.4 GC 调优

```
GOGC=200 (默认 100，降低 GC 频率)
GOMEMLIMIT=24GiB
```

---

# 12. 部署与配置

## 12.1 资源规格

```yaml
resources:
  cpu: 16
  memory: 32Gi
  network: 10Gbps

limits:
  max_connections: 100000
  max_qps_per_conn: 50
```

## 12.2 配置文件

```yaml
gateway:
  listen:
    quic: 0.0.0.0:443
    ws:   0.0.0.0:443
  tls:
    cert: /etc/im/tls.crt
    key:  /etc/im/tls.key
  
  auth:
    timeout: 500ms
    cache_ttl: 60s
  
  heartbeat:
    timeout: 60s
    
  rate_limit:
    msg_rate: 10
    msg_burst: 30
    signal_rate: 50
    ip_conn_limit: 50
    ip_conn_rate: 10
  
  quic:
    cid_pool_size: 8
    max_idle_timeout: 60s
  
  upstream:
    msg_write: msg-write-svc:9090
    auth: auth-svc:9090
    presence: presence-svc:9090
```

## 12.3 健康检查

```
GET /health
  - 200: ready
  - 503: not_ready (drain)

GET /metrics  (Prometheus)
GET /debug/pprof/  (only internal)
```

---

**文档结束** | Version 1.0