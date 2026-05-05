# 消息存储分库分表方案 v1.0

> 适用：消息主表 / 提及索引 / 收件箱 / 游标 等核心表  
> 目标：单表 5 亿行内、查询 P99 < 50ms、平滑扩容

---

## 目录

1. 分片策略
2. 分片键选型
3. 路由层设计
4. 扩容方案
5. 数据迁移流程
6. 对账机制
7. 冷热分离
8. 跨分片查询
9. 备份与恢复

---

# 1. 分片策略

## 1.1 总体方案

| 表 | 分片键 | 分库 | 分表 | 总分片 |
|---|---|---|---|---|
| `im_message` | `conv_id` | 32 | 16 | 512 |
| `mention_index` | `user_id` | 32 | 16 | 512 |
| `user_conv_cursor` | `user_id` | 32 | 16 | 512 |
| `inbox` | `user_id` | 32 | 16 | 512 |
| `group_member` | `group_id` | 16 | 16 | 256 |
| `conversation_meta` | `conv_id` | 16 | 8 | 128 |
| `outbox_event` | `id` (range) | 4 | - | 4 |

## 1.2 分片函数

```python
def shard_route(table_name, shard_key):
    if table_name == "im_message":
        db_idx   = hash(shard_key) % 32
        tbl_idx  = (hash(shard_key) >> 8) % 16
        return f"db_msg_{db_idx:02d}.im_message_{tbl_idx:02d}"
    
    if table_name == "mention_index":
        db_idx   = hash(shard_key) % 32
        tbl_idx  = (hash(shard_key) >> 8) % 16
        return f"db_mention_{db_idx:02d}.mention_index_{tbl_idx:02d}"
    
    # ...
```

注意：**db_idx 与 tbl_idx 用 hash 的不同部分**，避免 db 内分布不均。

## 1.3 hash 函数选择

```
推荐: CRC32 / MurmurHash3
不推荐: hash() (Python 内置不稳定)、MD5 (慢)

要求:
  - 均匀分布
  - 跨语言一致（Java/Go/Python 同结果）
  - 速度快
```

---

# 2. 分片键选型

## 2.1 选型原则

```
1. 主查询路径必须命中分片键 (避免跨分片)
2. 写入分布均匀 (避免热点)
3. 同一业务实体的数据落同一分片 (便于事务/join)
4. 长期稳定 (不会频繁变更)
```

## 2.2 各表分片键决策

### `im_message` → `conv_id`
- ✅ 主查询：按会话拉历史 / 按 seq 范围
- ✅ 同会话所有消息一起，便于按 seq 查询
- ✅ 唯一键 `(conv_id, global_seq)` 仅在分片内验证
- ⚠️ 单会话热点（万人群）→ 用大群独立 topic 缓解

**不选 user_id**：群消息会写一份，但用户查群历史要跨分片
**不选 server_msg_id**：跨系统引用方便，但会话内查询要扫全表

### `mention_index` → `user_id`
- ✅ 主查询："我被@的消息" `WHERE user_id=?`
- ✅ 用户级查询永远落单分片
- ⚠️ 一条消息@N人 → 写N个不同分片（可接受，N 通常 < 10）

### `user_conv_cursor` → `user_id`
- ✅ 用户上线拉所有会话游标
- ✅ 单用户分片局部性好

### `inbox` → `user_id` (recipient)
- ✅ 用户上线拉收件箱
- ⚠️ 写入时一条群消息要给 N 个用户写 inbox（多分片）

### `group_member` → `group_id`
- ✅ 群消息发送时拉成员列表
- ⚠️ "用户加入哪些群"是次要查询，用辅助表

## 2.3 复合分片键

某些表分片键不够稳定，用组合：

```
user_session 表:
  分片键 = hash(user_id, app_id) 

防止单用户跨 app 数据失衡
```

---

# 3. 路由层设计

## 3.1 应用层路由

推荐：**应用代码自己计算分片**，不依赖中间件代理。

```java
public class ShardRouter {
    private final int dbCount;
    private final int tblCount;
    
    public Shard route(String table, Object shardKey) {
        long hash = hashFunction(shardKey);
        int dbIdx = (int)(hash % dbCount);
        int tblIdx = (int)((hash >>> 8) % tblCount);
        return new Shard(table, dbIdx, tblIdx);
    }
}

// 使用
Shard s = router.route("im_message", convId);
String sql = "INSERT INTO " + s.fullTable() + " (...) VALUES (...)";
db.connect(s.dbName()).execute(sql);
```

## 3.2 中间件代理（备选）

ShardingSphere / Vitess / TDDL：
- 优点：业务无感
- 缺点：性能损耗、复杂查询易踩坑、运维成本高

**推荐应用层路由**，简单直接。

## 3.3 路由元数据

```yaml
shard_config:
  im_message:
    db_count: 32
    tbl_count: 16
    db_pattern: "db_msg_%02d"
    tbl_pattern: "im_message_%02d"
    nodes:
      db_msg_00: 
        master: 10.0.1.10:3306
        slaves: 
          - 10.0.1.11:3306
          - 10.0.1.12:3306
      # ...
```

存放在配置中心（etcd），变更时 Watch 更新。

## 3.4 连接池

```
单业务节点连接池 = N (业务实例数) × M (每节点连接数)
建议: M = 10 ~ 20

64 业务节点 × 32 DB × 10 连接 = 20480 连接
单 DB 接收连接: 64 × 10 = 640 (可控)
```

---

# 4. 扩容方案

## 4.1 扩容时机

```
触发条件 (任一):
  - 单库存储 > 70% 容量
  - 单库 QPS > 80% 容量
  - 预测 6 个月内会满
```

## 4.2 扩容方式

### 方式 A：双倍扩容（推荐）

```
原: 32 库 × 16 表 = 512 分片
新: 64 库 × 16 表 = 1024 分片

迁移规则:
  原 db_msg_00 → 拆分为 db_msg_00 + db_msg_32
  按 hash 高位决定数据归属
```

**优点**：迁移规则简单，hash 一致性好

### 方式 B：增加分表数

```
原: 32 库 × 16 表 = 512
新: 32 库 × 32 表 = 1024

只在库内增加表，不跨库迁移
```

**优点**：迁移代价小（库内 INSERT...SELECT）  
**缺点**：库容量瓶颈未解

### 方式 C：一致性哈希

```
路由用 jump consistent hash
扩容时只迁移 1/N 数据
```

**优点**：迁移最少  
**缺点**：分片号不连续，运维复杂

**推荐方式 A**，运维清晰。

## 4.3 扩容前置条件

```
[ ] 新硬件资源就绪
[ ] 测试环境演练通过
[ ] 回滚预案准备
[ ] 业务低峰期进行
[ ] 通知相关方
```

---

# 5. 数据迁移流程

## 5.1 双写迁移（推荐）

```
阶段 1: 准备
  - 部署新分片
  - 路由层支持双写

阶段 2: 双写
  - 业务同时写老分片 + 新分片
  - 新��据进入两边
  - 持续 N 天确认稳定

阶段 3: 历史数据迁移
  - 启动迁移任务，按时间段批量复制
  - 用主键范围分页（避免锁表）
  - 速率控制（不影响生产）

阶段 4: 数据校验
  - 对账（见第 6 节）
  - 修复差异

阶段 5: 切读
  - 灰度切读（1% → 10% → 100%）
  - 老分片仍双写

阶段 6: 停老
  - 停老分片写入
  - 保留 30 天
  - 删除老数据
```

## 5.2 迁移工具

```python
def migrate_table(src_shard, dst_router, batch_size=1000):
    last_id = 0
    while True:
        rows = src_shard.query(
            "SELECT * FROM im_message WHERE id > %s ORDER BY id LIMIT %s",
            last_id, batch_size
        )
        if not rows:
            break
        
        for row in rows:
            dst_shard = dst_router.route("im_message", row.conv_id)
            dst_shard.upsert(row)
        
        last_id = rows[-1].id
        
        # 限速
        time.sleep(0.01)  # 100 batch/s = 100k rows/s
        
        # 进度
        progress.report(last_id)
```

## 5.3 迁移性能

```
单线程: ~10K rows/s
多线程: 按分片并行，N × 10K
全量迁移 100 亿行: 100亿 / 100K/s = 100,000 秒 ≈ 28 小时
```

实际通过分片并行可压缩到 6~12 小时。

## 5.4 数据校验

```python
def verify_shard(src, dst, sample_rate=0.01):
    """抽样校验"""
    total = src.query("SELECT COUNT(*) FROM ...")
    sample_size = int(total * sample_rate)
    
    samples = src.query(
        "SELECT * FROM ... ORDER BY RAND() LIMIT %s",
        sample_size
    )
    
    diffs = []
    for row in samples:
        dst_row = dst.query("SELECT * FROM ... WHERE id = %s", row.id)
        if not row_equal(row, dst_row):
            diffs.append(row.id)
    
    return diffs
```

---

# 6. 对账机制

## 6.1 对账类型

### 实时对账
```
双写后: 比较两边的 server_msg_id 集合
差异 → 自动修复 + 告警
```

### 定时对账
```
每小时 / 每天:
  1. 抽样校验
  2. 边界数据校验（最近 1 小时）
  3. 关键 ID 范围校验

每周:
  全量哈希校验（按分片）
```

## 6.2 对账实现

```sql
-- 老分片
SELECT 
  DATE_FORMAT(created_at, '%Y-%m-%d %H') as hour_bucket,
  COUNT(*) as cnt,
  SUM(server_msg_id) as checksum   -- 简单校验和
FROM im_message_old
WHERE conv_id BETWEEN 0 AND 1000
GROUP BY hour_bucket;

-- 新分片
SELECT 
  DATE_FORMAT(created_at, '%Y-%m-%d %H') as hour_bucket,
  COUNT(*) as cnt,
  SUM(server_msg_id) as checksum
FROM im_message_new
WHERE conv_id BETWEEN 0 AND 1000
GROUP BY hour_bucket;

-- 对比
```

## 6.3 差异处理

```
策略:
  1. 老分片有，新分片无 → 补写新分片
  2. 老分片无，新分片有 → 调查原因（双写时机）
  3. 两边都有但内容不同 → 以老为准（更可靠）
```

## 6.4 在线对账（持续）

```
binlog 订阅:
  老分片 binlog → 对账服务
  对账服务 → 查新分片 → 比对
  差异 → 告警/修复
```

---

# 7. 冷热分离

## 7.1 分级策略

| 时间 | 存储 | 查询模式 |
|---|---|---|
| 0~7 天 | MySQL 热表 | 实时查询 |
| 7~30 天 | MySQL 温表 | 偶尔查询 |
| 30~365 天 | MySQL 冷表 / TiKV | 历史回溯 |
| > 1 年 | HBase / OSS | 极少查询 |

## 7.2 冷热分离实现

### 方式 A：分区表
```sql
CREATE TABLE im_message (
  ...
) PARTITION BY RANGE (TO_DAYS(created_at)) (
  PARTITION p_recent VALUES LESS THAN (TO_DAYS('2026-05-01')),
  PARTITION p_old    VALUES LESS THAN (TO_DAYS('2026-04-01')),
  PARTITION p_archive VALUES LESS THAN MAXVALUE
);
```

### 方式 B：独立表 + 归档任务
```
im_message_hot       (近 30 天)
im_message_archive   (> 30 天)

定时任务每天凌晨:
  INSERT INTO archive SELECT FROM hot WHERE created_at < NOW() - 30 DAY
  DELETE FROM hot WHERE created_at < NOW() - 30 DAY
```

### 方式 C：冷数据导出 HBase
```
每周:
  按 conv_id 把 1 年前数据导出到 HBase
  RowKey: reverse(conv_id) + global_seq
  MySQL 删除
```

## 7.3 查询路由

```python
def query_messages(conv_id, since_seq, limit):
    # 优先查热表
    rows = hot_table.query(...)
    
    if len(rows) < limit:
        # 不够，查冷表
        cold_rows = cold_table.query(...)
        rows.extend(cold_rows)
    
    if len(rows) < limit and need_archive:
        # 仍不够，查归档
        archive_rows = hbase.query(...)
        rows.extend(archive_rows)
    
    return rows
```

---

# 8. 跨分片查询

## 8.1 避免跨分片

设计时让 95% 查询命中分片键。

## 8.2 必要的跨分片场景

### 场景 1：用户查所有会话
```
SELECT DISTINCT conv_id FROM user_conv_cursor 
WHERE user_id = ?

→ 命中 user_id 分片，单库查询
```

### 场景 2：管理后台查询
```
SELECT * FROM im_message WHERE created_at > ?
→ 跨所有分片

实现: scatter-gather
  - 并行查每个分片
  - 应用层合并、排序、分页
```

### 场景 3：全文搜索
```
不走 MySQL，走 ES
ES 索引按时间分片
```

## 8.3 scatter-gather 实现

```python
def query_all_shards(table, condition, limit):
    futures = []
    for shard in all_shards(table):
        futures.append(
            executor.submit(shard.query, condition, limit)
        )
    
    results = []
    for f in futures:
        results.extend(f.result())
    
    # 全局排序（按业务字段）
    results.sort(key=lambda x: x.created_at, reverse=True)
    
    return results[:limit]
```

**注意**：跨分片分页有性能陷阱，深分页时每个分片都要返回大量数据。  
解决：用游标分页（按 created_at + id）。

---

# 9. 备份与恢复

## 9.1 备份策略

```
全量: 每周 1 次（周日凌晨）
增量: 每 5 分钟 binlog 同步

存储:
  本地 SSD: 7 天
  对象存储: 90 天
  异地: 灾备中心
```

## 9.2 备份方式

```
mysqldump (小库):
  mysqldump --single-transaction --master-data=2 ...

xtrabackup (大库):
  innobackupex --slave-info /backup/

物理备份 + binlog 增量:
  RPO = 5 分钟
  RTO = 30 分钟
```

## 9.3 恢复流程

```
1. 选择恢复点
2. 恢复全量备份到新实例
3. apply binlog 到目标点
4. 数据校验
5. 切换业务
```

## 9.4 误删除恢复

```
binlog 闪回:
  - 解析 binlog 找到 DELETE 事件
  - 反向生成 INSERT
  - 在原库执行

时间窗口: binlog 保留期 (7 天)
```

---

**文档结束** | Version 1.0