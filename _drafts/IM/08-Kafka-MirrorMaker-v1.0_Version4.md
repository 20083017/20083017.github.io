# 跨地域 Kafka MirrorMaker 详细配置 v1.0

> 适用：跨地域消息复制、灾备、活跃-活跃多地域部署  
> 版本：MirrorMaker 2.0 (Kafka 2.4+)  
> 目标：低延迟、可控带宽、容错、可观测

---

## 目录

1. 设计背景与目标
2. MM2 vs MM1
3. 部署拓扑
4. 配置详解
5. Topic 复制策略
6. 一致性保证
7. 性能调优
8. 故障处理
9. 监控指标
10. 跨地域 IM 实战

---

# 1. 设计背景与目标

## 1.1 为什么需要跨地域复制

```
1. 多地域用户消息互通
2. 灾备 (一个地域整体挂掉)
3. 流量就近接入
4. 数据合规 (各地保留本地副本)
```

## 1.2 设计目标

| 指标 | 目标 |
|---|---|
| 复制延迟 P99 | < 200ms（大陆内）/ < 500ms（跨大陆） |
| 数据完整性 | 0 丢失（at-least-once） |
| 吞吐 | 100 MB/s 单连接 |
| 故障恢复 | < 30s |
| Topic 同步 | 自动 |
| ACL 同步 | 自动 |

## 1.3 跨地域模式

### Active-Standby（主备）
```
华东 (Active) ────→ 华南 (Standby)
        ↑
   所有写入

华东挂 → 切换到华南
```

### Active-Active（双活）
```
华东 (Active) ←──→ 华南 (Active)
   写本地         写本地
   读本地+对端    读本地+对端
```

IM 推荐 **Active-Active** + **就近写入**模式。

---

# 2. MM2 vs MM1

## 2.1 对比

| 特性 | MM1 | MM2 |
|---|---|---|
| 实现 | 独立进程 | Kafka Connect |
| Topic 自动创建 | ❌ | ✅ |
| ACL 同步 | ❌ | ✅ |
| Offset 同步 | ❌ | ✅ |
| 自动 failover | ❌ | ✅ |
| 多集群拓扑 | 难 | 简单 |
| 监控 | 弱 | 完善 |
| 推荐版本 | 弃用 | ✅ 必选 |

**MM2 是唯一选择。**

## 2.2 MM2 核心组件

```
- MirrorSourceConnector:    跨集群复制数据
- MirrorCheckpointConnector: 同步消费者 offset
- MirrorHeartbeatConnector:  集群间健康检查
```

---

# 3. 部署拓扑

## 3.1 Active-Active 双地域

```
┌──────────────────────────────────────────────────┐
│                  华东 (East) 集群                  │
│                                                   │
│  Topic: msg.fanout.normal           (本地写入)    │
│  Topic: msg.fanout.normal.east_to_south (复制来源)│
│  Topic: south.msg.fanout.normal     (来自华南的)  │
└────────┬─────────────────────────────────────────┘
         │
         │ MirrorMaker 2 (双向)
         │
┌────────▼─────────────────────────────────────────┐
│                  华南 (South) 集群                 │
│                                                   │
│  Topic: msg.fanout.normal           (本地写入)    │
│  Topic: east.msg.fanout.normal      (来自华东的)  │
└──────────────────────────────────────────────────┘
```

### 命名规则
```
{source_alias}.{topic_name}

east.msg.fanout.normal    ← 华南集群中,来自华东的副本
south.msg.fanout.normal   ← 华东集群中,来自华南的副本
```

## 3.2 三地域 Mesh

```
        ┌──────┐
        │ East │
        └──┬───┘
           │
    ┌──────┴──────┐
    │             │
┌───▼───┐    ┌───▼───┐
│ South │←──→│  US   │
└───────┘    └───────┘
```

每个集群与其他集群双向复制。

## 3.3 MM2 部署模式

### 模式 1：Connect 集群部署（推荐）
```
独立 Kafka Connect 集群
运行 MM2 Connectors
- 单独的 worker 节点
- 易于扩展
- 可控
```

### 模式 2：嵌入到 Source/Target Kafka
```
不推荐，影响 Kafka 性能
```

### 部署位置选择

```
推荐: 部署在目标地域
理由:
  - 消费者在 target，写入更快
  - source 网络问题时不阻塞
  - 反压控制在 target

例：复制 East → South
   MM2 部署在 South 集群附近
```

---

# 4. 配置详解

## 4.1 主配置文件 `mm2.properties`

```properties
# ============================================
# 集群定义
# ============================================
clusters = east, south

east.bootstrap.servers = kafka-east-1:9092,kafka-east-2:9092,kafka-east-3:9092
south.bootstrap.servers = kafka-south-1:9092,kafka-south-2:9092,kafka-south-3:9092

# 安全配置
east.security.protocol = SASL_SSL
east.sasl.mechanism = PLAIN
east.sasl.jaas.config = org.apache.kafka.common.security.plain.PlainLoginModule required username="..." password="...";

south.security.protocol = SASL_SSL
south.sasl.mechanism = PLAIN
south.sasl.jaas.config = ...

# ============================================
# 复制流定义 (东 ←→ 南 双向)
# ============================================
east->south.enabled = true
south->east.enabled = true

# ============================================
# Topic 复制规则
# ============================================
east->south.topics = msg\\..*, presence\\..*, user\\.behavior
east->south.topics.exclude = .*\\.internal\\.*, .*-changelog, .*-repartition

south->east.topics = msg\\..*, presence\\..*
south->east.topics.exclude = .*\\.internal\\.*

# ============================================
# Consumer Group offset 同步
# ============================================
east->south.groups = .*
east->south.groups.exclude = console-consumer-.*, mirror-maker-.*

south->east.groups = .*

# ============================================
# 复制因子 / 分区
# ============================================
replication.factor = 3
checkpoints.topic.replication.factor = 3
heartbeats.topic.replication.factor = 3
offset-syncs.topic.replication.factor = 3

# ============================================
# 复制策略
# ============================================
# 自动同步 source 的 ACL
sync.topic.acls.enabled = true
# 自动同步 source 的 topic 配置
sync.topic.configs.enabled = true
# 是否启用 group offset 同步
emit.checkpoints.enabled = true
emit.checkpoints.interval.seconds = 60

# 心跳间隔
emit.heartbeats.enabled = true
emit.heartbeats.interval.seconds = 5

# ============================================
# 复制重命名规则 (默认: source.topic_name)
# ============================================
replication.policy.class = org.apache.kafka.connect.mirror.DefaultReplicationPolicy
# 或自定义: 不加前缀 (谨慎，可能导致循环复制)
# replication.policy.class = com.example.IdentityReplicationPolicy

# ============================================
# 性能配置
# ============================================
tasks.max = 16

# Source connector
east->south.tasks.max = 16
south->east.tasks.max = 16

# Producer 配置 (写入 target)
east->south.producer.compression.type = lz4
east->south.producer.acks = all
east->south.producer.batch.size = 65536
east->south.producer.linger.ms = 5
east->south.producer.max.in.flight.requests.per.connection = 5
east->south.producer.enable.idempotence = true

# Consumer 配置 (读取 source)
east->south.consumer.fetch.min.bytes = 65536
east->south.consumer.fetch.max.wait.ms = 500
east->south.consumer.max.poll.records = 5000

# ============================================
# 限流（防止打爆带宽）
# ============================================
east->south.replication.factor = 3
east->south.target.cluster.alias = south
east->south.source.cluster.alias = east

# 单 task 最大字节/秒
east->south.producer.max.request.size = 10485760
east->south.consumer.max.partition.fetch.bytes = 10485760
```

## 4.2 Connect Worker 配置 `connect-distributed.properties`

```properties
bootstrap.servers = kafka-south-1:9092,kafka-south-2:9092,kafka-south-3:9092
group.id = mm2-connect-cluster
key.converter = org.apache.kafka.connect.converters.ByteArrayConverter
value.converter = org.apache.kafka.connect.converters.ByteArrayConverter

# 内部 topic
config.storage.topic = mm2-configs
config.storage.replication.factor = 3
offset.storage.topic = mm2-offsets
offset.storage.replication.factor = 3
status.storage.topic = mm2-status
status.storage.replication.factor = 3

# REST API
listeners = HTTP://0.0.0.0:8083
rest.advertised.host.name = mm2-worker-1

# 资源
producer.buffer.memory = 67108864
consumer.fetch.max.bytes = 52428800
```

## 4.3 启动

```bash
# 方式 1: 命令行直接运行 MM2
bin/connect-mirror-maker.sh mm2.properties

# 方式 2: Connect 集群运行 (推荐生产环境)
bin/connect-distributed.sh connect-distributed.properties

# 注册 connector
curl -X POST http://mm2-worker:8083/connectors \
  -H "Content-Type: application/json" \
  -d @mirror-source-connector.json
```

### Connector JSON 示例

```json
{
  "name": "east-to-south-source",
  "config": {
    "connector.class": "org.apache.kafka.connect.mirror.MirrorSourceConnector",
    "tasks.max": "16",
    
    "source.cluster.alias": "east",
    "target.cluster.alias": "south",
    
    "source.cluster.bootstrap.servers": "kafka-east-1:9092",
    "target.cluster.bootstrap.servers": "kafka-south-1:9092",
    
    "source.cluster.security.protocol": "SASL_SSL",
    "source.cluster.sasl.mechanism": "PLAIN",
    "source.cluster.sasl.jaas.config": "...",
    
    "target.cluster.security.protocol": "SASL_SSL",
    "target.cluster.sasl.mechanism": "PLAIN",
    "target.cluster.sasl.jaas.config": "...",
    
    "topics": "msg\\..*, presence\\..*",
    "topics.exclude": ".*\\.internal\\..*",
    
    "replication.factor": "3",
    "sync.topic.configs.enabled": "true",
    "sync.topic.acls.enabled": "true",
    
    "producer.override.compression.type": "lz4",
    "producer.override.acks": "all",
    "producer.override.enable.idempotence": "true",
    "producer.override.max.in.flight.requests.per.connection": "5"
  }
}
```

---

# 5. Topic 复制策略

## 5.1 哪些 Topic 需要复制

| Topic | 是否复制 | 备注 |
|---|---|---|
| `msg.fanout.normal` | ✅ | 跨地域用户消息 |
| `msg.fanout.large` | ✅ | 同上 |
| `msg.fanout.vip` | ✅ | 同上 |
| `msg.push.high` | ⚠️ | 视情况，push 通常本地处理 |
| `msg.recall` | ✅ | 撤回要全局生效 |
| `msg.read` | ⚠️ | 已读回执，可不跨域 |
| `presence.event` | ❌ | 在线状态本地用 |
| `user.behavior` | ✅ | 风控全局分析 |
| `audit.log` | ✅ | 合规审计 |
| `search.index` | ❌ | 搜索本地建索引 |
| `*.dlq` | ❌ | DLQ 不复制 |

## 5.2 复制规则配置

```properties
# 使用正则
east->south.topics = msg\\.fanout\\..*, msg\\.recall, user\\.behavior, audit\\..*

# 排除
east->south.topics.exclude = .*\\.dlq, presence\\..*, search\\..*

# 黑名单优先级 > 白名单
```

## 5.3 防止循环复制

**关键问题**：如果 East 和 South 互相复制 `msg.fanout.normal`，会不会产生无限循环？

MM2 用 **DefaultReplicationPolicy** 自动重命名：

```
East 集群:
  msg.fanout.normal           ← 本地写入
  south.msg.fanout.normal     ← 来自 South 的副本

South 集群:
  msg.fanout.normal           ← 本地写入
  east.msg.fanout.normal      ← 来自 East 的副本
```

复制 `east.msg.fanout.normal` 到 East？  
→ 重命名后变成 `south.east.msg.fanout.normal` → 不是匹配的 topic → 不复制。

实际上 MM2 会**检测前缀**，避免复制已经是副本的 topic。

## 5.4 自定义重命名

如果想让副本 topic 名字干净（不带前缀），用 `IdentityReplicationPolicy`：

```java
public class IdentityReplicationPolicy implements ReplicationPolicy {
    @Override
    public String formatRemoteTopic(String sourceClusterAlias, String topic) {
        return topic;  // 不重命名
    }
    
    @Override
    public String topicSource(String topic) {
        return null;  // 无法识别源
    }
}
```

⚠️ 警告：使用 IdentityReplicationPolicy **必须确保不会循环复制**，否则灾难。  
做法：在配置里**单向只复制特定 topic**：

```properties
east->south.topics = msg.fanout.normal
south->east.topics = ""   # 反向不复制相同 topic
```

## 5.5 IM 推荐方案

**用 DefaultReplicationPolicy + 消费者订阅多 topic**：

```
消费者代码:
subscribe(["msg.fanout.normal", "east.msg.fanout.normal", "south.msg.fanout.normal"])
```

或者用通配符：
```
subscribe("*msg.fanout.normal")
```

业务侧透明合并本地和远程消息。

---

# 6. 一致性保证

## 6.1 复制语义

```
MM2 默认: at-least-once
  - 不丢
  - 可能重复
  
要求消费者幂等
```

## 6.2 Offset 同步

MM2 用 `MirrorCheckpointConnector` 同步消费 offset：

```
Source 集群:
  consumer-group-A 在 topic-X 的 offset = 1000
  
Checkpoint 写入:
  topic: south.checkpoints.internal
  msg:   "consumer-group-A" → "topic-X" → offset 1000

Target 集群（消费者切换过来时）:
  从 checkpoint 恢复 offset
  在 east.topic-X 上从对应 offset 继续消费
```

注意：offset 在不同集群里**数值不同**，但 MM2 会维护映射关系。

## 6.3 Failover 流程

```
场景: East 挂掉，业务切到 South

Step 1: 消费者从 East 切换到 South
   - 读取 South 的 checkpoint
   - 恢复 East 集群消费 offset
   - 在 South 集群对应 topic (east.topic-X) 上继续消费

Step 2: 生产者也切到 South
   - 写本地 topic
   - 等 East 恢复后再同步回去
```

## 6.4 Failback

```
East 恢复后:
  - South → East 复制照常
  - East 之前的副本 topic 仍存在
  - 业务可选择切回 East
```

---

# 7. 性能调优

## 7.1 吞吐瓶颈定位

```
1. 网络带宽
2. Producer 批次大小
3. Consumer fetch 大小
4. Task 并行度
5. 压缩
```

## 7.2 调优参数

### 增大批次

```properties
east->south.producer.batch.size = 524288       # 512KB
east->south.producer.linger.ms = 20
east->south.producer.compression.type = lz4
```

### 增加并行

```properties
east->south.tasks.max = 32   # 与 partition 数匹配
```

每个 task 处理一组 partitions，task 数 ≤ 总 partition 数。

### 增大 fetch

```properties
east->south.consumer.fetch.min.bytes = 1048576    # 1MB
east->south.consumer.fetch.max.wait.ms = 500
east->south.consumer.max.partition.fetch.bytes = 10485760
```

### 缓冲

```properties
producer.buffer.memory = 134217728   # 128MB
```

## 7.3 带宽控制

```properties
# 限制单个 producer 的字节/秒
east->south.producer.max.request.size = 10485760
```

或在网络层用 QoS 限制 MM2 worker 的出口带宽。

## 7.4 性能基线

```
单 task: 30~50 MB/s
16 task: 500~800 MB/s
32 task: 800~1500 MB/s

单 task 延迟: 50~100ms
P99 延迟:    < 200ms (RTT < 50ms 的网络)
```

---

# 8. 故障处理

## 8.1 故障矩阵

| 故障 | 影响 | 恢复 |
|---|---|---|
| MM2 worker 挂 | 该 task 暂停 | Connect 自动调度到其他 worker |
| Source Kafka 挂 | 复制暂停 | 等待恢复，offset 保留，自动追赶 |
| Target Kafka 挂 | 复制失败 | 等待恢复 |
| 网络分区 | 复制延迟增加 | 网络恢复后追赶 |
| Topic 不存在 | 自动创建 | 默认行为 |

## 8.2 复制延迟告警

```
监控: kafka_consumer_lag (MM2 consumer)
告警: lag > 10000 持续 1 分钟

排查:
  - 网络是否正常？
  - Worker 是否健康？
  - 目标 Kafka 是否能写入？
  - 带宽是否足够？
```

## 8.3 数据校验

```bash
# 对比两端 topic 的 offset
kafka-consumer-groups --bootstrap-server east:9092 \
  --describe --group mm2-east-to-south

kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list south:9092 \
  --topic east.msg.fanout.normal
```

定期对账：

```python
def verify_replication():
    east_total = count_messages("kafka-east", "msg.fanout.normal", time_range)
    south_total = count_messages("kafka-south", "east.msg.fanout.normal", time_range)
    
    diff_pct = abs(east_total - south_total) / east_total
    if diff_pct > 0.01:
        alert("MM2 lag/loss detected: %.2f%%" % (diff_pct * 100))
```

## 8.4 回填

如果 MM2 长时间故障导致数据丢失：

```
方案 1: 重置 offset 重新复制
  缺点：会重复
  适合：消费侧幂等

方案 2: 业务层重发
  从 DB / 备份恢复
```

---

# 9. 监控指标

## 9.1 关键指标

| 指标 | 含义 |
|---|---|
| `kafka_connect_mirror_source_connector_record_age_ms` | 复制延迟 |
| `kafka_connect_mirror_source_connector_record_rate` | 复制速率 |
| `kafka_connect_mirror_source_connector_byte_rate` | 复制带宽 |
| `kafka_connect_mirror_source_connector_replication_latency_ms` | 端到端延迟 |
| `kafka_connect_task_status` | Task 健康状态 |

## 9.2 JMX 暴露

```
mirror-source-connector → MBean: kafka.connect:type=mirror-source-connector-metrics
mirror-checkpoint-connector → MBean: kafka.connect:type=mirror-checkpoint-connector-metrics
```

## 9.3 Prometheus 抓取

```yaml
- job_name: 'mm2'
  static_configs:
    - targets: ['mm2-worker-1:8083', 'mm2-worker-2:8083']
  metrics_path: /metrics
```

## 9.4 Grafana 大盘

```
Panel 1: 各 source-target 对的复制速率
Panel 2: 复制延迟分布
Panel 3: Task 健康状态
Panel 4: 各 topic 复制 lag
Panel 5: 网络带宽利用率
Panel 6: 错误率
```

---

# 10. 跨地域 IM 实战

## 10.1 IM 复制需求

```
1. 用户跨地域消息
2. 撤回事件全局生效
3. 离线消息存储跨地域备份
4. 风控数据集中分析
5. 合规审计
```

## 10.2 拓扑设计

```
              ┌─────────────┐
              │ 全球路由层    │
              │ (DNS/GSLB)   │
              └──────┬───────┘
                     │
       ┌─────────────┼─────────────┐
       │             │             │
   ┌───▼───┐    ┌───▼───┐    ┌───▼───┐
   │ East  │←──→│ South │←──→│  US   │
   │       │    │       │    │       │
   │ Kafka │    │ Kafka │    │ Kafka │
   └───────┘    └───────┘    └───────┘
       ↑            ↑            ↑
       │            │            │
   ┌───┴───┐    ┌───┴───┐    ┌───┴───┐
   │ Users │    │ Users │    │ Users │
   └───────┘    └───────┘    └───────┘
```

## 10.3 消息流

```
场景: 上海用户 A 给广州用户 B 发消息

1. A 连接华东 Gateway
2. 消息写入华东 Kafka: msg.fanout.normal
3. 华东 MsgWrite 处理
4. MM2 复制到华南: east.msg.fanout.normal
5. 华南 Deliver 消费 east.msg.fanout.normal
6. 投递到 B (在华南 Gateway)
```

## 10.4 撤回事件全局复制

```
A 撤回消息 → East 写 msg.recall

MM2:
  East → South: msg.recall → south.msg.recall
  East → US:    msg.recall → us.msg.recall

各地域消费者:
  消费本地 msg.recall + 远程副本
  对所有地域生效
```

## 10.5 用户归属与就近写入

```
用户元数据: home_region (East/South/US)

接入:
  - GSLB 按 IP 路由到最近接入
  - 临时跨域接入（如出差）允许，但写入仍走主分片

消息存储:
  - 用户 A 主分片在 East
  - A 在 South 发消息，先写到 East（跨域 RPC）
  - 或：写本地 + 异步同步

推荐:
  - 私聊：发送方主区域写
  - 群聊：群主区域写
```

## 10.6 灾备演练

```
模拟 East 集群挂掉:
1. GSLB 切流到 South / US
2. 用户重连到其他地域
3. 消费者从 South 集群消费 east.msg.fanout.normal 副本
4. 写入也切到 South 本地

恢复后:
1. East 重新上线
2. South → East MM2 把累积数据同步过去
3. 灰度切回 East
```

## 10.7 合规与数据本地化

```
GDPR 等法规要求数据不出境:

方案:
  - 用户数据按 home_region 分区
  - 跨域复制只复制必要 topic
  - 敏感字段在跨域时脱敏
  - 审计日志各地域独立保留
```

---

# 附录：完整部署示例

## A.1 Docker Compose

```yaml
version: '3'
services:
  mm2-worker:
    image: confluentinc/cp-kafka-connect:7.5.0
    ports:
      - "8083:8083"
    environment:
      CONNECT_BOOTSTRAP_SERVERS: kafka-south:9092
      CONNECT_REST_ADVERTISED_HOST_NAME: mm2-worker
      CONNECT_GROUP_ID: mm2-cluster
      CONNECT_CONFIG_STORAGE_TOPIC: mm2-configs
      CONNECT_OFFSET_STORAGE_TOPIC: mm2-offsets
      CONNECT_STATUS_STORAGE_TOPIC: mm2-status
      CONNECT_KEY_CONVERTER: org.apache.kafka.connect.converters.ByteArrayConverter
      CONNECT_VALUE_CONVERTER: org.apache.kafka.connect.converters.ByteArrayConverter
      CONNECT_PLUGIN_PATH: /usr/share/java
    volumes:
      - ./jaas.conf:/etc/kafka/jaas.conf
```

## A.2 Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mm2-worker
  namespace: kafka
spec:
  replicas: 4
  selector:
    matchLabels:
      app: mm2-worker
  template:
    metadata:
      labels:
        app: mm2-worker
    spec:
      containers:
      - name: mm2
        image: confluentinc/cp-kafka-connect:7.5.0
        ports:
        - containerPort: 8083
        env:
        - name: CONNECT_BOOTSTRAP_SERVERS
          value: "kafka-south:9092"
        - name: CONNECT_GROUP_ID
          value: "mm2-cluster"
        # ...
        resources:
          requests:
            cpu: 4
            memory: 8Gi
          limits:
            cpu: 8
            memory: 16Gi
```

## A.3 注册脚本

```bash
#!/bin/bash

CONNECT_URL="http://mm2-worker:8083"

# East → South source connector
curl -X POST $CONNECT_URL/connectors \
  -H "Content-Type: application/json" \
  -d @east-to-south-source.json

# East → South checkpoint connector
curl -X POST $CONNECT_URL/connectors \
  -H "Content-Type: application/json" \
  -d @east-to-south-checkpoint.json

# East → South heartbeat connector
curl -X POST $CONNECT_URL/connectors \
  -H "Content-Type: application/json" \
  -d @east-to-south-heartbeat.json

# 状态检查
curl $CONNECT_URL/connectors/east-to-south-source/status
```

---

**文档结束** | Version 1.0