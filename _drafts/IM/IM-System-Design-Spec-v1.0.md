# 千万并发 IM 系统技术设计规范 v1.0

> 适用规模：千万级 DAU / 百万级在线 / 单日百亿消息  
> 文档目标：作为架构、开发、SRE、安全的统一参考  
> 版本：1.0  
> 状态：设计基线（Baseline）

---

## 目录

1. [整体架构设计](#1-整体架构设计)
2. [负载均衡与接入](#2-负载均衡与接入)
3. [消息协议设计](#3-消息协议设计)
4. [存储选型与配置](#4-存储选型与配置)
5. [IM 数据表设计](#5-im-数据表设计)
6. [Redis Key 设计规范](#6-redis-key-设计规范)
7. [Kafka Topic 设计](#7-kafka-topic-设计)
8. [幂等性设计](#8-幂等性设计)
9. [异常处理与 Fallback](#9-异常处理与-fallback)
10. [风控设计](#10-风控设计)
11. [流量控制与限流](#11-流量控制与限流)
12. [跨地域部署](#12-跨地域部署)
13. [可观测性与 SLA](#13-可观测性与-sla)
14. [灰度发布与上线](#14-灰度发布与上线)
15. [附录：容量规划与基线指标](#15-附录容量规划与基线指标)

---

# 1. 整体架构设计

## 1.1 设计目标与约束

| 维度 | 目标 |
|---|---|
| 在线用户 | 百万级单地域，千万级全球 |
| 消息吞吐 | 写入 50 万 QPS / 投递 200 万 QPS（含 fanout） |
| 端到端延迟 | P99 < 500ms（同地域）/ P99 < 1s（跨地域） |
| 可用性 | 99.95%（年停机 < 4.4h） |
| 消息可靠性 | 不丢、不重（业务视角） |
| 单地域故障 | RTO < 5min，RPO < 30s |

## 1.2 分层架构

```
┌──────────────────────────────────────────────────┐
│  端层 (Client)                                    │
│  iOS / Android / Web / PC / 小程序                 │
└──────────────────────┬───────────────────────────┘
                       │ WSS / QUIC / HTTPS
┌──────────────────────▼───────────────────────────┐
│  接入层 (Edge)                                    │
│  调度服务 + 4层LB + 7层LB + 接入网关 (Gateway)      │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│  业务层 (Logic) — 无状态                          │
│  写入服务 / 投递服务 / 同步服务 / 状态服务 / 撤回...   │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│  数据层 (Data)                                    │
│  Redis / MySQL/TiDB / Kafka / HBase / ES / OSS    │
└──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│  基础设施 (Infra)                                 │
│  K8s / 服务发现 (etcd) / 配置中心 / 监控 / 日志       │
└──────────────────────────────────────────────────┘
```

## 1.3 核心服务划分

| 服务 | 职责 | 状态 |
|---|---|---|
| **Dispatcher** | 接入调度（返回最优网关） | 无状态 |
| **Gateway** | 长连接维护、协议解析、限流 | 有状态（连接） |
| **MsgWrite** | 消息落库、分配 seq、写 outbox | 无状态 |
| **MsgSync** | 同步增量、历史拉取 | 无状态 |
| **Presence** | 在线状态查询/上报 | 弱状态 |
| **Deliver** | 在线消息投递 | 无状态 |
| **Push** | 离线 Push（APNs/FCM/厂商） | 无状态 |
| **InboxWriter** | 写离线收件箱 | 无状态 |
| **CounterSvc** | 未读计数 / 游标 | 无状态 |
| **MentionSvc** | @ 消息处理 | 无状态 |
| **GroupSvc** | 群成员管理 | 无状态 |
| **Recall** | 撤回 / 编辑 | 无状态 |
| **Risk** | 风控决策（异步） | 无状态 |
| **Audit** | 审计 / 合规 | 无状态 |
| **OutboxWorker** | 扫 outbox 投 Kafka | 有状态（任务） |

## 1.4 关键设计原则

1. **接入层有状态，业务层无状态**：连接归属网关，业务可任意扩缩容
2. **消息走"实时通道 + 拉取"双路径**：实时投递保即时性，拉取保最终一致
3. **Outbox 模式保证写库与发 MQ 一致**：业务事务内写 outbox，Worker 异步投 Kafka
4. **多 seq 分离**：`global_seq`（全局唯一）+ `visible_seq`（连续，未读用）
5. **每层独立幂等**：从客户端到下游，5 道幂等防线
6. **故障隔离**：大 V / 大群独立 topic + 独立 consumer
7. **任何节点都能挂**：连接重连、shard 主备、跨集群切流

---

# 2. 负载均衡与接入

## 2.1 接入调度（Dispatcher）

客户端启动时，先请求调度服务获取最佳接入入口。

### 接口

```http
GET /v1/dispatch?user_id=...&device_id=...&client_ip=...
Response:
{
  "endpoints": [
    {"protocol": "quic", "host": "edge-east-1.im.example.com", "port": 443, "priority": 1},
    {"protocol": "wss",  "host": "edge-east-2.im.example.com", "port": 443, "priority": 2}
  ],
  "ttl": 3600
}
```

### 调度策略

| 维度 | 策略 |
|---|---|
| 地理位置 | GeoIP → 最近接入区域 |
| 集群健康 | 排除 unhealthy 集群 |
| 容量负载 | 按网关连接数加权 |
| 协议偏好 | QUIC 优先，WSS 兜底 |
| 用户粘性 | 同一用户优先返回上次成功的入口 |
| 灰度策略 | 按 user_id hash 分流 |

## 2.2 多层 LB 架构

```
Client
  │
  ▼
[DNS/HTTPDNS]    ← 智能解析（按地理/网络）
  │
  ▼
[L4 LB: LVS/DPVS]    ← 传输层负载（百万 QPS）
  │
  ▼
[L7 LB: Envoy/Nginx]  ← TLS 卸载、HTTP/3、限流（仅短连接走）
  │
  ▼
[Gateway 集群]        ← 长连接终结
```

### 长连接路径
长连接不走 L7（避免双重 TLS），直接 L4 LB → Gateway。

### QUIC 连接迁移
- L4 LB 必须基于 **QUIC Connection ID** 路由（不是四元组）
- Gateway 生成 CID 时编码 `server_id`，LB 解 CID 提取后转发
- 实现选型：eBPF/XDP (Katran) / DPVS 自研模块

详见 [QUIC 连接迁移设计文档]。

## 2.3 Gateway 容量与配置

| 配置项 | 值 |
|---|---|
| 单 Gateway 连接数 | 50K~100K |
| 单 Gateway CPU | 16 核 |
| 单 Gateway 内存 | 32GB |
| 心跳间隔 | 客户端 30s，服务端 60s 超时 |
| 单连接 KeepAlive | TCP_KEEPALIVE 60s |
| 单连接读 buffer | 64KB |
| 单连接写 buffer | 256KB |
| 单连接最大消息 | 1MB（超过走 HTTP 上传） |

---

# 3. 消息协议设计

## 3.1 协议分层

```
应用层:  IM 业务协议 (Protobuf 二进制)
传输层:  WebSocket / QUIC HTTP/3
安全层:  TLS 1.3
```

## 3.2 协议帧结构

```
+----+--------+--------+----------+----------+------------------+
| M  | Ver    | Cmd    | Flags    | SeqId    | Length           |
| 1B | 1B     | 2B     | 2B       | 8B       | 4B               |
+----+--------+--------+----------+----------+------------------+
| Body (Protobuf)                                                |
+---------------------------------------------------------------+

M:      Magic 0x4D ("M")
Ver:    协议版本
Cmd:    指令类型
Flags:  位标志（压缩/加密/优先级）
SeqId:  请求 ID（回包匹配）
```

## 3.3 主要指令（Cmd）

| Cmd | 名称 | 方向 |
|---|---|---|
| 0x0001 | LOGIN | C → S |
| 0x0002 | LOGOUT | C → S |
| 0x0003 | HEARTBEAT | 双向 |
| 0x0010 | SEND_MSG | C → S |
| 0x0011 | MSG_ACK | S → C |
| 0x0012 | MSG_PUSH | S → C |
| 0x0013 | MSG_RECALL | C → S |
| 0x0014 | MSG_EDIT | C → S |
| 0x0020 | SYNC_PULL | C → S |
| 0x0021 | SYNC_NOTIFY | S → C |
| 0x0030 | READ_REPORT | C → S |
| 0x0031 | READ_NOTIFY | S → C |
| 0x0040 | TYPING | C → S |
| 0x0050 | KICK | S → C |

## 3.4 消息体协议（核心 Protobuf）

```protobuf
// 发送消息
message SendMsgReq {
  string client_msg_id = 1;       // 客户端幂等 ID
  int64  conv_id       = 2;
  int32  msg_type      = 3;       // 1:text 2:image 3:file 4:audio 5:video 6:custom
  bytes  content       = 4;       // 序列化后的消息内容
  int64  send_time     = 5;       // 客户端时间戳（仅参考）
  int32  priority      = 6;       // 0:normal 1:high
  Mentions mentions    = 7;
}

message SendMsgResp {
  string client_msg_id = 1;
  int64  server_msg_id = 2;
  int64  global_seq    = 3;
  int64  visible_seq   = 4;
  int64  server_time   = 5;
  int32  status        = 6;       // 0:success 1:blocked 2:rate_limited
}

message Mentions {
  repeated MentionItem items = 1;
  bool all = 2;
}

message MentionItem {
  int64  user_id = 1;
  int32  offset  = 2;
  int32  length  = 3;
  string name_at_send = 4;
}

// 推送消息（服务端 → 客户端）
message MsgPush {
  int64  conv_id = 1;
  int64  global_seq = 2;
  int64  visible_seq = 3;
  int64  server_msg_id = 4;
  int64  sender_id = 5;
  int32  msg_type = 6;
  bytes  content = 7;
  int64  send_time = 8;
  Mentions mentions = 9;
}
```

## 3.5 协议优化

- **压缩**：消息体 > 4KB 启用 gzip/zstd
- **批量**：一次握手内发送多条消息（batch frame）
- **延迟 ACK**：客户端心跳 piggyback 已读上报
- **二进制 ID**：所有 ID 用 int64，不用字符串

---

# 4. 存储选型与配置

## 4.1 存储矩阵

| 数据类型 | 存储 | 选型 | 理由 |
|---|---|---|---|
| 消息正文 | 分布式 SQL | TiDB / MySQL 分库分表 | 强一致、唯一约束、易运维 |
| 历史消息 | KV | HBase / Cassandra | 大容量、低成本 |
| 用户/群资料 | RDB | MySQL | 关系型、低频写 |
| 在线状态 | KV | Redis Cluster | 高频读写、TTL |
| 未读游标 | KV | Redis Cluster + DB 兜底 | 单值幂等更新 |
| @ 索引 | 分布式 SQL | TiDB | 关系查询 + 分片 |
| 文件/图片 | 对象存储 | OSS / S3 / COS | 海量、CDN 加速 |
| 全文搜索 | 倒排索引 | Elasticsearch | 历史消息搜索 |
| 事件流 | MQ | Kafka | 高吞吐、可重放 |
| 配置 | KV | etcd | 强一致、Watch |

## 4.2 MySQL/TiDB 配置

### 容量规划
```
单表行数上限:   5 亿（MySQL）/ 无限（TiDB）
分库数:         32（按 conv_id hash）
分表数:         单库 16 张（共 512 张）
冷热分离:       30 天热表 → 归档表
```

### 关键参数
```ini
[mysqld]
innodb_buffer_pool_size = 32G
innodb_log_file_size = 2G
innodb_flush_log_at_trx_commit = 1
sync_binlog = 1
binlog_format = ROW
max_connections = 5000
innodb_thread_concurrency = 32
```

### 主从架构
- 1 主 2 从（同地域）
- 1 异地灾备（异步）
- 自动切主：MHA / Orchestrator / TiDB 内置

## 4.3 Redis 配置

### 集群拓扑
```
Redis Cluster: 64 主 + 64 从
单节点内存:    32GB
maxmemory-policy: volatile-lru
```

### 多实例分组
| 集群 | 用途 | 节点数 |
|---|---|---|
| `redis-presence` | 在线状态 | 16 主 |
| `redis-counter` | 未读游标、计数 | 16 主 |
| `redis-cache` | 通用热缓存 | 32 主 |
| `redis-rate` | 限流计数 | 8 主 |
| `redis-mention` | @ 索引 | 8 主 |

### 关键参数
```ini
maxmemory-policy: volatile-lru
timeout: 0
tcp-keepalive: 60
appendonly: yes
appendfsync: everysec
cluster-enabled: yes
cluster-require-full-coverage: no
```

## 4.4 Kafka 配置

### 集群拓扑
```
Brokers:    12 节点（同地域），3 副本
Zookeeper:  5 节点 / 或 KRaft 模式
单 Broker:  16 核 / 64GB / 4TB SSD
```

### 关键参数
```properties
# Broker
num.network.threads=8
num.io.threads=16
log.retention.hours=168
log.segment.bytes=1073741824
default.replication.factor=3
min.insync.replicas=2
unclean.leader.election.enable=false
auto.create.topics.enable=false

# Producer
acks=all
enable.idempotence=true
max.in.flight.requests.per.connection=5
compression.type=lz4
linger.ms=10
batch.size=65536

# Consumer
enable.auto.commit=false
isolation.level=read_committed
max.poll.records=500
fetch.max.bytes=10485760
```

## 4.5 HBase（历史消息冷存储）

```
RegionServer:    32 节点
单 Region 大小:   10GB
RowKey 设计:      reverse(conv_id) + visible_seq
压缩:             SNAPPY
TTL:              永久 / 按业务策略
```

---

# 5. IM 数据表设计

## 5.1 消息主表 `im_message`

```sql
CREATE TABLE im_message (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  app_id          INT NOT NULL,
  conv_id         BIGINT NOT NULL,
  sender_id       BIGINT NOT NULL,
  client_msg_id   VARCHAR(64) NOT NULL,
  server_msg_id   BIGINT NOT NULL,
  global_seq      BIGINT NOT NULL,
  visible_seq     BIGINT,                    -- NULL 表示不计未读
  msg_type        TINYINT NOT NULL,
  content         JSON NOT NULL,
  mention_all     TINYINT DEFAULT 0,
  mention_count   SMALLINT DEFAULT 0,
  reply_to_id     BIGINT,                    -- 引用回复
  status          TINYINT DEFAULT 0,         -- 0:normal 1:recalled 2:edited 3:blocked
  version         INT DEFAULT 1,
  send_time       BIGINT,
  created_at      BIGINT NOT NULL,
  
  UNIQUE KEY uk_client (app_id, sender_id, conv_id, client_msg_id),
  UNIQUE KEY uk_server (server_msg_id),
  UNIQUE KEY uk_seq (conv_id, global_seq),
  KEY idx_visible (conv_id, visible_seq),
  KEY idx_mention_all (conv_id, mention_all, visible_seq),
  KEY idx_created (conv_id, created_at)
) ENGINE=InnoDB
  PARTITION BY HASH(conv_id) PARTITIONS 64;
```

## 5.2 用户会话游标 `user_conv_cursor`

```sql
CREATE TABLE user_conv_cursor (
  user_id              BIGINT NOT NULL,
  conv_id              BIGINT NOT NULL,
  read_visible_seq     BIGINT DEFAULT 0,
  read_mention_seq     BIGINT DEFAULT 0,
  joined_at_seq        BIGINT DEFAULT 0,
  cleared_before_seq   BIGINT DEFAULT 0,    -- 单方面清空对话
  is_muted             TINYINT DEFAULT 0,
  is_pinned            TINYINT DEFAULT 0,
  updated_at           BIGINT NOT NULL,
  
  PRIMARY KEY (user_id, conv_id),
  KEY idx_updated (user_id, updated_at)
) PARTITION BY HASH(user_id) PARTITIONS 256;
```

## 5.3 提及索引 `mention_index`

```sql
CREATE TABLE mention_index (
  user_id        BIGINT NOT NULL,
  conv_id        BIGINT NOT NULL,
  msg_seq        BIGINT NOT NULL,
  server_msg_id  BIGINT NOT NULL,
  sender_id      BIGINT NOT NULL,
  mention_type   TINYINT NOT NULL,         -- 1:@user 2:@all 3:reply
  status         TINYINT DEFAULT 0,
  created_at     BIGINT NOT NULL,
  
  PRIMARY KEY (user_id, conv_id, msg_seq),
  KEY idx_user_time (user_id, created_at DESC),
  KEY idx_msg (server_msg_id)
) PARTITION BY HASH(user_id) PARTITIONS 256;
```

## 5.4 会话元数据 `conversation_meta`

```sql
CREATE TABLE conversation_meta (
  conv_id              BIGINT PRIMARY KEY,
  conv_type            TINYINT NOT NULL,      -- 1:single 2:group 3:channel
  max_global_seq       BIGINT DEFAULT 0,
  max_visible_seq      BIGINT DEFAULT 0,
  max_seg_allocated    BIGINT DEFAULT 0,      -- seq 号段水位
  member_count         INT DEFAULT 0,
  is_large_group       TINYINT DEFAULT 0,
  created_at           BIGINT NOT NULL,
  updated_at           BIGINT NOT NULL
);
```

## 5.5 离线收件箱 `inbox`

```sql
CREATE TABLE inbox (
  user_id        BIGINT NOT NULL,
  conv_id        BIGINT NOT NULL,
  msg_seq        BIGINT NOT NULL,
  server_msg_id  BIGINT NOT NULL,
  created_at     BIGINT NOT NULL,
  
  PRIMARY KEY (user_id, conv_id, msg_seq),
  KEY idx_user_time (user_id, created_at)
) PARTITION BY HASH(user_id) PARTITIONS 256;
```

## 5.6 群成员 `group_member`

```sql
CREATE TABLE group_member (
  group_id    BIGINT NOT NULL,
  user_id     BIGINT NOT NULL,
  role        TINYINT DEFAULT 0,    -- 0:member 1:admin 2:owner
  joined_seq  BIGINT NOT NULL,
  joined_at   BIGINT NOT NULL,
  status      TINYINT DEFAULT 0,    -- 0:active 1:muted 2:removed
  
  PRIMARY KEY (group_id, user_id),
  KEY idx_user (user_id)
) PARTITION BY HASH(group_id) PARTITIONS 64;
```

## 5.7 Outbox 事件表 `outbox_event`

```sql
CREATE TABLE outbox_event (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  event_type    VARCHAR(32) NOT NULL,
  partition_key VARCHAR(64) NOT NULL,
  payload       JSON NOT NULL,
  status        TINYINT DEFAULT 0,    -- 0:pending 1:sent 2:failed
  retry_count   INT DEFAULT 0,
  created_at    BIGINT NOT NULL,
  sent_at       BIGINT,
  
  KEY idx_status (status, created_at)
) ENGINE=InnoDB;
```

## 5.8 撤回记录 `message_recall`

```sql
CREATE TABLE message_recall (
  server_msg_id  BIGINT PRIMARY KEY,
  conv_id        BIGINT NOT NULL,
  operator_id    BIGINT NOT NULL,
  recall_reason  VARCHAR(128),
  recalled_at    BIGINT NOT NULL,
  KEY idx_conv (conv_id, recalled_at)
);
```

## 5.9 用户主表 `user`

```sql
CREATE TABLE user (
  user_id     BIGINT PRIMARY KEY,
  app_id      INT NOT NULL,
  nickname    VARCHAR(64),
  avatar      VARCHAR(256),
  status      TINYINT DEFAULT 0,
  created_at  BIGINT NOT NULL,
  updated_at  BIGINT NOT NULL
);
```

---

# 6. Redis Key 设���规范

## 6.1 命名规范

```
{业务}:{对象}:{ID}[:{子维度}]
```

- 全部小写
- 用 `:` 分隔
- 必须以业务前缀开头

## 6.2 完整 Key 列表

### 在线状态

| Key | Type | TTL | 用途 |
|---|---|---|---|
| `presence:user:{userId}` | Hash | 30s（续约） | userId → {deviceId, gateway, conn_id} |
| `presence:dev:{userId}:{deviceId}` | String | 30s | 设备级路由 |
| `presence:gw:{gatewayId}` | Set | 60s | 某网关上的所有用户（监控） |

### 消息相关

| Key | Type | TTL | 用途 |
|---|---|---|---|
| `msg:dedup:{convId}:{clientMsgId}` | String | 5min | 发送去重快路径 |
| `msg:result:{convId}:{clientMsgId}` | Hash | 5min | 重试返回首次结果 |
| `msg:recent:{convId}` | ZSet (by seq) | LRU | 最近消息缓存 |
| `msg:recall:{serverMsgId}:{reqId}` | String | 5min | 撤回去重 |

### Seq 与游标

| Key | Type | TTL | 用途 |
|---|---|---|---|
| `seq:max:{convId}` | String | 持久 | 会话最大 visible_seq |
| `seq:max_global:{convId}` | String | 持久 | 会话最大 global_seq |
| `seq:segment:{convId}` | Hash | 持久 | 号段水位（备份恢复） |
| `cursor:{userId}:{convId}` | Hash | 持久 | read_visible_seq, read_mention_seq, joined_at_seq |

### @ 与计数

| Key | Type | TTL | 用途 |
|---|---|---|---|
| `mention:{userId}:{convId}` | ZSet (by seq) | 30d | 单会话 @ 我列表 |
| `mention_inbox:{userId}` | ZSet (by time) | 30d | 全局 @ 我列表（最近 1000） |
| `conv_mention_all_max:{convId}` | String | 持久 | 该会话最大 @all seq |

### 限流

| Key | Type | TTL | 用途 |
|---|---|---|---|
| `rate:user:{userId}:msg` | String | 60s | 用户消息频率 |
| `rate:conv:{convId}:msg` | String | 60s | 会话消息频率 |
| `rate:ip:{ip}:conn` | String | 60s | IP 建连频率 |
| `rate:global:{shard}` | String | 60s | 全局 QPS 限流（分桶） |

### 风控

| Key | Type | TTL | 用途 |
|---|---|---|---|
| `risk:user:{userId}` | Hash | 1h | 风险等级与封禁状态 |
| `risk:hot_keys` | Set | 5min | 热点 key 名单（用于路由） |
| `risk:large_user` | Set | 1h | 大 V 名单 |
| `risk:large_conv` | Set | 1h | 大群名单 |

### 群与会话

| Key | Type | TTL | 用途 |
|---|---|---|---|
| `group:members:{groupId}` | Set | 1h | 群成员集合（小群） |
| `group:meta:{groupId}` | Hash | 1h | 群元数据 |

### 同步

| Key | Type | TTL | 用途 |
|---|---|---|---|
| `syncbox:{userId}` | ZSet (by time) | 30d | 用户活跃会话列表 |

## 6.3 分片策略

- 用户相关 key 用 `{userId}` hashtag 保��同槽
- 会话相关用 `{convId}` hashtag
- 全局 key 加随机分桶 `:{0..15}` 防热点

## 6.4 内存预算

```
presence:        2GB（每用户 ~200B × 1000万）
cursor:          20GB（每用户 1000 会话 × 100B）
recent msg:      50GB（每会话 100 条 × 1KB × 50 万活跃会话）
mention:         5GB
rate limit:      2GB
total ~ 80GB → 64 主节点 × 2GB used
```

---

# 7. Kafka Topic 设计

## 7.1 Topic 规划

| Topic | Partitions | Replication | Retention | Key | 用途 |
|---|---|---|---|---|---|
| `msg.fanout.normal` | 500 | 3 | 7d | conv_id | 普通消息分发 |
| `msg.fanout.large` | 200 | 3 | 7d | conv_id+salt | 大群消息（隔离） |
| `msg.fanout.vip` | 100 | 3 | 7d | recipient_id+salt | 大 V 推送 |
| `msg.system` | 50 | 3 | 3d | random | 系统消息广播 |
| `msg.push.high` | 200 | 3 | 1d | user_id | 高优 push（@/私聊） |
| `msg.push.normal` | 100 | 3 | 1d | user_id | 普通 push（合并） |
| `msg.push.low` | 50 | 3 | 1d | random | 营销/低优 |
| `msg.recall` | 50 | 3 | 7d | server_msg_id | 撤回事件 |
| `msg.read` | 100 | 3 | 1d | user_id | 已读回执 |
| `msg.edit` | 50 | 3 | 7d | server_msg_id | 编辑事件 |
| `msg.mention` | 100 | 3 | 7d | user_id | @ 专属事件流 |
| `msg.inbox` | 200 | 3 | 3d | recipient_id | 写离线收件箱 |
| `presence.event` | 100 | 3 | 1h | user_id | 在线状态变更 |
| `user.behavior` | 200 | 3 | 30d | user_id | 风控行为日志 |
| `audit.log` | 100 | 3 | 90d | random | 审计 |
| `search.index` | 100 | 3 | 1d | server_msg_id | 搜索索引更新 |

## 7.2 分区与热点

### 普通消息
- key = `conv_id`
- 同会话有序

### 大群消息
- key = `conv_id + "#" + recipient_hash % 16`
- 按接收者加盐，接收者维度有序

### 大 V 推送
- key = `recipient_id`
- 接收者维度有序，发送者维度无序

### 系统广播
- key = random
- 完全打散

## 7.3 Consumer Group

| Topic | Consumer Group | 实例数 |
|---|---|---|
| `msg.fanout.normal` | `cg-deliver-normal` | 50 |
| `msg.fanout.large` | `cg-deliver-large` | 20 |
| `msg.fanout.vip` | `cg-fanout-vip` | 30 |
| `msg.push.high` | `cg-push-high` | 30 |
| `msg.push.normal` | `cg-push-normal` | 20 |
| `msg.inbox` | `cg-inbox` | 40 |
| `msg.mention` | `cg-mention-push` | 10 |
| `search.index` | `cg-search` | 10 |
| `user.behavior` | `cg-risk` | 20 |

## 7.4 死信队列（DLQ）

每个关键 topic 配套 DLQ：

```
msg.push.high       → msg.push.high.dlq
msg.fanout.normal   → msg.fanout.normal.dlq
```

消费失败 5 次后进 DLQ，人工 / 定时任务处理。

## 7.5 跨地域同步

```
华东 Kafka              华南 Kafka
msg.fanout.normal  ─MirrorMaker─→  msg.fanout.normal.replicated
                                    └─→ 华南消费者
```

---

# 8. 幂等性设计

## 8.1 五道幂等防线

| 层 | 幂等键 | 实现 |
|---|---|---|
| 客户端 | `clientMsgId` | 重试不变更，本地持久化 |
| Redis 快路径 | `dedup:{conv}:{clientMsgId}` | SETNX + TTL |
| DB 唯一约束 | `(app, sender, conv, client_msg_id)` | UNIQUE KEY |
| Outbox | `outbox_event.id` | 主键去重 |
| Consumer | 业务键 | 各消费者独立去重 |

## 8.2 ID 体系

| ID | 生成方 | 范围 | 特点 |
|---|---|---|---|
| `client_msg_id` | 客户端 | UUID/雪花 | 重试不变 |
| `server_msg_id` | 服务端 | 雪花 64bit | 全局唯一、近似有序 |
| `global_seq` | 服务端 | 会话内分片自增 | 允许空洞 |
| `visible_seq` | 服务端 | 会话内严格连续 | 未读用 |
| `outbox.id` | DB | 自增 | 投递去重 |

## 8.3 关键场景幂等

### 发送消息
```
1. 客户端 clientMsgId 持久化，重试不变
2. 服务端 SETNX msg:dedup:{conv}:{clientMsgId}
3. INSERT im_message ON DUPLICATE KEY → 返回原结果
4. Outbox 事件
5. Consumer 按 server_msg_id 幂等
```

### 已读上报
```
GREATEST 推进游标:
read_seq = MAX(prev, reported_seq)
```

### 撤回
```
条件更新:
UPDATE im_message SET status=1
WHERE server_msg_id=? AND status=0
```

### 离线消息写入
```
UNIQUE KEY (user_id, conv_id, msg_seq)
INSERT IGNORE
```

### Push
```
SETNX push:{serverMsgId}:{userId}:{channel} EX 86400
+ 厂商 collapse_id
```

## 8.4 防 seq 回退

- visible_seq INSERT 成功后才确认
- 节点切主：DB MAX + 1（visible）/ MAX + GAP（global）
- DB UNIQUE KEY (conv, seq) 兜底

---

# 9. 异常处理与 Fallback

## 9.1 故障矩阵

| 故障 | 影响 | Fallback |
|---|---|---|
| Gateway 挂 | 该机连接断 | 客户端 1~5s 重连到新网关，状态 30s 自愈 |
| MsgWrite 挂 | 写入失败 | LB 切流到健康实例 |
| Redis 主挂 | 缓存不可用 | 读 DB，写降级延迟同步 |
| Redis 集群挂 | 全站缓存失败 | 限流降级，DB 兜底 |
| MySQL 主挂 | 写入失败 | 切主（10~30s），期间写入排队 |
| Kafka 挂 | 异步 fanout 卡 | Outbox 堆积，消息核心仍可入库 |
| Push 厂商挂 | push 失败 | 切换备用厂商 |
| 状态分片挂 | 路由查询失败 | 本地缓存 + 广播投递降级 |
| 整集群挂 | 区域不可用 | DNS 切到其他集群，状态切到 standby |

## 9.2 Fallback 策略

### Redis 不可用
```
读: Redis miss → 查 DB → 不回填（避免雪崩）
写: 双写失败时，DB 成功即返回成功
   异步重试写 Redis
```

### Kafka 不可用
```
Outbox 堆积，业务正常写入
Worker 持续重试
SLA: outbox 堆积 > 1 万触发告警
```

### 状态服务不可用
```
策略 A: 广播投递（消息发到用户所属集群所有 Gateway）
策略 B: 本地缓存兜底（1 秒 TTL）
策略 C: 排队 1~3s 等切主完成
```

### Gateway 路由失败
```
消息服务投递到 Gateway 收到 NOT_FOUND:
1. 强制刷新 status shard
2. 重投递
3. 仍失败 → 进离线 inbox + 触发 push
```

## 9.3 客户端降级

- 实时通道断 → 自动切 WS（QUIC 失败）
- 双通道都断 → HTTP 轮询兜底
- 服务返回 503 → 指数退避重试
- 长期失联 → 本地草稿保留，恢复后发送

## 9.4 应急开关（一键降级）

| 开关 | 默认 | 紧急时 | 配置中心 |
|---|---|---|---|
| `kill.typing` | off | on | etcd |
| `kill.read_receipt` | off | on | etcd |
| `kill.large_group_fanout` | off | on | etcd |
| `kill.search` | off | on | etcd |
| `rate.global.qps` | 1M | 100K | etcd |
| `force.read_only` | off | on | etcd |

---

# 10. 风控设计

## 10.1 威胁模型

| 威胁 | 影响 | 检测手段 |
|---|---|---|
| 脚本刷消息 | 资源耗尽 | 频率检测 |
| 群发广告 | 用户骚扰 | 内容相似度 + 多收件人 |
| 拉群轰炸 | 用户体验 | 群成员变化速率 |
| 多账号协同 | 绕过限流 | 设备指纹 + IP 集群 |
| 暴力破解登录 | 安全 | 登录失败次数 |
| 爬取关系链 | 数据泄露 | 查询频率 |
| 钓鱼链接 | 用户损失 | URL 黑名单 + AI 识别 |
| 涉政/违规内容 | 合规风险 | 内容审核 |

## 10.2 风控架构

```
业务事件 ─→ Kafka (user.behavior)
                  │
                  ▼
         ┌────────────────┐
         │  实时风控引擎    │ ← 规则 + 模型
         │  (Flink)       │
         └────┬───────────┘
              │
              ▼
         risk:user:{uid}  ← 决策结果
              │
              ▼
         业务层查询消费
```

## 10.3 检测信号

```
- 发送频率 (sliding window)
- 收件人多样性 (HLL)
- 内容相似度 (SimHash)
- 收发比 (ratio)
- 加好友通过率
- 设备指纹 (canvas/UA/IP/...)
- 注册时间 (新号高风险)
- IP 类型 (机房 IP 段)
- 行为轨迹 (登录时间分布)
- 关系链密度 (异常连通)
```

## 10.4 决策与处置

| 等级 | 处置 |
|---|---|
| Level 0 | 正常 |
| Level 1 | 加验证码 |
| Level 2 | 降速（限流阈值减半） |
| Level 3 | 临时封禁 1h |
| Level 4 | 临时封禁 24h |
| Level 5 | 永久封号（人工审核） |

## 10.5 内容审核

```
消息发送 ─→ 同步快审（关键词/URL 黑名单）
              │
              ├─ 通过 → 入库 + 异步深审
              └─ 拒绝 → 直接 block

异步深审:
  图片: AI 鉴黄/暴恐/政治
  文本: NLP 模型
  音频: ASR + 文本审
  视频: 抽帧 + 综合
```

违规处置：撤回 + 下发警告 + 计入用户风险分。

---

# 11. 流量控制与限流

## 11.1 限流分层

| 层 | 维度 | 算法 | 实现 |
|---|---|---|---|
| 客户端 | 自限 | 节流/防抖 | SDK |
| Gateway | 单连接消息频率 | 令牌桶 | 本地内存 |
| Gateway | 单 IP 连接数 | 计数 | 本地内存 |
| Gateway | 单 IP 建连频率 | 令牌桶 | 本地内存 |
| 业务层 | 用户级消息频率 | 令牌桶 | Redis Lua |
| 业务层 | 会话级频率 | 令牌桶 | Redis Lua |
| 业务层 | 接口频率 | 滑动窗口 | Redis ZSet |
| 业务层 | 全局 QPS | 计数（分桶） | Redis |
| 下游 | 消费者池 | 信号量 | 本地 |
| 下游 | 大群 fanout | 漏桶 | 本地 |

## 11.2 限流配置基线

| 维度 | 阈值 |
|---|---|
| 单连接消息频率 | 10/s, 突发 30 |
| 单连接信令 | 50/s |
| 单 IP 连接数 | 50 |
| 单 IP 建连 | 10/s |
| 单用户消息 | 200/min |
| 单会话消息 | 20/s |
| 私聊收发对 | 60/min |
| 加好友 | 50/d |
| 建群 | 5/h |
| 拉群成员 | 100/h |
| 历史消息拉取 | 5/s, limit ≤ 200 |
| 万人群消息 | 5/s |
| 文件消息 | 10/min |

## 11.3 Redis Lua 令牌桶

```lua
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local n = tonumber(ARGV[4])

local last_tokens = tonumber(redis.call('hget', key, 'tokens')) or capacity
local last_time = tonumber(redis.call('hget', key, 'ts')) or now

local elapsed = math.max(0, now - last_time)
local filled = math.min(capacity, last_tokens + elapsed * rate)

local allowed = filled >= n
if allowed then
  filled = filled - n
end

redis.call('hmset', key, 'tokens', filled, 'ts', now)
redis.call('expire', key, 60)
return allowed and 1 or 0
```

## 11.4 限流降级

- 限流命中 → 返回 429 + Retry-After
- 客户端指数退避 + 抖动
- 紧急时全局阈值通过配置中心动态下调

## 11.5 重连风暴防御

```
- 客户端: 指数退避 1s→2s→4s→8s + random(0~1s)
- Gateway: 单实例每秒最多接受 1000 新连接
- Dispatcher: 优雅恢复，按比例放量
```

---

# 12. 跨地域部署

## 12.1 部署拓扑

```
┌──────────────────────────────────────────────┐
│              全球 GSLB (DNS)                  │
└──────┬───────────┬─────────────┬─────────────┘
       │           │             │
   ┌───▼───┐  ┌────▼───┐  ┌─────▼────┐
   │ 华东  │  │ 华南    │  │ 美西      │
   │ 区域   │  │ 区域    │  │ 区域      │
   └───────┘  └────────┘  └──────────┘
```

每个区域包含：
- 完整的接入层 + 业务层 + 数据层
- 独立 Kafka 集群
- 独立 Redis 集群
- 独立 DB 主从（异地有 standby）

## 12.2 用户归属

每个用户有"主区域"（home region），由：
- 注册地
- 主要活动地
决定。

```
用户元数据:
  user_id → home_region
  存储: 全局配置中心 / 全局 DB
```

## 12.3 跨区消息流

```
A 在华东，B 在华南：

1. A 发消息 → 华东 Gateway → 华东 MsgWrite
2. 写华东 DB（A 的会话主分片）
3. 写华东 Kafka
4. MirrorMaker 同步到华南 Kafka
5. 华南消费者投递给 B
```

延迟预算：
- 同区域 P99: 200ms
- 跨区域 P99: 500ms (含 100~150ms 网络)

## 12.4 数据一致性

| 数据 | 一致性级别 | 同步方式 |
|---|---|---|
| 消息正文 | 最终一致 | Kafka MirrorMaker（异步） |
| 用户资料 | 最终一致 | DB binlog 异步复制 |
| 在线状态 | 区域内一致 | 不跨区同步 |
| 配置 | 强一致 | etcd 跨区集群 |
| 群成员 | 最终一致 | 主区域为准，异步同步 |

## 12.5 容灾切换

### 单 AZ 故障
- AZ 内自动切换（K8s 调度 + LB 摘除）
- RTO: < 30s

### 整区域故障
- DNS GSLB 切流到其他区域
- 用户重连到新区域
- 数据：DB standby 提升为主
- RTO: < 5min, RPO: < 30s

### 跨区域脑裂
- 分区双方各自服务（CP）
- 网络恢复后异步合并
- 冲突按 timestamp 解决

---

# 13. 可观测性与 SLA

## 13.1 SLA 定义

| 指标 | 目标 | 测量 |
|---|---|---|
| 接入可用性 | 99.95% | 探针 + LB 健康率 |
| 消息送达率 | 99.99% | 端到端追踪 |
| 消息延迟 P99 | < 500ms（同区） | 全链路打点 |
| 消息延迟 P99 | < 1s（跨区） | 全链路打点 |
| 离线消息延迟 | < 5s | push 时间戳对比 |
| 消息丢失率 | < 0.001% | 对账 |
| API 成功率 | > 99.9% | LB / Gateway 日志 |

## 13.2 监控分层

```
基础设施: CPU/MEM/Disk/Network/IOPS
中间件:    Redis/MySQL/Kafka/etcd 各项内置指标
业务:      QPS/延迟/错误率/业务计数
端到端:    全链路 Trace（OpenTelemetry）
体验:      客户端上报（连接成功率、收发延迟）
```

## 13.3 关键监控指标

### Gateway
```
- 连接数（当前/峰值）
- 建连/秒
- 消息收发 QPS
- 消息延迟 (P50/P99)
- TLS 握手失败率
- QUIC 迁移成功率
- CPU / 内存 / 网络
```

### 消息链路
```
- 写入 QPS / 延迟
- Outbox 堆积量
- Kafka 各 topic lag（按 partition）
- 投递成功率
- 各下游消费者 lag
- 撤回 / 编辑速率
```

### 数据层
```
- Redis: hit ratio / 内存 / 慢查询
- MySQL: QPS / 慢查询 / 主从延迟 / 死锁
- Kafka: ISR / Under-Replicated / 网络
- DB 连接池使用率
```

### 业务
```
- DAU / MAU
- 消息发送量
- 群活跃数
- @ 消息量
- 异常封禁数（风控）
- Push 成功率（按厂商）
```

## 13.4 日志规范

### 结构化日志
```json
{
  "ts": "2026-05-04T10:00:00.123Z",
  "level": "INFO",
  "service": "msg-write",
  "trace_id": "...",
  "span_id": "...",
  "user_id": 1001,
  "conv_id": 123,
  "client_msg_id": "...",
  "server_msg_id": 99001,
  "event": "message_created",
  "duration_ms": 45
}
```

### 日志分级
- DEBUG: 仅开发环境
- INFO: 关键业务事件
- WARN: 异常但可处理
- ERROR: 失败需关注
- FATAL: 触发告警

### 日志收集
```
应用 → Filebeat → Kafka → Logstash → ES
保留期: 错���日志 30 天 / INFO 7 天
```

## 13.5 全链路追踪

OpenTelemetry 标准：
- 客户端发送 → 注入 trace_id
- Gateway 透传
- 所有 RPC 携带 trace context
- Kafka 消息 header 携带 trace
- 全链路一个 trace 串起来

## 13.6 告警分级

| 级别 | 响应时间 | 渠道 |
|---|---|---|
| P0 | 5 分钟 | 电话 + IM + 邮件 |
| P1 | 15 分钟 | IM + 邮件 |
| P2 | 1 小时 | IM |
| P3 | 4 小时 | 邮件 |

### P0 告警示例
- 接入成功率 < 99%
- 消息丢失率 > 0.01%
- 主集群整体不可用
- DB 主从延迟 > 60s

## 13.7 容量监控

```
- 连接数水位
- QPS 水位
- 存储水位
- Redis 内存水位
- Kafka 磁盘水位
告警阈值: 70% (黄), 85% (橙), 95% (红)
```

---

# 14. 灰度发布与上线

## 14.1 发布策略矩阵

| 变更类型 | 策略 | 验证 |
|---|---|---|
| 客户端 | 应用商店阶段发布 | 1% → 10% → 50% → 100% |
| Gateway | 蓝绿 + 滚动 | 单实例验证 → 一区域 → 全量 |
| 业务层 | 滚动 | 单 AZ → 一区域 → 全量 |
| 协议变更 | 双协议兼容 | 长达数周 |
| 数据库 | 只增不删，分阶段 | 见 14.5 |

## 14.2 灰度维度

```
按用户:    user_id % 100 < N  (N=1,5,20,50,100)
按区域:    单 AZ → 一区域
按租户:    白名单 app_id
按设备:    iOS/Android 分批
按版本:    强制升级旧版本
```

## 14.3 灰度流程

```
1. 内部环境验证 (开发/测试)
2. 预发布环境（生产数据镜像）
3. Canary（< 1% 流量）24h
4. 灰度 5% 24h
5. 灰度 20% 12h
6. 灰度 50% 12h
7. 全量
8. 持续观察 7 天
```

每个阶段必须满足：
- 错误率不上升
- 延迟不上升
- 业务核心指标不下降

## 14.4 回滚机制

- 一键回滚（≤ 5 分钟）
- 数据库变更：必须可回滚（增字段 / 不删字段）
- 协议变更：双向兼容期 ≥ 1 个月

## 14.5 数据库变更规范

```
✅ 允许:
  - 加字段 (DEFAULT NULL)
  - 加索引 (online DDL)
  - 加表

⚠️ 谨慎:
  - 改字段类型 (要求兼容)
  - 改索引 (双跑后切)

❌ 禁止:
  - 直接删字段
  - 直接删表
  - 字段重命名

变更步骤:
  1. 加新字段（兼容旧代码）
  2. 双写
  3. 历史数据迁移
  4. 切读
  5. 停旧字段写入
  6. 30 天后真删
```

## 14.6 发布前检查清单

```
[ ] Code Review 通过
[ ] 单元测试覆盖 > 70%
[ ] 集成测试通过
[ ] 性能测试达标
[ ] 监控/告警就��
[ ] 回滚预案文档
[ ] 灰度计划评审
[ ] 风险预案
[ ] 变更通知 (业务/客服/SRE)
[ ] 应急联系人就位
```

## 14.7 发布窗口

```
工作日 10:00 - 17:00（优先）
重大变更: 周二/周三
禁止时段:
  - 周五下午（防周末爆雷）
  - 节假日
  - 大型营销活动期间
```

## 14.8 应急响应

```
故障发现 → 5 分钟内决策回滚 / 修复
P0 故障 → 立即拉群 + 战时模式
事后复盘:
  - 时间线
  - 根因
  - 改进项
  - 责任界定（不追责，但要总结）
```

---

# 15. 附录：容量规划与基线指标

## 15.1 容量预估（千万 DAU）

```
DAU:               10,000,000
峰值在线:           1,000,000
日消息量:           20 亿
峰值消息 QPS:       50万 (写入) / 200万 (含 fanout)
日新增数据:         约 500GB（消息）+ 索引
```

## 15.2 资源预算（参考）

| 组件 | 数量 | 规格 |
|---|---|---|
| Gateway | 50 | 16C32G |
| MsgWrite | 30 | 16C32G |
| MsgSync | 20 | 16C32G |
| Deliver | 20 | 16C32G |
| InboxWriter | 30 | 16C32G |
| Push | 20 | 16C32G |
| MySQL | 32 主 + 32 从 | 32C128G + SSD |
| Redis | 64 主 + 64 从 | 8C32G |
| Kafka | 12 broker | 16C64G + 4TB |
| ES | 20 节点 | 16C64G + 2TB |
| HBase | 32 节点 | 16C64G + 8TB |

## 15.3 性能基线（单实例）

| 服务 | QPS | 延迟 P99 |
|---|---|---|
| Gateway 消息转发 | 50K | < 5ms |
| MsgWrite 入库 | 5K | < 50ms |
| Deliver 投递 | 20K | < 20ms |
| Redis 单实例 | 100K | < 1ms |
| MySQL 单实例 | 5K | < 10ms |
| Kafka 单 partition | 10K | < 10ms |

## 15.4 SLA 总表

| 指标 | 目标 |
|---|---|
| 服务可用性 | 99.95% |
| 消息成功率 | 99.99% |
| 消息丢失率 | < 0.001% |
| P50 延迟 | < 100ms |
| P99 延迟 | < 500ms |
| RTO | < 5min |
| RPO | < 30s |

---

# 文档维护

- 文档负责人: 架构组
- 评审周期: 每季度
- 变更流程: PR + 至少 2 人 review
- 版本控制: Git
- 关联文档:
  - QUIC 接入网关详细设计
  - 消息存储分库分表方案
  - 风控规则手册
  - SRE 运维手册
  - 客户端 SDK 设计

---

**文档结束**

*Version 1.0 | 最后更新: 2026-05-04*