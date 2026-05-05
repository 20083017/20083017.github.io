# 消息存储分库分表方案 v1.0

> 千万并发 IM 系统的存储分片、迁移、扩容与对账方案  
> 关键词：分片策略 / 在线扩容 / 数据迁移 / 一致性对账

## 目录
1. [设计目标与原则](#1-设计目标与原则)
2. [分片策略](#2-分片策略)
3. [核心表分片设计](#3-核心表分片设计)
4. [中间件选型](#4-中间件选型)
5. [扩容方案](#5-扩容方案)
6. [数据迁移](#6-数据迁移)
7. [对账机制](#7-对账机制)
8. [冷热分离与归档](#8-冷热分离与归档)
9. [备份与恢复](#9-备份与恢复)
10. [跨地域复制](#10-跨地域复制)
11. [性能基线](#11-性能基线)

---

# 1. 设计目标与原则

## 1.1 容量目标

| 指标 | 目标 |
|---|---|
| 日新增消息 | 20 亿条 |
| 总消息量（3 年） | ~2 万亿 |
| 单消息平均大小 | 500B（含元数据） |
| 总数据量（3 年） | ~1PB |
| 写入峰值 QPS | 50 万 |
| 查询峰值 QPS | 200 万 |
| 单查询 P99 | < 50ms |

## 1.2 设计原则

1. **分片键先行**：每张表必须明确分片键，避免跨片查询
2. **唯一索引必须包含分片键**：保证唯一性可在单分片内验证
3. **无 join**：跨分片不做 join，业务层组装
4. **冷热分离**：30 天内热数据 + 历史数据分层
5. **可扩容**：使用一致性 hash 或 slot 模型，平滑扩容
6. **可对账**：定期校验分片间一致性

## 1.3 分片维度选择

| 业务表 | 分片键 | 理由 |
|---|---|---|
| `im_message` | `conv_id` | 按会话查询是主路径 |
| `mention_index` | `user_id` | 按用户查 @我 是主路径 |
| `inbox` | `user_id` | 按用户拉离线消息 |
| `user_conv_cursor` | `user_id` | 按用户查游标 |
| `conversation_meta` | `conv_id` | 单条记录 |
| `group_member` | `group_id` | 按群查成员 |
| `user` | `user_id` | 按用户查 |
| `outbox_event` | `id` (range) | 顺序消费 |

---

# 2. 分片策略

## 2.1 三种主流策略对比

| 策略 | 优点 | 缺点 | 适用 |
|---|---|---|---|
| **HASH 取模** | 简单，均匀 | 扩容要 rehash 全部数据 | 不推荐生产 |
| **一致性 HASH** | 扩容只迁移部分 | 实现复杂，热点风险 | 中等规模 |
| **SLOT (类 Redis Cluster)** | 灵活，可手动 rebalance | 需要路由表 | **推荐** |
| **Range** | 范围查询好 | 容易热点 | 时序数据 |

## 2.2 推荐方案：SLOT 模型

```
1. 全局 16384 个 slot
2. 每个 slot 映射到一个物理分片（库.表）
3. 路由: slot = CRC32(shard_key) % 16384
4. 物理分片数可变 (16, 32, 64, 128 ...)
5. slot → shard 映射存配置中心 (etcd)
6. 扩容时按 slot 迁移
```

### 路由表示例

```yaml
# etcd: /im/sharding/im_message
slots:
  - range: [0, 511]      → shard: shard_00
  - range: [512, 1023]   → shard: shard_01
  - range: [1024, 1535]  → shard: shard_02
  ...
  - range: [16128, 16383] → shard: shard_31
shards:
  shard_00:
    db_host: "mysql-001:3306"
    db_name: "im_msg_00"
    table_count: 16   # 单库分 16 表
  ...
```

### 路由代码

```go
func ResolveShard(convID int64) (db, table string) {
    slot := crc32.ChecksumIEEE([]byte(strconv.FormatInt(convID, 10))) % 16384
    shard := slotToShard(slot)
    
    // 库内再分 16 表（按 conv_id 取模）
    tableIdx := convID % 16
    
    return shard.DBName, fmt.Sprintf("im_message_%02d", tableIdx)
}
```

## 2.3 双层分片：分库 + 分表

```
分库:    决定数据落在哪台 MySQL 实例（slot 模型）
分表:    决定数据落在该实例的哪张表

例:
  16 个 slot 一组 → 1 个库
  16 张表 = 1 个库内
  
  64 个分片库 × 16 张表 = 1024 张物理表
  支持 1024 × 5亿(MySQL推荐上限) = 5000亿行
```

## 2.4 分片键无法覆盖的查询

某些查询不走分片键，需要：

```
场景: 按 server_msg_id 查消息（撤回、引用）
方案 A: server_msg_id 编码 conv_id（雪花 ID 中预留位）
方案 B: 建二级映射表 server_msg_id → (conv_id, ...)
方案 C: 全分片广播查询（仅低频管理操作）

推荐 A: 雪花 ID 中嵌入 conv_id 的 hash 信息
```

### 雪花 ID 嵌入分片信息

```
| 1bit 0 | 41bit 时间戳 | 4bit shard_hint | 6bit machine | 12bit seq |

shard_hint = (conv_id % 16384) >> 10   // 低 4 位作为分片提示

通过 server_msg_id 反推时:
  shard_hint = (id >> 18) & 0xF
  全分片中只有 1/16 可能匹配 → 缩小搜索范围
```

---

# 3. 核心表分片设计

## 3.1 `im_message` 消息主表

### 物理布局
```
分库数:     32
单库表数:   16
总表数:     512
分片键:     conv_id

库命名:     im_msg_{00..31}
表命名:     im_message_{00..15}
```

### 完整定义

```sql
CREATE TABLE im_message_00 (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  app_id          INT NOT NULL,
  conv_id         BIGINT NOT NULL,
  sender_id       BIGINT NOT NULL,
  client_msg_id   VARCHAR(64) NOT NULL,
  server_msg_id   BIGINT NOT NULL,
  global_seq      BIGINT NOT NULL,
  visible_seq     BIGINT,
  msg_type        TINYINT NOT NULL,
  content         JSON NOT NULL,
  mention_all     TINYINT DEFAULT 0,
  mention_count   SMALLINT DEFAULT 0,
  reply_to_id     BIGINT,
  status          TINYINT DEFAULT 0,
  version         INT DEFAULT 1,
  send_time       BIGINT,
  created_at      BIGINT NOT NULL,
  updated_at      BIGINT,
  
  UNIQUE KEY uk_client (app_id, sender_id, conv_id, client_msg_id),
  UNIQUE KEY uk_server (server_msg_id),
  UNIQUE KEY uk_seq (conv_id, global_seq),
  KEY idx_visible (conv_id, visible_seq),
  KEY idx_created (conv_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 容量估算

```
单表行数:   5 亿（MySQL 推荐上限）
单库表数:   16 → 单库容纳 80 亿行
总库数:     32 → 总容纳 2560 亿行
单消息大小: 500B → 总数据 ~125TB

按日新增 20 亿 / 总 512 表 = 单表日增 ~400 万
单表寿命: 5 亿 / 400 万 = 125 天

→ 30 天后开始归档热数据，单表稳定在 1.2 亿行内
```

## 3.2 `mention_index` @ 索引

```
分库数:     16
单库表数:   16
总表数:     256
分片键:     user_id

为何按 user_id：主查询是"我被 @ 了什么"
```

```sql
CREATE TABLE mention_index_00 (
  user_id        BIGINT NOT NULL,
  conv_id        BIGINT NOT NULL,
  msg_seq        BIGINT NOT NULL,
  server_msg_id  BIGINT NOT NULL,
  sender_id      BIGINT NOT NULL,
  mention_type   TINYINT NOT NULL,
  status         TINYINT DEFAULT 0,
  created_at     BIGINT NOT NULL,
  
  PRIMARY KEY (user_id, conv_id, msg_seq),
  KEY idx_user_time (user_id, created_at DESC),
  KEY idx_msg (server_msg_id)
) ENGINE=InnoDB;
```

## 3.3 `inbox` 离线收件箱

```
分库数:     32
单库表数:   16
总表数:     512
分片键:     user_id
```

```sql
CREATE TABLE inbox_00 (
  user_id        BIGINT NOT NULL,
  conv_id        BIGINT NOT NULL,
  msg_seq        BIGINT NOT NULL,
  server_msg_id  BIGINT NOT NULL,
  created_at     BIGINT NOT NULL,
  
  PRIMARY KEY (user_id, conv_id, msg_seq),
  KEY idx_user_time (user_id, created_at)
) ENGINE=InnoDB;
```

## 3.4 `user_conv_cursor` 游标

```
分库数:     16
单库表数:   16
分片键:     user_id
```

## 3.5 `group_member` 群成员

```
分库数:     16
分片键:     group_id

注意: 单条记录的另一查询路径"用户在哪些群"
       建二级索引表 user_groups (user_id) 异步维护
```

```sql
CREATE TABLE user_groups (
  user_id   BIGINT,
  group_id  BIGINT,
  joined_at BIGINT,
  PRIMARY KEY (user_id, group_id)
) PARTITION BY HASH(user_id) PARTITIONS 64;
```

## 3.6 `outbox_event` 事件表

```
不分库分表（单库主备）
原因:
  - 顺序消费（Worker 按 ID 递增扫描）
  - 数��量小（事件发完即归档）
  - 单库 QPS 5 万足够

容量管理:
  - 已发送的 event 24h 后归档
  - 主表保持 < 1000 万行
```

---

# 4. 中间件选型

## 4.1 选型对比

| 中间件 | 类型 | 优点 | 缺点 |
|---|---|---|---|
| **ShardingSphere** | Java SDK/Proxy | 灵活、SQL 兼容 | 需要 SDK 集成 |
| **Vitess** | YouTube 开源 | 生产验证、自动 rebalance | 复杂度高 |
| **TiDB** | 分布式 SQL | 原生分布式、强一致 | 资源占用大 |
| **MyCat** | Proxy | 简单 | 社区一般 |
| **自研路由** | 业务层 | 完全可控 | 维护成本 |

## 4.2 推荐方案

```
方案 A (推荐): TiDB
  - 完全兼容 MySQL 协议
  - 自动分片 (Region) + 自动 rebalance
  - 强一致 + 高可用
  - 单消息表无需手动分库分表
  - 适合中大型 IM

方案 B: MySQL + ShardingSphere
  - 成熟度高
  - 团队 MySQL 经验丰富
  - 需手动维护分片
  - 适合存量 MySQL 体系

方案 C: 混合
  - 消息热数据: MySQL 分库分表 (写入快)
  - 历史归档: HBase / Cassandra (大容量)
  - 索引: Elasticsearch (搜索)
```

## 4.3 客户端 SDK 路由（自研）

```go
type ShardingClient struct {
    routeMap map[int]*sql.DB  // slot → DB
    routes   *RouteTable      // 从 etcd 加载
}

func (c *ShardingClient) Query(table string, shardKey int64, sql string, args ...interface{}) {
    slot := hash(shardKey) % 16384
    shardName := c.routes.GetShard(table, slot)
    db := c.routeMap[shardName]
    
    realTable := buildTableName(table, shardKey)
    realSQL := strings.Replace(sql, "{table}", realTable, -1)
    
    db.Query(realSQL, args...)
}

// 监听 etcd 路由变更
func (c *ShardingClient) WatchRoutes() {
    etcdClient.Watch("/im/sharding/", func(events []Event) {
        c.routes.Reload()
    })
}
```

---

# 5. 扩容方案

## 5.1 扩容触发条件

```
- 单库存储 > 70%
- 单库 QPS > 设计容量 70%
- 慢查询比例上升
- CPU 持续 > 70%
```

## 5.2 扩容步骤（SLOT 模式）

```
当前: 32 库 → 扩容到 64 库

阶段 1: 准备
  1.1 新建 32 个空库 (shard_32 ~ shard_63)
  1.2 配置主从、备份、监控

阶段 2: 数据迁移
  2.1 选择要迁移的 slot 范围
      原 shard_00 (slots 0-511) 拆分:
        slots 0-255   → 留 shard_00
        slots 256-511 → 迁到 shard_32
  2.2 全量同步 (binlog 起点记录)
  2.3 增量同步 (CDC tail binlog)
  2.4 双写阶段 (新写入两边都写)
  2.5 校验数据一致性

阶段 3: 切换
  3.1 更新 etcd 路由 (slot 256-511 → shard_32)
  3.2 路由热更新（< 5s 收敛）
  3.3 停止旧库的 256-511 slot 写入
  3.4 删除旧库的 256-511 slot 数据（延迟 7 天）

阶段 4: 验证
  4.1 监控新库 QPS / 错误率
  4.2 对账
```

## 5.3 在线迁移工具链

```
[Source MySQL]
     ↓ binlog
[Canal/Debezium]    ← CDC 工具
     ↓ Kafka topic
[Migration Worker]
     ↓
[Target MySQL]
     ↓
[Diff Worker]       ← 对账
```

## 5.4 双写降级方案

```
状态:
  WRITING_BOTH:    新旧双写，读旧
  READING_NEW:     双写，读新（验证期）
  STOPPED_OLD:     仅写新
  
切换步骤:
  Day 1: WRITING_BOTH (24h 验证)
  Day 2: READING_NEW (24h 灰度)
  Day 3: STOPPED_OLD
  
回滚:
  任何阶段发现问题 → 立即回退到 READING_OLD
```

## 5.5 客户端零停机切换

```go
// 路由热加载
func (c *ShardingClient) ReloadRoutes() {
    newRoutes := loadFromEtcd()
    
    // CAS 替换
    atomic.StorePointer(&c.routes, unsafe.Pointer(newRoutes))
    
    log.Info("routes reloaded", "version", newRoutes.Version)
}
```

---

# 6. 数据迁移

## 6.1 迁移类型

| 类型 | 场景 |
|---|---|
| 扩容迁移 | 增加分片 |
| 降配合并 | 减少分片 |
| 跨地域迁移 | 用户主区域变更 |
| 冷数据归档 | 30 天前数据归档 |
| 跨存储迁移 | MySQL → TiDB / HBase |

## 6.2 全量 + 增量迁移流程

### 步骤 1: binlog 起点记录

```sql
-- 在源库执行
SHOW MASTER STATUS;
+--------------+-----------+
| File         | Position  |
+--------------+-----------+
| binlog.0001  | 12345678  |
+--------------+-----------+

-- 记录此 GTID 作为增量起点
```

### 步骤 2: 全量同步

```bash
# 工具: mydumper + myloader
mydumper -h source-mysql -u root -p ... \
  --regex 'im_msg_00\.im_message_.*' \
  --rows 100000 \
  -t 16 \
  -o /backup/full/

myloader -h target-mysql -u root -p ... \
  -d /backup/full/ \
  -t 16
```

### 步骤 3: 增量同步

```yaml
# Canal 配置
canal.instance.master.address: source-mysql:3306
canal.instance.master.position: 12345678
canal.instance.master.journal.name: binlog.0001
canal.instance.filter.regex: im_msg_00\\.im_message_.*

# 输出到 Kafka
canal.mq.topic: db_migration_events
```

### 步骤 4: 应用层消费

```go
func (m *Migrator) Consume(event *BinlogEvent) error {
    // 解析 row 事件
    row := parseRow(event)
    
    // 路由到目标分片
    targetShard := m.targetRoutes.GetShard(row.ConvID)
    
    // 写入
    return m.writeToTarget(targetShard, row)
}
```

### 步骤 5: 数据对账（见第 7 节）

## 6.3 迁移性能优化

```
- 并发: 按表/分区并行迁移
- 批量: 1000 行一批 INSERT
- 关键索引后建: 数据导入后再 CREATE INDEX
- 关闭非必要约束: 临时关闭外键检查
- 限流: 不超过源库 30% IO
- 时段: 业务低峰期 (凌晨 2-6 点)
```

## 6.4 大表迁移分段策略

```
单表 5 亿行迁移:
  按主键 ID 分 100 段
  每段 500 万行
  10 个并发 worker 同时跑
  预计耗时: 6-12 小时
```

```sql
-- 分段查询
SELECT * FROM im_message_00 
WHERE id BETWEEN ? AND ?
ORDER BY id
LIMIT 10000;
```

---

# 7. 对账机制

## 7.1 对账维度

| 维度 | 频率 | 工具 |
|---|---|---|
| 行数对账 | 每小时 | SQL COUNT |
| 关键字段对账 | 每天 | Diff 工具 |
| 业务逻辑对账 | 每天 | 自研脚本 |
| 跨地域对账 | 每天 | 全局对账服务 |
| 缓存与 DB | 实时（采样） | 旁路 |

## 7.2 行数对账（最简）

```sql
-- 源库
SELECT COUNT(*) FROM im_message_00 
WHERE created_at BETWEEN ? AND ?;

-- 目标库
SELECT COUNT(*) FROM im_message_00 
WHERE created_at BETWEEN ? AND ?;

-- 一致 → OK
-- 不一致 → 进入字段对账
```

## 7.3 字段对账（CRC 校验）

```sql
-- 计算分段 checksum
SELECT 
  COUNT(*) as cnt,
  BIT_XOR(CRC32(CONCAT_WS('|', id, conv_id, content, status))) as chk
FROM im_message_00
WHERE id BETWEEN ? AND ?;
```

CRC 一致 → 数据一致；不一致 → 二分查找差异行。

## 7.4 业务对账

```python
# 关键业务规则
对账项:
  1. 每会话 visible_seq 是否连续
     SELECT conv_id, COUNT(DISTINCT visible_seq), MAX(visible_seq), MIN(visible_seq)
     FROM im_message
     WHERE visible_seq IS NOT NULL
     GROUP BY conv_id
     HAVING COUNT(*) != MAX - MIN + 1
  
  2. 每用户 inbox 与 message 一致
     用户 U 的 inbox 数 == U 加入会话后的 visible 消息数
  
  3. 撤回消息状态一致
     status=1 的消息必须有 message_recall 记录
  
  4. mention_index 与 message.mentions 一致
     展开 message.content.mentions 与 mention_index 行数相等
```

## 7.5 对账工具实现

```go
type Reconciler struct {
    sourceDB *sql.DB
    targetDB *sql.DB
}

func (r *Reconciler) RunCheck(table string, timeRange [2]int64) error {
    // 分段对账
    const segmentSize = 100000
    
    minID := r.queryMinID(table, timeRange)
    maxID := r.queryMaxID(table, timeRange)
    
    var diffs []DiffRecord
    for start := minID; start <= maxID; start += segmentSize {
        end := min(start + segmentSize - 1, maxID)
        
        sourceChecksum := r.checksumSegment(r.sourceDB, table, start, end)
        targetChecksum := r.checksumSegment(r.targetDB, table, start, end)
        
        if sourceChecksum != targetChecksum {
            // 详细 diff
            diffs = append(diffs, r.detailDiff(table, start, end)...)
        }
    }
    
    return r.report(diffs)
}
```

## 7.6 自动修复

```
检测到差异:
  Level 1 (< 100 行): 自动补写
  Level 2 (100-10K): 通知 SRE，半自动
  Level 3 (> 10K):   告警，人工介入
  
修复策略:
  - 以源库为准（迁移期）
  - 以最新 updated_at 为准（双向写时）
  - 业务规则裁决（如最大 seq 为准）
```

---

# 8. 冷热分离与归档

## 8.1 分层存储

```
┌──────────────────────────────────────────────┐
│ 热层 (Hot)        : 最近 30 天                │
│ MySQL 主表        : 高 QPS, 低延迟            │
└──────────────────────────────────────────────┘
                    ↓ 归档
┌──────────────────────────────────────────────┐
│ 温层 (Warm)       : 30 天 - 1 年              │
│ MySQL 归档表 / TiDB : 中等查询                 │
└──────────────────────────────────────────────┘
                    ↓ 归档
┌──────────────────────────────────────────────┐
│ 冷层 (Cold)       : 1 年以上                  │
│ HBase / OSS       : 大容量, 低成本             │
└──────────────────────────────────────────────┘
```

## 8.2 归档调度

```
每日凌晨 02:00 执行:
  1. 查询 30 天前的数据
  2. 写入归档表
  3. 校验
  4. 删除原表
  
INSERT INTO im_message_archive 
SELECT * FROM im_message 
WHERE created_at < UNIX_TIMESTAMP() - 30*86400;

DELETE FROM im_message 
WHERE created_at < UNIX_TIMESTAMP() - 30*86400
LIMIT 10000;  -- 分批删，防长事务
```

## 8.3 归档查询

```go
func (s *MsgService) GetMessage(serverMsgID int64) (*Message, error) {
    // 1. 先查热表
    msg, err := s.queryHot(serverMsgID)
    if err == nil {
        return msg, nil
    }
    
    // 2. 查归档
    msg, err = s.queryArchive(serverMsgID)
    if err == nil {
        return msg, nil
    }
    
    // 3. 查冷存储 (HBase)
    return s.queryHBase(serverMsgID)
}
```

## 8.4 HBase RowKey 设计

```
RowKey: reverse(conv_id) + visible_seq

为何 reverse: 防止热点（连续 conv_id 集中在一个 region）

查询:
  按会话查: scan rowkey prefix
  按 ID 查: 走 server_msg_id 二级索引
```

## 8.5 归档保留策略

```
普通用户:    1 年
VIP / 企业: 3 年
法律合规:    7 年（部分场景）
彻底删除:    用户主动注销 → 30 天后 GDPR 删除
```

---

# 9. 备份与恢复

## 9.1 备份策略

| 类型 | 频率 | 保留 | 介质 |
|---|---|---|---|
| 全量备份 | 每周 | 4 周 | OSS |
| 增量备份 | 每天 | 7 天 | OSS |
| binlog 备份 | 实时 | 30 天 | OSS |
| 异地备份 | 每天 | 30 天 | 跨区域 OSS |

## 9.2 备份工具

```bash
# 物理备份: xtrabackup
xtrabackup --backup --target-dir=/backup/$(date +%F) \
  --user=backup --password=...

# 逻辑备份: mydumper
mydumper -h ... --regex '...' -o /backup/dump-$(date +%F)/

# binlog 持续上传
mysqlbinlog --read-from-remote-server ... | gzip | aws s3 cp - s3://...
```

## 9.3 恢复演练

```
每季度演练:
  1. 选定备份点
  2. 在隔离环境恢复
  3. 验证数据完整性
  4. 测试业务可用性
  5. 记录 RTO / RPO

RTO 目标:
  - 单表恢复: < 1 小时
  - 单库恢复: < 4 小时
  - 整集群恢复: < 12 小时

RPO 目标: < 1 分钟
```

## 9.4 误删除应对

```
应急流程:
  1. 立即停止写入相关表 (kill 开关)
  2. 确认误删范围 (binlog 分析)
  3. 从最近全备 + binlog 重放到误删前
  4. 导出受影响数据
  5. 写回主库
  6. 业务核对

工具: gh-ost (binlog 反向应用)
```

---

# 10. 跨地域复制

## 10.1 复制拓扑

```
华东 (主)              华南 (从)            美西 (从)
   │                     │                    │
   ├── MySQL 主 ─binlog→ MySQL 异步从 ─→ MySQL 异步从
   ├── Redis ──────────→ Redis (双向同步)
   └── Kafka ─Mirror→ Kafka ─Mirror→ Kafka
```

## 10.2 一致性级别

| 数据 | 一致性 | 同步方式 |
|---|---|---|
| 用户主区消息 | 强一致 | 同步写主区 |
| 跨区消息 | 最终一致 | Kafka MirrorMaker (50-200ms) |
| 用户资料 | 最终一致 | binlog 异步 |
| 群成员 | 最终一致 | 主区���准 |
| 在线状态 | 区域内 | 不同步 |
| 配置 | 强一致 | etcd 跨区集群 |

## 10.3 跨区写冲突处理

```
冲突场景: 用户在两个区都做了"修改昵称"
  时间戳大的胜出
  或 LWW (Last Write Wins) 策略

冲突场景: 用户在两个区都登录
  按 device_id 区分会话
  禁止同 device_id 双登
```

## 10.4 网络分区处理

```
华东 ⇸ 华南 网络断:
  双方各自服务（CP 模式: 拒绝跨区操作）
  恢复后: 异步合并
  冲突按规则裁决

监控:
  跨区延迟 > 1s 告警
  跨区中断 > 30s 触发降级
```

---

# 11. 性能基线

## 11.1 单实例性能

| 操作 | QPS | 延迟 P99 |
|---|---|---|
| 单行 INSERT | 8,000 | 5ms |
| 单行点查 | 30,000 | 2ms |
| 范围扫描 (100 行) | 5,000 | 10ms |
| 单事务（多语句） | 3,000 | 15ms |

## 11.2 集群整体（32 库）

| 操作 | QPS |
|---|---|
| 写入 | 25 万 |
| 点查 | 100 万 |
| 范围查询 | 15 万 |

## 11.3 容量规划公式

```
分库数 = ceil(峰值写 QPS / 单库写 QPS × 安全系数)
        = ceil(50万 / 8千 × 2)
        = 125
        → 选 128（2 的幂）
        
        实际 32 也够用，因为多数库不会同时打满
```

## 11.4 慢查询管控

```
监控:
  - slow_query_log 阈值 100ms
  - 每日 slow query 数 < 总 QPS 万分之一
  - 慢查询 TOP 10 邮件日报

治理:
  - 缺索引 → 加索引 (online DDL)
  - 不走分片键 → 业务改造
  - 大事务 → 拆分
```

---

**文档结束**

*Version 1.0 | 消息存储分库分表方案*