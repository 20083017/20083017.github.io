# Outbox Worker 详细设计与实现 v1.0

> 适用：保证业务 DB 写入与 Kafka 投递的最终一致性  
> 模式：Transactional Outbox Pattern  
> 目标：消息不丢、不重复、低延迟、可水平扩展

---

## 目录

1. 设计背景与目标
2. 架构设计
3. Outbox 表设计
4. Worker 实现详解
5. 投递保证
6. 性能优化
7. 故障处理
8. 监控指标
9. 部署与运维

---

# 1. 设计背景与目标

## 1.1 解决的问题

### 双写不一致
```
错误做法 1: 先写 DB 再发 Kafka
  DB 成功 + Kafka 失败 → 消息丢失

错误做法 2: 先发 Kafka 再写 DB
  Kafka 成功 + DB 失败 → 幻影消息

错误做法 3: XA / 2PC
  性能差，运维复杂，跨系统不可靠
```

### Outbox 模式
```
事务内:
  INSERT 业务表
  INSERT outbox_event       ← 同事务原子写入

事务外:
  Worker 扫 outbox → 投 Kafka → 标记已发
```

## 1.2 设计目标

| 指标 | 目标 |
|---|---|
| 消息丢失率 | 0 |
| 重复率 | < 0.01%（消费侧幂等兜底） |
| 投递延迟 P99 | < 500ms |
| 吞吐 | 10 万 events/s |
| 故障恢复 | < 30s |

---

# 2. 架构设计

## 2.1 整体架构

```
┌────────────────────────────────────────────┐
│  业务服务 (MsgWrite/Recall/...)              │
│  事务内: INSERT msg + INSERT outbox          │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────┐
│  outbox_event 表 (按 shard 分布)             │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────���───────────────────┐
│  Outbox Worker 集群                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Worker 1 │  │ Worker 2 │  │ Worker N │  │
│  │ (持锁)   │  │ (持锁)   │  │ (持锁)   │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────┐
│  Kafka 集群                                 │
└────────────────────────────────────────────┘
```

## 2.2 Worker 调度模型

每个 outbox 分片由**一个 Worker 实例独占处理**，避免重复扫描。

```
shard 0 → worker-1 (持锁)
shard 1 → worker-2 (持锁)
shard 2 → worker-3 (持锁)
...
shard N → worker-M

如果 worker-1 挂:
  锁过期 (30s)
  其他 worker 抢锁
  接管 shard 0
```

锁实现：etcd / Redis SET NX EX。

---

# 3. Outbox 表设计

## 3.1 表结构

```sql
CREATE TABLE outbox_event (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  shard_id        INT NOT NULL,                  -- 分片 ID（0~N-1）
  event_type      VARCHAR(64) NOT NULL,
  topic           VARCHAR(128) NOT NULL,         -- 目标 Kafka topic
  partition_key   VARCHAR(128) NOT NULL,         -- Kafka 分区键
  payload         MEDIUMBLOB NOT NULL,           -- 事件正文（Protobuf/JSON）
  
  status          TINYINT NOT NULL DEFAULT 0,    -- 0:pending 1:sent 2:failed
  retry_count     INT NOT NULL DEFAULT 0,
  next_retry_at   BIGINT,                        -- 下次重试时间
  last_error      VARCHAR(512),
  
  created_at      BIGINT NOT NULL,
  sent_at         BIGINT,
  
  KEY idx_pending (shard_id, status, id),        -- Worker 扫描索引
  KEY idx_retry (status, next_retry_at)          -- 重试扫描
) ENGINE=InnoDB
  PARTITION BY RANGE (id) (
    PARTITION p_2026_01 VALUES LESS THAN (...),
    PARTITION p_2026_02 VALUES LESS THAN (...),
    ...
  );
```

### 关键设计

#### shard_id
- 业务写入时按 hash 决定（如 `hash(conv_id) % N`）
- 同一业务实体的事件落同一 shard，保证顺序
- N 通常 = Worker 数 × 2（留扩缩容空间）

#### status
- `0 pending`：待投递
- `1 sent`：已投递
- `2 failed`：超过重试次数，进 DLQ

#### partition_key
- 写入业务事件时就确定，Worker 不再计算
- 通常是 `conv_id` 或 `user_id`

#### payload
- 推荐 Protobuf（小、快）
- 事件结构里**不放完整消息内容**，只放 ID + 元数据
- 消费者需要正文时按 ID 查 DB

### 已发记录处理

```sql
-- 选项 A: 保留 N 天后归档/删除
DELETE FROM outbox_event 
WHERE status = 1 AND sent_at < NOW() - INTERVAL 7 DAY;

-- 选项 B: 投递成功立即删除（推荐）
-- 但失去审计能力
```

**推荐选项 A**：保留 7 天，便于排查问题。

## 3.2 索引选择

```sql
KEY idx_pending (shard_id, status, id)
```

Worker 查询：

```sql
SELECT * FROM outbox_event 
WHERE shard_id = ? AND status = 0
ORDER BY id 
LIMIT 1000;
```

走 `idx_pending`，O(log N) 定位 + 范围扫描。

## 3.3 容量估算

```
事件量: 10 万/秒
保留 7 天: 10 万 × 86400 × 7 = 60 亿
单事件大小: ~500 字节
存储: 3 TB

按 shard 分库:
  32 shard → 单库 100 GB
  按月分区，便于归档
```

---

# 4. Worker 实现详解

## 4.1 Worker 主循环

```go
type OutboxWorker struct {
    shardID       int
    db            *sql.DB
    producer      *kafka.Producer
    locker        DistributedLock
    batchSize     int
    pollInterval  time.Duration
    metrics       *Metrics
}

func (w *OutboxWorker) Run(ctx context.Context) error {
    // 1. 抢锁
    lock, err := w.locker.Acquire(ctx, fmt.Sprintf("outbox:shard:%d", w.shardID), 30*time.Second)
    if err != nil {
        return fmt.Errorf("acquire lock: %w", err)
    }
    defer lock.Release()
    
    // 2. 启动锁续约
    go w.renewLock(ctx, lock)
    
    // 3. 主循环
    ticker := time.NewTicker(w.pollInterval)
    defer ticker.Stop()
    
    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-ticker.C:
            if err := w.processBatch(ctx); err != nil {
                w.metrics.ErrorTotal.Inc()
                log.Errorf("processBatch: %v", err)
            }
        }
    }
}
```

## 4.2 批量处理

```go
func (w *OutboxWorker) processBatch(ctx context.Context) error {
    // 1. 拉一批待发
    events, err := w.fetchPending(ctx, w.batchSize)
    if err != nil {
        return err
    }
    if len(events) == 0 {
        return nil
    }
    
    w.metrics.BatchSize.Observe(float64(len(events)))
    
    // 2. 批量投递
    successful, failed := w.batchProduce(ctx, events)
    
    // 3. 批量更新状态
    if err := w.markSent(ctx, successful); err != nil {
        return fmt.Errorf("mark sent: %w", err)
    }
    
    if len(failed) > 0 {
        w.markFailed(ctx, failed)
    }
    
    w.metrics.SentTotal.Add(float64(len(successful)))
    w.metrics.FailedTotal.Add(float64(len(failed)))
    
    return nil
}
```

## 4.3 拉取待发事件

```go
func (w *OutboxWorker) fetchPending(ctx context.Context, limit int) ([]*Event, error) {
    query := `
        SELECT id, event_type, topic, partition_key, payload, retry_count
        FROM outbox_event 
        WHERE shard_id = ? 
          AND status = 0 
          AND (next_retry_at IS NULL OR next_retry_at <= ?)
        ORDER BY id 
        LIMIT ?
    `
    
    rows, err := w.db.QueryContext(ctx, query, w.shardID, time.Now().UnixMilli(), limit)
    if err != nil {
        return nil, err
    }
    defer rows.Close()
    
    var events []*Event
    for rows.Next() {
        e := &Event{}
        if err := rows.Scan(&e.ID, &e.EventType, &e.Topic, &e.PartitionKey, &e.Payload, &e.RetryCount); err != nil {
            return nil, err
        }
        events = append(events, e)
    }
    return events, nil
}
```

## 4.4 批量投递 Kafka

```go
func (w *OutboxWorker) batchProduce(ctx context.Context, events []*Event) (successful []int64, failed []*Event) {
    // 用 channel 收集结果
    deliveryChan := make(chan kafka.Event, len(events))
    
    // 1. 发送
    for _, e := range events {
        msg := &kafka.Message{
            TopicPartition: kafka.TopicPartition{
                Topic:     &e.Topic,
                Partition: kafka.PartitionAny,
            },
            Key:   []byte(e.PartitionKey),
            Value: e.Payload,
            Headers: []kafka.Header{
                {Key: "event_type", Value: []byte(e.EventType)},
                {Key: "outbox_id", Value: []byte(strconv.FormatInt(e.ID, 10))},
                {Key: "trace_id", Value: []byte(extractTraceID(ctx))},
            },
        }
        
        if err := w.producer.Produce(msg, deliveryChan); err != nil {
            // 本地队列满，标记失败
            failed = append(failed, e)
            continue
        }
    }
    
    // 2. 等待 ack
    timeout := time.After(10 * time.Second)
    eventByID := make(map[int64]*Event)
    for _, e := range events {
        eventByID[e.ID] = e
    }
    
    received := 0
    expected := len(events) - len(failed)
    
    for received < expected {
        select {
        case ev := <-deliveryChan:
            received++
            msg := ev.(*kafka.Message)
            outboxID, _ := strconv.ParseInt(string(getHeader(msg.Headers, "outbox_id")), 10, 64)
            e := eventByID[outboxID]
            
            if msg.TopicPartition.Error != nil {
                failed = append(failed, e)
                e.LastError = msg.TopicPartition.Error.Error()
            } else {
                successful = append(successful, e.ID)
            }
            
        case <-timeout:
            log.Warn("kafka ack timeout, will retry")
            // 超时未 ack 的事件下次重试
            return
        }
    }
    
    return
}
```

## 4.5 标记已发（关键事务）

```go
func (w *OutboxWorker) markSent(ctx context.Context, ids []int64) error {
    if len(ids) == 0 {
        return nil
    }
    
    // 批量 UPDATE
    query := fmt.Sprintf(`
        UPDATE outbox_event 
        SET status = 1, sent_at = ? 
        WHERE id IN (%s)
    `, placeholders(len(ids)))
    
    args := []interface{}{time.Now().UnixMilli()}
    for _, id := range ids {
        args = append(args, id)
    }
    
    _, err := w.db.ExecContext(ctx, query, args...)
    return err
}
```

## 4.6 标记失败 + 重试退避

```go
func (w *OutboxWorker) markFailed(ctx context.Context, events []*Event) error {
    for _, e := range events {
        e.RetryCount++
        
        if e.RetryCount >= MaxRetries {
            // 进入 DLQ
            w.sendToDLQ(ctx, e)
            
            _, err := w.db.ExecContext(ctx, `
                UPDATE outbox_event 
                SET status = 2, last_error = ?, retry_count = ? 
                WHERE id = ?
            `, e.LastError, e.RetryCount, e.ID)
            if err != nil {
                return err
            }
            continue
        }
        
        // 计算下次重试时间（指数退避）
        backoff := w.calcBackoff(e.RetryCount)
        nextRetry := time.Now().Add(backoff).UnixMilli()
        
        _, err := w.db.ExecContext(ctx, `
            UPDATE outbox_event 
            SET retry_count = ?, next_retry_at = ?, last_error = ? 
            WHERE id = ?
        `, e.RetryCount, nextRetry, e.LastError, e.ID)
        if err != nil {
            return err
        }
    }
    return nil
}

func (w *OutboxWorker) calcBackoff(retry int) time.Duration {
    base := time.Second
    max := 5 * time.Minute
    
    backoff := base * time.Duration(1<<retry)  // 1s, 2s, 4s, 8s, 16s, 32s, 64s, 128s, 256s
    if backoff > max {
        backoff = max
    }
    
    // 加随机抖动 ±20%
    jitter := time.Duration(rand.Int63n(int64(backoff) / 5))
    return backoff + jitter - backoff/10
}

const MaxRetries = 8  // ~ 累计 8 分钟重试
```

## 4.7 锁续约

```go
func (w *OutboxWorker) renewLock(ctx context.Context, lock DistributedLock) {
    ticker := time.NewTicker(10 * time.Second)
    defer ticker.Stop()
    
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            if err := lock.Renew(ctx, 30*time.Second); err != nil {
                log.Errorf("renew lock failed: %v", err)
                // 锁丢失，停止处理（其他 worker 会接管）
                return
            }
        }
    }
}
```

## 4.8 Kafka Producer 配置

```go
producerConfig := &kafka.ConfigMap{
    "bootstrap.servers": "kafka:9092",
    
    // 可靠性
    "acks":                              "all",
    "enable.idempotence":                true,
    "max.in.flight.requests.per.connection": 5,
    "retries":                           10,
    "retry.backoff.ms":                  100,
    
    // 性能
    "linger.ms":                         5,
    "batch.size":                        65536,
    "compression.type":                  "lz4",
    "queue.buffering.max.messages":      100000,
    "queue.buffering.max.kbytes":        1048576,
    
    // 超时
    "delivery.timeout.ms":               30000,
    "request.timeout.ms":                10000,
}
```

---

# 5. 投递保证

## 5.1 不丢消息

```
关键点 1: 业务事务内写 outbox
  业务 INSERT + outbox INSERT 在同一事务
  事务提交 → 事件必然存在
  
关键点 2: 投递成功才标记
  Kafka ack=all
  + producer 幂等
  + 标记 status=1 在 ack 后
  
关键点 3: Worker 故障可恢复
  锁过期，其他 worker 接管
  status=0 的事件继续被扫到
```

## 5.2 不重复投递

```
难点: 投递成功了但更新 status 失败
       下次扫到又投一次

解决:
  1. Producer 幂等（enable.idempotence）
     单 producer 实例内自动去重
  
  2. 消费者幂等
     按 outbox_id / server_msg_id 去重
     这是最终防线
```

## 5.3 顺序保证

```
同一 partition_key 的事件:
  - 落同一 outbox shard
  - 单 Worker 顺序处理
  - 投到 Kafka 同一 partition
  
所以同一 conv_id / user_id 的事件在 Kafka 内严格有序
```

---

# 6. 性能优化

## 6.1 批量优化

```go
// 批量大小调优
batchSize: 1000 events

// 单事件 500B → 一批 500KB
// 单 Worker 吞吐: 1000 events × 100 batch/s = 100K events/s
```

## 6.2 并发模型

每个 Worker 单线程串行扫描，但内部可以并发：

```go
// 并发投递
func (w *OutboxWorker) parallelProduce(events []*Event) {
    // 按 partition_key 分组
    groups := groupByPartitionKey(events)
    
    var wg sync.WaitGroup
    for _, group := range groups {
        wg.Add(1)
        go func(g []*Event) {
            defer wg.Done()
            for _, e := range g {
                w.producer.Produce(e)  // 异步发送
            }
        }(group)
    }
    wg.Wait()
}
```

注意：**同一 partition_key 必须串行**，否则破坏顺序。

## 6.3 减少 DB 压力

### 索引选择
确保 `(shard_id, status, id)` 索引被用上。

### 避免全表扫描
```sql
-- 错误：全表扫
SELECT * FROM outbox_event WHERE status = 0;

-- 正确：分片扫
SELECT * FROM outbox_event WHERE shard_id = ? AND status = 0 LIMIT 1000;
```

### 已发数据归档
```sql
-- 每天凌晨
DELETE FROM outbox_event 
WHERE status = 1 AND sent_at < NOW() - INTERVAL 7 DAY
LIMIT 10000;

-- 分批删除，避免大事务
```

## 6.4 拉取优化

### 长轮询 vs 定时
```
定时轮询: 每 50ms 扫一次
  优点: 简单
  缺点: 空轮询多

通知触发:
  业务写 outbox 后发个轻量信号给 Worker
  Worker 收到信号立即处理
  Channel + 定时兜底
```

```go
type OutboxWorker struct {
    notifyChan chan struct{}
    ...
}

// 业务侧
func InsertOutbox(...) {
    db.Insert(...)
    select {
    case worker.notifyChan <- struct{}{}:
    default:  // 已有信号，丢弃
    }
}

// Worker 侧
for {
    select {
    case <-w.notifyChan:
        w.processBatch()
    case <-time.After(50 * time.Millisecond):
        w.processBatch()
    }
}
```

## 6.5 性能基线

```
单 Worker:
  - 拉取: 5 ms (1000 行)
  - 投递: 10 ms (Kafka batch)
  - 标记: 5 ms (UPDATE)
  - 总: 20 ms / batch
  - 吞吐: 1000 / 0.02 = 50K events/s

10 个 Worker:
  - 总吞吐: 500K events/s
```

---

# 7. 故障处理

## 7.1 故障矩阵

| 故障 | 影响 | 恢复 |
|---|---|---|
| Worker 进程崩溃 | 该 shard 暂停 | 锁过期 30s → 其他 worker 接管 |
| DB 主挂 | 全部 worker 暂停 | DB 切主 → 自动恢复 |
| Kafka 不可用 | 投递失败累积 | Outbox 堆积，Kafka 恢复后追赶 |
| 锁服务（etcd）挂 | 抢锁失败 | 等待恢复（可短暂双扫，幂等兜底） |
| 网络分区 | 部分 worker 失联 | 锁过期，分区方接管 |

## 7.2 双 Worker 抢锁

```
worker-1 (持锁) 假死
   │
   ▼ 锁未过期但停止续约
   │
   ▼ 30s 后锁过期
   │
   ▼ worker-2 抢到锁
   │
   ▼ worker-1 恢复，发现锁丢失
   │
   ▼ worker-1 退出
```

短暂的双 worker 处理是可能的，但：
- Producer 幂等 → 不会双投
- 消费者幂等 → 兜底

## 7.3 DLQ 处理

```sql
-- 失败事件
SELECT * FROM outbox_event WHERE status = 2;
```

```go
// DLQ 消费器
func processDLQ() {
    events := db.Query("SELECT * FROM outbox_event WHERE status=2")
    for _, e := range events {
        // 1. 人工分析失败原因
        // 2. 修复后可重置为 status=0
        // 3. 或者标记为 status=3 (人工已处理)
    }
}
```

DLQ 告警：

```
SELECT count(*) FROM outbox_event WHERE status=2
> 100 触发告警
```

## 7.4 Outbox 堆积

```
触发条件: status=0 行数 > 阈值

排查:
  - Worker 是否在工作？
  - Kafka 是否健康？
  - DB 是否有锁？
  
处置:
  - 临时增加 Worker 实例
  - 增大 batchSize
  - 关闭非关键事件类型
```

## 7.5 数据修复

```
场景: 业务事务提交了，但 outbox 记录被误删

恢复:
  1. 从业务表反向重建事件
  2. INSERT INTO outbox_event SELECT FROM message ...
  3. 设置正确的 partition_key 和 topic
```

---

# 8. 监控指标

## 8.1 关键指标

| 指标 | 类型 | 说明 |
|---|---|---|
| `outbox_pending_count{shard}` | Gauge | 待发数量（堆积） |
| `outbox_sent_total{shard,topic}` | Counter | 已发总数 |
| `outbox_failed_total{shard,reason}` | Counter | 失败总数 |
| `outbox_dlq_count{shard}` | Gauge | DLQ 数量 |
| `outbox_batch_size` | Histogram | 批次大小 |
| `outbox_process_duration{shard}` | Histogram | 单批处理耗时 |
| `outbox_age_seconds{shard}` | Gauge | 最老 pending 事件年龄 |
| `outbox_worker_active{shard}` | Gauge | Worker 是否在线 |
| `outbox_lock_lost_total` | Counter | 锁丢失次数 |

## 8.2 告警规则

```yaml
- alert: OutboxBacklog
  expr: outbox_pending_count > 10000
  for: 1m
  severity: P1
  
- alert: OutboxStale
  expr: outbox_age_seconds > 60
  for: 1m
  severity: P1
  
- alert: OutboxDLQGrowing
  expr: rate(outbox_failed_total[5m]) > 1
  for: 5m
  severity: P2
  
- alert: OutboxWorkerDown
  expr: outbox_worker_active == 0
  for: 30s
  severity: P0
```

## 8.3 Grafana 大盘

```
Panel 1: 实时吞吐 (events/s by topic)
Panel 2: 堆积量 (pending by shard)
Panel 3: 投递延迟 P50/P99
Panel 4: 失败率
Panel 5: DLQ 增长趋势
Panel 6: Worker 健康
```

---

# 9. 部署与运维

## 9.1 部署架构

```yaml
# K8s Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: outbox-worker
spec:
  replicas: 16   # = shard 数 × 1.5（冗余）
  template:
    spec:
      containers:
      - name: worker
        image: im/outbox-worker:v1.0
        env:
          - name: WORKER_ID
            valueFrom:
              fieldRef:
                fieldPath: metadata.name
          - name: SHARD_COUNT
            value: "32"
        resources:
          requests:
            cpu: 1
            memory: 2Gi
          limits:
            cpu: 2
            memory: 4Gi
```

## 9.2 配置示例

```yaml
outbox:
  shard_count: 32
  batch_size: 1000
  poll_interval: 50ms
  max_retries: 8
  
  lock:
    backend: etcd  # 或 redis
    ttl: 30s
    renew_interval: 10s
  
  kafka:
    bootstrap_servers: "kafka:9092"
    acks: all
    idempotence: true
    compression: lz4
    
  db:
    max_connections: 20
    query_timeout: 5s
```

## 9.3 滚动升级

```
1. 新版本 Worker 启动
2. 老 Worker 收到 SIGTERM
3. 老 Worker 处理完当前 batch
4. 老 Worker 释放锁
5. 新 Worker 抢锁继续
6. 全程不停机
```

```go
func (w *OutboxWorker) shutdown() {
    log.Info("graceful shutdown begin")
    
    // 1. 停止接收新批次
    w.cancel()
    
    // 2. 等待当前批次完成（最多 30s）
    w.waitCurrentBatch(30 * time.Second)
    
    // 3. 释放锁
    w.lock.Release()
    
    log.Info("graceful shutdown done")
}
```

## 9.4 容量规划

```
业务峰值: 50 万消息/秒
每条消息: 1~5 个 outbox 事件（fanout/push/inbox）
峰值事件: 200 万 events/s

单 Worker: 50K events/s
所需 Worker: 40 个

留余量: 64 个 Worker
对应 shard 数: 32（每 shard 配 2 个 worker，但只 1 个持锁）
```

## 9.5 故障演练

```
每月一次演练:
- 杀掉某个 Worker → 看接管时间
- 临时阻断 Kafka → 看堆积情况
- DB 主切换 → 看自愈
- 网络分区 → 看锁行为
```

---

# 附录：完整代码骨架

```go
package outbox

import (
    "context"
    "database/sql"
    "fmt"
    "math/rand"
    "time"
    
    "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type Event struct {
    ID           int64
    EventType    string
    Topic        string
    PartitionKey string
    Payload      []byte
    RetryCount   int
    LastError    string
}

type OutboxWorker struct {
    shardID      int
    db           *sql.DB
    producer     *kafka.Producer
    locker       DistributedLock
    config       Config
    metrics      *Metrics
    notifyChan   chan struct{}
}

type Config struct {
    BatchSize    int
    PollInterval time.Duration
    MaxRetries   int
}

func NewWorker(shardID int, db *sql.DB, producer *kafka.Producer, locker DistributedLock, cfg Config) *OutboxWorker {
    return &OutboxWorker{
        shardID:    shardID,
        db:         db,
        producer:   producer,
        locker:     locker,
        config:     cfg,
        metrics:    NewMetrics(),
        notifyChan: make(chan struct{}, 1),
    }
}

func (w *OutboxWorker) Run(ctx context.Context) error {
    lockKey := fmt.Sprintf("outbox:shard:%d", w.shardID)
    lock, err := w.locker.AcquireWithRetry(ctx, lockKey, 30*time.Second)
    if err != nil {
        return err
    }
    defer lock.Release(ctx)
    
    go w.renewLock(ctx, lock)
    
    timer := time.NewTimer(w.config.PollInterval)
    defer timer.Stop()
    
    for {
        select {
        case <-ctx.Done():
            return nil
        case <-w.notifyChan:
        case <-timer.C:
        }
        
        if err := w.processBatch(ctx); err != nil {
            w.metrics.ErrorTotal.Inc()
        }
        
        timer.Reset(w.config.PollInterval)
    }
}

// ... (其他方法见上文)
```

---

**文档结束** | Version 1.0