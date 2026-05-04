# IM 消息存储分库分表方案 v1.0

> 适用规模：日新增 100 亿消息  
> 存储介质：MySQL/TiDB（主存）+ HBase（冷存）+ ES（搜索）

---

## 目录

1. [总体存储策略](#1-总体存储策略)
2. [分片策略](#2-分片策略)
3. [分片键选择](#3-分片键选择)
4. [冷热分离](#4-冷热分离)
5. [扩容方案](#5-扩容方案)
6. [数据迁移](#6-数据迁移)
7. [对账机制](#7-对账机制)
8. [备份与恢复](#8-备份与恢复)
9. [运维操作手册](#9-运维操作手册)

---

# 1. 总体存储策略

## 1.1 数据分层

```
┌──────────────────────────────────────────────┐
│  热数据 (0~7 天)                              │
│  MySQL/TiDB 主表                              │
│  - 在线消息读写                                │
│  - 单消息 < 1KB                                │
└──────────────────────────────────────────────┘
                  │ 异步迁移
                  ▼
┌──────────────────────────────────────────────┐
│  温数据 (7~30 天)                             │
│  MySQL/TiDB 归档表 + 缓存                      │
│  - 历史消息查询                                │
└──────────────────────────────────────────────┘
                  │ 批量归档
                  ▼
┌──────────────────────────────────────────────┐
│  冷数据 (> 30 天)                             │
│  HBase + 对象存储                              │
│  - 漫游 / 合规 / 审计                          │
└──────────────────────────────────────────────┘
                  │ 索引同步
                  ▼
┌──────────────────────────────────────────────┐
│  搜索索引                                     │
│  Elasticsearch                                │
│  - 全文搜索                                   │
└──────────────────────────────────────────────┘
```

## 1.2 选型理由

| 层 | 选型 | 理由 |
|---|---|---|
| 热 | TiDB（推荐） | 自动分片、强一致、HTAP |
| 热 | MySQL（备选） | 成熟稳定、运维熟悉 |
| 温 | 同热层（不同表） | 避免冷数据撑爆主表 |
| 冷 | HBase | 海量、低成本、按 RowKey 顺序读 |
| 搜索 | Elasticsearch | 全文检索、聚合分析 |
| 文件 | OSS/S3 | 海量大文件、CDN |

## 1.3 容量预估

```
日消息量:        100 亿
单消息平均:      512 字节
日新增数据:      5TB（含索引）
30 天热+温:      150TB
1 年冷数据:      1.5PB

单表上限 (MySQL): 5 亿行
推荐单表 200GB 内
```

---

# 2. 分片策略

## 2.1 分片维度

IM 消息有几个候选分片键：

| 维度 | 优点 | 缺点 |
|---|---|---|
| `conv_id` | 同会话消息聚合，查询友好 | 大群单 conv 热点 |
| `user_id` | 用户消息聚合 | 群消息不直接归属用户 |
| `time` | 易归档 | 写热点（永远写最新分片） |
| `server_msg_id` | 完全打散 | 查询要全分片扫 |

## 2.2 推荐方案：双分片键

主表按 `conv_id` 分片（业务读），收件箱按 `user_id` 分片（用户拉取）。

### 消息主表 `im_message`：按 `conv_id` 分片

```
分库:   32 库 (db_0 ~ db_31)
分表:   每库 16 表 (msg_0 ~ msg_15)
总分片: 512

定位规则:
  shard_key = hash(conv_id) % 512
  db_index  = shard_key / 16
  table_idx = shard_key % 16

例: conv_id=12345
  hash(12345) = 0x7A3B → 0x7A3B % 512 = 251
  db_index   = 251 / 16 = 15  → db_15
  table_idx  = 251 % 16 = 11  → msg_11
  实际表名:    db_15.msg_11
```

### 离线收件箱 `inbox`：按 `user_id` 分片

```
分库:   32 库
分表:   每库 16 表
总分片: 512

shard_key = hash(user_id) % 512
表名:      inbox_<shard_key>
```

## 2.3 时间维度二级分区

热表按 `created_at` 做 RANGE 分区：

```sql
CREATE TABLE im_message_db15_msg11 (
  ...
  created_at BIGINT,
  PRIMARY KEY (id, created_at)
)
PARTITION BY RANGE (created_at) (
  PARTITION p202604 VALUES LESS THAN (1714521600000),
  PARTITION p202605 VALUES LESS THAN (1717113600000),
  PARTITION p202606 VALUES LESS THAN (1719792000000),
  PARTITION p_max   VALUES LESS THAN MAXVALUE
);
```

每月新建分区，30 天前的分区可快速 DROP（归档后）。

## 2.4 分片路由层

```
应用层 → ShardingProxy → 后端 DB
       ↑
       基于 shard_key 路由
```

实现方式：
- **客户端 SDK 直连**：性能好，扩容时 SDK 要更新
- **中间件代理**（推荐）��ShardingSphere / MyCat / 自研
- **TiDB**：原生分布式，应用层无感

## 2.5 路由表

```
shard_meta 表 (全局，单点存储)
+----------+----------+----------+----------+
| shard_id | db_url   | status   | weight   |
+----------+----------+----------+----------+
| 0        | db0:3306 | active   | 100      |
| 1        | db0:3306 | active   | 100      |
| ...      |          |          |          |
| 511      | db31:3306| active   | 100      |
+----------+----------+----------+----------+
```

存储：etcd / Apollo / 自研配置中心。

---

# 3. 分片键选择

## 3.1 不同表的分片键

| 表 | 分片键 | 理由 |
|---|---|---|
| `im_message` | `conv_id` | 会话内消息聚合查询 |
| `inbox` | `user_id` | 用户离线消息拉取 |
| `mention_index` | `user_id` | "我被@的消息"查询 |
| `user_conv_cursor` | `user_id` | 用户游标查询 |
| `conversation_meta` | `conv_id` | 会话元数据 |
| `group_member` | `group_id` | 群成员查询 |
| `outbox_event` | 时间 + 自增 ID | 顺序消费 |
| `user` | `user_id` | 用户基本信息 |

## 3.2 跨分片查询的处理

### 查询某用户在所有会话的消息？
**正常不查**。如果一定要：
- 走 `inbox`（按 user_id 分片，单分片）
- 不走 `im_message`（要扫所有分片）

### 查询某会话所有 @ 我的消息？
- 走 `mention_index`（按 user_id + conv_id 分片）

### 查询某用户的活跃会话列表？
- 走 `user_conv_cursor`（按 user_id 分片）

**核心原则**：让每个查询都能命中单分片。

## 3.3 热点分片处理

### 大群（万人群）→ 单 conv_id 写入热点
- 识别后单独路由到独立分片
- 该分片配置更高规格

### 大 V → 写扩散热点
- 不写 inbox，改读扩散
- 详见消息分发文档

---

# 4. 冷热分离

## 4.1 热表 → 温表（同库）

每月底执行：
```sql
-- 切换分区，30 天前的数据进归档分区
ALTER TABLE im_message_db15_msg11 
  REORGANIZE PARTITION p_max INTO (
    PARTITION p202604 VALUES LESS THAN (...),
    PARTITION p_max   VALUES LESS THAN MAXVALUE
  );
```

应用层查询时优先查最新分区，不影响。

## 4.2 温表 → 冷表（HBase）

### HBase 表设计

```
表名: im_message_archive
RowKey: reverse(conv_id) + visible_seq

ColumnFamily:
  d: data
    server_msg_id, sender_id, msg_type, content, send_time, status
  m: meta
    mention_all, mention_count, version
```

### 为什么 reverse(conv_id)
RowKey 顺序递增会导致 RegionServer 写热点。reverse 后 conv_id 散列到不同 Region。

### 归档作业

```
每天凌晨 3:00 执行:

1. 扫描 im_message 中 created_at < now-30d 的数据
2. 按 conv_id 分批 (1000 条/批)
3. 写入 HBase
4. 校验 HBase 数据完整性
5. DROP MySQL 对应分区

并发控制: 32 个分库并行，每库 4 线程
单批耗时: 5~10s
日归档量: 500GB ~ 1TB
```

## 4.3 冷数据查询

```python
def query_history(conv_id, before_seq, limit):
    # 先查热表
    rows = mysql.query(im_message, conv_id, before_seq, limit)
    
    if len(rows) >= limit:
        return rows
    
    # 不够则补冷表
    cold_rows = hbase.scan(
        rowkey_prefix=reverse(conv_id),
        start=visible_seq_to_rowkey(before_seq),
        limit=limit - len(rows)
    )
    
    return rows + cold_rows
```

## 4.4 文件消息冷分离

文件 / 图片 / 视频：
- **元数据**留 MySQL（含 OSS URL）
- **文件本体**永久放 OSS
- 30 天后元数据归档到 HBase
- 90 天后访问频率低的文件迁移到低频存储（成本降 80%）

---

# 5. 扩容方案

## 5.1 扩容触发条件

任一指标命中：
- 单库存储 > 80% 容量
- 单库 QPS > 80% 峰值能力
- 单表行数 > 4 亿
- CPU 持续 > 70%

## 5.2 扩容方式对比

| 方式 | 适用 | 复杂度 |
|---|---|---|
| 垂直扩容 | 短期，CPU/内存瓶颈 | 低 |
| 加从库 | 读瓶颈 | 低 |
| 分片倍增（512 → 1024） | 长期，数据量瓶颈 | 高 |
| 一致性 Hash 加节点 | 灵活扩容 | 中 |
| 升级到 TiDB | 彻底解决 | 极高 |

## 5.3 推荐扩容方案：双倍分片

将 512 分片扩成 1024：

```
原 hash(conv_id) % 512 = 251
新 hash(conv_id) % 1024 = 251 或 763

规则: 
  - 251 (落原分片) 不动
  - 763 (新分片) 数据从 251 拷贝过来
  - 新写入按新规则路由
```

### 扩容流程

```
阶段 1: 准备
  - 创建新数据库实例 db_32 ~ db_63
  - 创建对应表结构
  - 启动数据同步链路

阶段 2: 双写
  - 应用层开关：双写新旧分片
  - 验证新分片数据正确性

阶段 3: 历史数据迁移
  - 后台 worker 按 conv_id 扫描
  - hash(conv_id) % 1024 落新分片的，拷贝过去
  - 校验完整性

阶段 4: 切流
  - 路由规则切换为 % 1024
  - 应用层停止双写
  - 流量观察 7 天

阶段 5: 清理
  - 旧分片中"应该在新分片"的数据删除
  - 释放空间
```

## 5.4 平滑扩容关键点

### 1）应用层路由可热更新
```go
type Router struct {
    rule atomic.Value  // *RoutingRule
}

func (r *Router) Update(newRule *RoutingRule) {
    r.rule.Store(newRule)  // 无锁更新
}
```

### 2）双写期间幂等
新旧分片都用同样的唯一键，重复写入冲突即可。

### 3）迁移期间读策略
```
迁移中: 同时查新旧分片，结果合并
迁移后: 只查新分片
```

### 4）回滚预案
- 路由规则可瞬间切回旧规则
- 双写期数据完全一致，回滚无损

## 5.5 TiDB 扩容（推荐长期方案）

TiDB 扩容简单：
```
tiup cluster scale-out im-prod scale-out.yaml
```

无需停机、无需迁移，自动 rebalance Region。  
**长期看，TiDB 方案运维成本远低于 MySQL 分片。**

---

# 6. 数据迁移

## 6.1 迁移工具选型

| 场景 | 工具 |
|---|---|
| MySQL → MySQL 增量 | Canal / Maxwell / Debezium |
| MySQL → MySQL 全量 | mysqldump / mydumper |
| MySQL → TiDB | TiDB DM (Data Migration) |
| MySQL → HBase | 自研 ETL / Flink CDC |
| 跨地域同步 | binlog 异步复制 |

## 6.2 迁移流程模板

```
1. 准备阶段
   - 评估数据量、停机窗口
   - 准备目标存储
   - 建立监控

2. 全量迁移
   - 选择空闲时段
   - 分批读取（避免锁库）
   - 并行写入目标
   - 记录迁移点位

3. 增量同步
   - 启动 binlog 同步
   - 追平实时数据

4. 验证
   - 行数对比
   - 抽样校验
   - 业务双查对比

5. 切流
   - 应用层切到新存储
   - 灰度 1% → 100%
   - 保留旧存储 7 天

6. 清理
   - 停止同步
   - 删除旧数据
```

## 6.3 大表迁移

单表 5 亿行（约 200GB）的迁移策略：

```python
# 按主键分段并行
def migrate_table(table_name, start_id, end_id, batch_size=10000, workers=8):
    ranges = split_range(start_id, end_id, workers)
    
    pool = ThreadPool(workers)
    for r in ranges:
        pool.submit(migrate_range, table_name, r.start, r.end, batch_size)
    pool.join()

def migrate_range(table, start, end, batch):
    cursor = start
    while cursor < end:
        rows = src.query(f"SELECT * FROM {table} WHERE id >= ? AND id < ? LIMIT ?",
                         cursor, end, batch)
        if not rows:
            break
        dst.batch_insert(table, rows)
        cursor = rows[-1].id + 1
        sleep(0.01)  # 限速防压垮源
```

## 6.4 在线迁移注意事项

- **限速**：迁移流量 < 主流量 30%
- **避开高��**：通常凌晨 1~5 点
- **断点续传**：记录已迁移位置
- **失败重试**：单批失败 3 次后人工介入
- **监控**：迁移速度、错误率、源/目标负载

---

# 7. 对账机制

对账目的：确保数据完整性、识别丢失/重复。

## 7.1 对账层级

| 层级 | 对账内容 | 频率 |
|---|---|---|
| 写入层 | DB ↔ Outbox | 实时 |
| 分发层 | Outbox ↔ Kafka | 5min |
| 消费层 | Kafka ↔ 各下游 DB | 1h |
| 跨地域 | 主区 ↔ 从区 | 1h |
| 冷热 | MySQL ↔ HBase | 每日 |

## 7.2 实时对账：Outbox 滞留监控

```sql
SELECT COUNT(*) FROM outbox_event 
WHERE status=0 AND created_at < UNIX_TIMESTAMP() * 1000 - 60000;
-- 超过 1 分钟未发送 → 告警
```

## 7.3 准实时对账：消费 lag

```bash
# Kafka consumer lag
kafka-consumer-groups --describe --group cg-inbox

# 自动告警: lag > 10000 持续 5 分钟
```

## 7.4 离线对账：每小时跑

### 上下游一致性
```sql
-- 上游消息数（每小时窗口）
SELECT COUNT(*) FROM im_message 
WHERE created_at BETWEEN ? AND ?;

-- 下游 inbox 写入数
SELECT SUM(count) FROM (
  SELECT COUNT(*) FROM inbox_0 WHERE ...
  UNION ALL
  ...
) ;

-- 偏差 = 上游 - 下游 / 期望接收人数
-- 偏差 > 0.01% → 告警
```

### 抽样校验
```python
def sample_check(hour):
    # 随机抽 1000 条上游消息
    msgs = db.sample("im_message", where=hour, n=1000)
    
    for msg in msgs:
        recipients = get_conv_members(msg.conv_id)
        for uid in recipients:
            # 检查每个接收人 inbox 是否有
            exists = db.exists("inbox", uid, msg.conv_id, msg.visible_seq)
            if not exists:
                report_missing(msg, uid)
```

## 7.5 跨地域对账

```
华东 → 华南 同步检查:
1. 取 5 分钟前的时间窗
2. 各自 SUM(count) GROUP BY conv_id
3. diff = 主区 - 从区
4. diff > 阈值 → 报警 + 触发补偿同步
```

## 7.6 对账失败处理

| 偏差 | 动作 |
|---|---|
| < 0.001% | 记录，不报警 |
| 0.001% ~ 0.01% | 邮件提醒 |
| 0.01% ~ 0.1% | IM 报警，人工查 |
| > 0.1% | 电话报警，启动应急 |

---

# 8. 备份与恢复

## 8.1 备份策略

| 备份类型 | 频率 | 保留 | 存储 |
|---|---|---|---|
| 全量备份 | 每周日 02:00 | 4 周 | 异地 OSS |
| 增量 binlog | 实时 | 30 天 | 异地 OSS |
| 逻辑导出 | 每月 1 号 | 1 年 | 异地 OSS |
| 跨地域副本 | 实时同步 | 永久 | 异地 DC |

## 8.2 备份执行

### MySQL
```bash
mydumper \
  --host=db15-master \
  --threads=8 \
  --compress \
  --less-locking \
  --outputdir=/backup/$(date +%Y%m%d) \
  --regex='^im_message'

# 上传到 OSS
ossutil cp /backup/... oss://im-backup/...
```

### TiDB
```bash
br backup full \
  --pd "pd:2379" \
  --storage "s3://im-backup/$(date +%Y%m%d)" \
  --ratelimit 128
```

## 8.3 恢复演练

每季度执行：
1. 选取一个分库的备份
2. 恢复到隔离环境
3. 校验数据完整性
4. 模拟应用查询
5. 记录 RTO

目标 RTO：单库 < 30 分钟。

## 8.4 灾难恢复

### 单库丢失
```
1. 从最近全量备份恢复
2. 应用 binlog 增量到故障点
3. 校验数据
4. 切流
RTO: 1~2 小时
RPO: < 1 分钟
```

### 整集群丢失
```
1. 切流到异地副本
2. 异地副本提升为主
RTO: < 10 分钟
RPO: < 30 秒
```

---

# 9. 运维操作手册

## 9.1 日常巡检

```
每日:
[ ] 各分片磁盘使用率
[ ] 主从延迟
[ ] 慢查询数量
[ ] 死锁数量
[ ] 备份成功状态
[ ] 对账偏差报告

每周:
[ ] 容量增长趋势
[ ] 索引使用情况
[ ] 表碎片率
[ ] 备份恢复演练（轮换分片）

每月:
[ ] 容量规划复盘
[ ] 成本分析
[ ] 灾备演练
```

## 9.2 紧急操作

### 单分片 CPU 爆满
```
1. 查 SHOW PROCESSLIST 找慢查询
2. KILL 异常查询
3. 排查应用是否有异常调用
4. 紧急时降级该分片读流量
```

### 单分片磁盘告急
```
1. 紧急加盘（如可热加）
2. 停止该分片归档（避免 I/O 加剧）
3. 加快冷数据归档
4. 必要时主从切换到大盘从库
```

### 主从延迟过大
```
1. 检查从库 IO/SQL 线程状态
2. 排查从库慢 SQL
3. 临时禁用从库读
4. 必要时重建从库
```

### 数据误删
```
1. 立即停止应用写入
2. 从 binlog 恢复
3. 数据回填到主库
4. 校验后恢复服务
```

## 9.3 容量规划

```
数据增长公式:
  日增 = DAU × 人均消息数 × 平均消息大小

例: 1000万 DAU × 50 条 × 512B = 250GB/天

3 个月预警:
  当前剩余 / 日增 < 90 天 → 触发扩容评估
```

## 9.4 SQL 规范

### 必须
- 所有查询带 LIMIT
- WHERE 必须命中索引
- 大表分页用 cursor 不用 OFFSET
- 历史数据查询带时间范围

### 禁止
- 跨分片 JOIN
- SELECT *
- 大事务（> 1000 行更���）
- 在线 DDL 不带 ALGORITHM=INPLACE

---

# 文档维护

- 文档负责人：DBA + 数据架构组
- 评审周期：季度
- 关联文档：DB 容量预算文档、灾备演练手册

*Version 1.0 | 最后更新：2026-05-04*