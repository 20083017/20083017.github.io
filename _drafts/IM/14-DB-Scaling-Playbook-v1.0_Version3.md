# 数据库扩容实战手册 v1.0

> 适用：MySQL / TiDB 分库分表的生产环境扩容  
> 场景：从 32 库扩到 64 库 / 单库扩容 / 跨集群迁移  
> 目标：在线扩容、零数据丢失、可回滚

---

## 目录

1. 扩容场景分类
2. 扩容前准备
3. 双写迁移完整流程
4. 数据迁移工具
5. 对账校验完整脚本
6. 切流方案
7. 回滚方案
8. 故障处理
9. 性能与限速
10. Checklist

---

# 1. 扩容场景分类

## 1.1 三种扩容场景

| 场景 | 复杂度 | 时长 | 影响 |
|---|---|---|---|
| **垂直扩容**（升级硬件） | 低 | 1~2h | 主备切换抖动 |
| **水平扩分库**（32 → 64 库） | 高 | 数天 | 全程双写 |
| **水平扩分表**（库内 16 → 32 表） | 中 | 1~2 天 | 单库内迁移 |

本文档重点是**水平扩分库**（最复杂的场景）。

## 1.2 扩容触发条件

```
任一满足:
  - 单库存储 > 70%
  - 单库 QPS 持续 > 80%
  - 单库连接数 > 80%
  - 预测 6 个月内会满
```

## 1.3 扩容方式选择

### 双倍扩容（推荐）
```
原 32 库 → 64 库
hash(key) % 64

迁移规则:
  原 db_00 → db_00 + db_32
  按 hash 高位决定
  
优点: hash 一致性好,迁移规则清晰
缺点: 必须 2 倍
```

### 一致性 hash
```
扩容时只迁移 1/N 数据
缺点: 实现复杂、运维难
```

**推荐双倍扩容**。

---

# 2. 扩容前准备

## 2.1 资源准备

```
[ ] 新硬件机器到位
[ ] 新数据库实例搭建
[ ] 主从复制配置
[ ] 备份策略一致
[ ] 监控告警接入
[ ] DNS / VIP 准备
```

## 2.2 容量评估

```
当前:
  数据量: 32 × 500GB = 16TB
  QPS: 32 × 5K = 160K

扩容后:
  数据量: 64 × 250GB = 16TB（每库减半）
  QPS: 64 × 2.5K = 160K

预留 1 年:
  数据量翻倍 → 64 × 500GB
  QPS 翻倍 → 64 × 5K = 320K
```

## 2.3 工具准备

```
[ ] 数据迁移工具（DTS / 自研）
[ ] 对账工具
[ ] 双写中间件（应用层路由开关）
[ ] 限速控制
[ ] 监控大盘
[ ] 回滚脚本
```

## 2.4 演练

**生产前必须在测试环境完整演练**：

```
1. 测试环境部署同样规模
2. 灌入 1% 生产数据
3. 完整跑一遍流程
4. 模拟故障
5. 验证回滚
```

---

# 3. 双写迁移完整流程

## 3.1 总体阶段

```
┌──────────────────┐
│ 阶段 1: 准备     │ 路由层支持双写开关
└────────┬─────────┘
         │
┌────────▼─────────┐
│ 阶段 2: 双写     │ 业务同时写新老分片
└────────┬─────────┘
         │
┌────────▼─────────┐
│ 阶段 3: 历史迁移 │ 后台迁移老数据到新分片
└────────┬─────────┘
         │
┌────────▼─────────┐
│ 阶段 4: 校验     │ 对账,修复差异
└────────┬─────────┘
         │
┌────────▼─────────┐
│ 阶段 5: 切读     │ 灰度切读到新分片
└────────┬─────────┘
         │
┌────────▼─────────┐
│ 阶段 6: 停老写   │ 关闭老分片写入
└────────┬─────────┘
         │
┌────────▼─────────┐
│ 阶段 7: 清理     │ 删除老数据
└──────────────────┘
```

## 3.2 路由层改造

### 配置版本

```yaml
# 老配置
shard_v1:
  count: 32
  hash: "hash(key) % 32"

# 新配置
shard_v2:
  count: 64
  hash: "hash(key) % 64"

# 双写开关
dual_write:
  enabled: true
  read_from: "v1"   # 切换值: v1 / v2
  write_to:  ["v1", "v2"]
```

### 路由代码

```python
class ShardRouter:
    def __init__(self, config):
        self.v1 = ShardConfig(count=32)
        self.v2 = ShardConfig(count=64)
        self.dual_write = config.dual_write
    
    def route_write(self, table, key):
        targets = []
        if "v1" in self.dual_write.write_to:
            targets.append(self.v1.route(table, key))
        if "v2" in self.dual_write.write_to:
            targets.append(self.v2.route(table, key))
        return targets
    
    def route_read(self, table, key):
        if self.dual_write.read_from == "v2":
            return self.v2.route(table, key)
        return self.v1.route(table, key)
```

### 双写实现

```python
def insert_message(msg):
    targets = router.route_write("im_message", msg.conv_id)
    
    primary = targets[0]
    secondary = targets[1] if len(targets) > 1 else None
    
    # 主写
    primary_db.insert(msg)
    
    # 副写（异步，失败不阻塞主流程）
    if secondary:
        try:
            secondary_db.insert(msg)
        except Exception as e:
            log.warn(f"secondary write failed: {e}")
            # 写入修复队列
            repair_queue.send(msg)
```

## 3.3 阶段 1：准备（1 周）

```
[ ] 部署新分片基础设施
[ ] 路由层支持 v1 / v2 双配置
[ ] 双写开关 OFF（默认）
[ ] 灰度部署带新代码的应用
[ ] 监控大盘准备好
```

## 3.4 阶段 2：开启双写（1~3 天观察）

```
1. 灰度开启双写（1% → 10% → 100%）
2. 观察:
   - 业务延迟是否上升
   - 新分片写入是否成功
   - 数据是否一致

3. 持续 1~3 天确认稳定
```

### 监控点

```
- 主��延迟
- 副写延迟
- 副写失败率
- 修复队列堆积
```

## 3.5 阶段 3：历史数据迁移（数小时~数天）

见**第 4 节**。

## 3.6 阶段 4：对账校验

见**第 5 节**。

## 3.7 阶段 5：切读

```
配置变更:
  read_from: v1 → v2

灰度:
  1% (5 分钟) → 10% (10 分钟) → 50% (30 分钟) → 100%

监控:
  - 业务错误率
  - 查询延迟
  - 业务异常告警
```

### 切读代码

```python
def route_read(table, key, request_id):
    # 灰度判断
    bucket = hash(request_id) % 100
    if bucket < CURRENT_GRAY_PERCENT:
        return v2.route(table, key)
    return v1.route(table, key)
```

## 3.8 阶段 6：停止老写入

```
配置变更:
  write_to: ["v1", "v2"] → ["v2"]

观察 7~30 天
确认 v1 不再被使用
```

## 3.9 阶段 7：清理

```
30 天后:
  - 备份 v1 数据到归档
  - 删除 v1 分片
  - 释放硬件
```

---

# 4. 数据迁移工具

## 4.1 工具选型

### 选项 A：DTS（云厂商工具）
```
阿里云 DTS / AWS DMS
- 优点: 开箱即用、增量同步、断点续传
- 缺点: 成本高、定制性差
```

### 选项 B：自研迁移工具
```
- 优点: 灵活、可控
- 缺点: 开发成本
```

### 选项 C：开源工具
```
gh-ost / pt-online-schema-change (单库)
shardingsphere-scaling (分库)
```

## 4.2 自研迁移工具核心实现

### 整体设计

```
┌──────────────┐
│ 迁移控制器    │ ← 任务调度、进度管理、限速
└──────┬───────┘
       │
   ┌───┴────┐
   ▼        ▼
┌──────┐  ┌──────┐
│Worker│  │Worker│  ... 多 worker 并行
└───┬──┘  └───┬──┘
    ▼         ▼
   v1        v2
```

### 任务表

```sql
CREATE TABLE migration_task (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  table_name  VARCHAR(64),
  src_shard   VARCHAR(64),
  dst_shard   VARCHAR(64),
  start_pk    BIGINT,
  end_pk      BIGINT,
  current_pk  BIGINT,
  status      VARCHAR(16),    -- pending/running/done/failed
  rows_total  BIGINT,
  rows_done   BIGINT,
  speed       INT,            -- rows/s
  started_at  BIGINT,
  finished_at BIGINT,
  error       TEXT
);
```

### Worker 实现

```python
class MigrationWorker:
    def __init__(self, task_id, src_db, dst_router, batch_size=1000):
        self.task = self.load_task(task_id)
        self.src = src_db
        self.router = dst_router
        self.batch_size = batch_size
        self.rate_limiter = RateLimiter(rows_per_sec=10000)
    
    def run(self):
        try:
            self.task.status = "running"
            self.task.save()
            
            current = self.task.current_pk or self.task.start_pk
            
            while current < self.task.end_pk:
                rows = self.fetch_batch(current, self.batch_size)
                if not rows:
                    break
                
                self.write_batch(rows)
                
                current = rows[-1].id
                self.task.current_pk = current
                self.task.rows_done += len(rows)
                self.task.save()
                
                # 限速
                self.rate_limiter.wait(len(rows))
                
                # 检查停止信号
                if self.should_stop():
                    self.task.status = "paused"
                    return
            
            self.task.status = "done"
            self.task.finished_at = now()
            self.task.save()
            
        except Exception as e:
            self.task.status = "failed"
            self.task.error = str(e)
            self.task.save()
            raise
    
    def fetch_batch(self, start_pk, limit):
        return self.src.query(
            f"SELECT * FROM {self.task.table_name} "
            f"WHERE id > %s AND id <= %s "
            f"ORDER BY id LIMIT %s",
            start_pk, self.task.end_pk, limit
        )
    
    def write_batch(self, rows):
        # 按 dst shard 分组
        grouped = defaultdict(list)
        for row in rows:
            shard_key = self.get_shard_key(row)
            dst = self.router.route(self.task.table_name, shard_key)
            grouped[dst].append(row)
        
        # 批量插入
        for dst, group in grouped.items():
            dst.batch_insert(self.task.table_name, group)
```

### 批量插入（幂等）

```python
def batch_insert_idempotent(table, rows):
    if not rows:
        return
    
    columns = list(rows[0].keys())
    values_sql = ",".join(["(" + ",".join(["%s"] * len(columns)) + ")"] * len(rows))
    
    sql = f"""
        INSERT INTO {table} ({','.join(columns)})
        VALUES {values_sql}
        ON DUPLICATE KEY UPDATE id=id   -- 幂等
    """
    
    args = []
    for row in rows:
        args.extend([row[c] for c in columns])
    
    db.execute(sql, args)
```

## 4.3 任务切分

```python
def split_tasks(table_name, src_shards, dst_router, slice_size=1000000):
    tasks = []
    
    for src in src_shards:
        # 拿到该 shard 的主键范围
        max_id = src.query(f"SELECT MAX(id) FROM {table_name}").scalar()
        min_id = src.query(f"SELECT MIN(id) FROM {table_name}").scalar()
        
        # 按 slice_size 切分
        current = min_id
        while current < max_id:
            end = min(current + slice_size, max_id)
            tasks.append(MigrationTask(
                table_name=table_name,
                src_shard=src.name,
                start_pk=current,
                end_pk=end,
                rows_total=slice_size
            ))
            current = end
    
    return tasks
```

## 4.4 限速

```python
class RateLimiter:
    def __init__(self, rows_per_sec):
        self.rate = rows_per_sec
        self.tokens = rows_per_sec
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def wait(self, n):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_refill = now
            
            if self.tokens >= n:
                self.tokens -= n
                return
            
            wait_time = (n - self.tokens) / self.rate
        
        time.sleep(wait_time)
        self.wait(n)
```

## 4.5 性能基线

```
单 Worker:    1~5 万 rows/s
10 Worker:    50 万 rows/s
30 Worker:    100 万 rows/s（受网络/DB 限制）

100 亿行迁移:
  100 亿 / 100 万/s = 10000 秒 ≈ 3 小时
  
实际 6~12 小时（含限速）
```

## 4.6 监控

```
- 任务进度（done/total）
- 迁移速度（rows/s）
- 错误率
- 源 / 目标 DB 负载
- 网络带宽
```

---

# 5. 对账校验完整脚本

## 5.1 对账层级

```
1. 行数对账（最快）
2. 边界对账（最近数据）
3. 抽样对账
4. 全量哈希对账（最准）
```

## 5.2 行数对账脚本

```python
def count_compare(table, time_range):
    """按小时桶对比行数"""
    sql = f"""
        SELECT 
          UNIX_TIMESTAMP(DATE_FORMAT(FROM_UNIXTIME(created_at/1000), '%Y-%m-%d %H:00:00')) * 1000 as bucket,
          COUNT(*) as cnt
        FROM {table}
        WHERE created_at BETWEEN {time_range.start} AND {time_range.end}
        GROUP BY bucket
        ORDER BY bucket
    """
    
    src_buckets = {}
    for shard in v1_shards:
        for row in shard.query(sql):
            src_buckets[row.bucket] = src_buckets.get(row.bucket, 0) + row.cnt
    
    dst_buckets = {}
    for shard in v2_shards:
        for row in shard.query(sql):
            dst_buckets[row.bucket] = dst_buckets.get(row.bucket, 0) + row.cnt
    
    diffs = []
    for bucket in set(src_buckets.keys()) | set(dst_buckets.keys()):
        src = src_buckets.get(bucket, 0)
        dst = dst_buckets.get(bucket, 0)
        if src != dst:
            diffs.append({
                "bucket": bucket,
                "src_count": src,
                "dst_count": dst,
                "diff": dst - src
            })
    
    return diffs
```

## 5.3 抽样对账

```python
def sample_compare(table, sample_size=10000):
    """随机抽样对比每行"""
    diffs = []
    
    for shard in v1_shards:
        sample = shard.query(f"""
            SELECT * FROM {table} 
            WHERE id IN (
              SELECT id FROM {table} 
              ORDER BY RAND() LIMIT {sample_size // len(v1_shards)}
            )
        """)
        
        for row in sample:
            shard_key = get_shard_key(row, table)
            dst_shard = v2_router.route(table, shard_key)
            
            dst_row = dst_shard.query(
                f"SELECT * FROM {table} WHERE id = %s", row.id
            ).first()
            
            if not dst_row:
                diffs.append({"id": row.id, "issue": "missing_in_dst"})
            elif not row_equal(row, dst_row):
                diffs.append({
                    "id": row.id, 
                    "issue": "content_diff",
                    "src": row,
                    "dst": dst_row
                })
    
    return diffs

def row_equal(a, b, ignore_fields=("updated_at",)):
    for k in a.keys():
        if k in ignore_fields:
            continue
        if a[k] != b[k]:
            return False
    return True
```

## 5.4 边界对账（增量）

```python
def boundary_compare(table, lookback=3600):
    """对比最近 N 秒数据"""
    end_time = int(time.time() * 1000)
    start_time = end_time - lookback * 1000
    
    src_rows = []
    for shard in v1_shards:
        rows = shard.query(f"""
            SELECT id, server_msg_id, conv_id, created_at, status
            FROM {table}
            WHERE created_at BETWEEN %s AND %s
        """, start_time, end_time)
        src_rows.extend(rows)
    
    dst_rows = []
    for shard in v2_shards:
        rows = shard.query(f"""
            SELECT id, server_msg_id, conv_id, created_at, status
            FROM {table}
            WHERE created_at BETWEEN %s AND %s
        """, start_time, end_time)
        dst_rows.extend(rows)
    
    # 按 server_msg_id 去重对比
    src_set = {r.server_msg_id: r for r in src_rows}
    dst_set = {r.server_msg_id: r for r in dst_rows}
    
    only_src = set(src_set.keys()) - set(dst_set.keys())
    only_dst = set(dst_set.keys()) - set(src_set.keys())
    
    return {
        "missing_in_dst": list(only_src),
        "extra_in_dst": list(only_dst),
        "src_count": len(src_set),
        "dst_count": len(dst_set)
    }
```

## 5.5 全量哈希对账

```python
def hash_compare(table, partition_field="conv_id"):
    """每个分片求哈希后对比"""
    
    def shard_hash(shard, where_clause):
        return shard.query(f"""
            SELECT 
              MD5(GROUP_CONCAT(
                CONCAT(id, server_msg_id, status) 
                ORDER BY id
              )) as hash,
              COUNT(*) as cnt
            FROM {table}
            WHERE {where_clause}
        """).first()
    
    diffs = []
    
    # 按 partition_field 分桶（如每 1000 个 conv_id 一组）
    for bucket_start in range(0, MAX_KEY, 1000):
        bucket_end = bucket_start + 1000
        where = f"{partition_field} BETWEEN {bucket_start} AND {bucket_end}"
        
        src_data = aggregate_shards(v1_shards, where)
        dst_data = aggregate_shards(v2_shards, where)
        
        if src_data.hash != dst_data.hash or src_data.cnt != dst_data.cnt:
            diffs.append({
                "bucket": (bucket_start, bucket_end),
                "src": src_data,
                "dst": dst_data
            })
    
    return diffs
```

## 5.6 差异修复

```python
def repair_diff(diff):
    """修复差异"""
    issue = diff["issue"]
    
    if issue == "missing_in_dst":
        # 老库有,新库无 → 补写
        src_row = fetch_from_src(diff["id"])
        shard_key = get_shard_key(src_row)
        dst = v2_router.route(table, shard_key)
        dst.insert_idempotent(src_row)
        
    elif issue == "content_diff":
        # 内容不一致 → 以老为准（更可靠）
        src_row = diff["src"]
        shard_key = get_shard_key(src_row)
        dst = v2_router.route(table, shard_key)
        dst.update(src_row.id, src_row)
        
    elif issue == "extra_in_dst":
        # 新库多 → 排查（可能是双写时机问题）
        log.warn(f"extra row in dst: {diff}")
        # 通常不删除,可能是新数据
```

## 5.7 持续对账（binlog）

```python
def continuous_verify():
    """订阅 binlog 持续对账"""
    consumer = BinlogConsumer(v1_shards)
    
    for event in consumer.stream():
        if event.type == "INSERT":
            # 等 100ms 让双写到达
            time.sleep(0.1)
            
            shard_key = get_shard_key_from_event(event)
            dst = v2_router.route(event.table, shard_key)
            
            dst_row = dst.query(
                f"SELECT * FROM {event.table} WHERE id = %s",
                event.row.id
            ).first()
            
            if not dst_row:
                metrics.diff_missing.inc()
                repair_queue.send(event.row)
            elif not row_equal(event.row, dst_row):
                metrics.diff_content.inc()
                repair_queue.send(event.row)
            else:
                metrics.consistent.inc()
```

---

# 6. 切流方案

## 6.1 切读灰度

```
小时 1: 1%
小时 2: 5%
小时 3: 20%
小时 4: 50%
小时 5: 100%

每个阶段必须满足:
  - 业务错误率不上升
  - 延迟不上升 > 10%
  - 业务核心指标稳定
```

## 6.2 灰度规则

```python
def should_use_v2(request):
    if not features.dual_read_enabled:
        return False
    
    # 按用户 ID 灰度（一致性）
    bucket = hash(request.user_id) % 100
    return bucket < features.v2_gray_percent
```

## 6.3 监控

```
切流监控:
  - 错误率（v1 vs v2）
  - 延迟分布（v1 vs v2）
  - 业务异常计数
```

## 6.4 自动熔断

```python
def auto_circuit_breaker():
    """灰度期间自动监控"""
    while True:
        v2_error_rate = metrics.error_rate("v2", "5min")
        baseline = metrics.error_rate("v1", "5min")
        
        if v2_error_rate > baseline * 2:
            log.error("v2 error rate too high, rollback")
            features.v2_gray_percent = 0
            send_alarm("auto_rollback_triggered")
        
        time.sleep(30)
```

---

# 7. 回滚方案

## 7.1 各阶段回滚

| 阶段 | 回滚方式 | 风险 |
|---|---|---|
| 双写 | 关闭副写开关 | 低 |
| 历史迁移中 | 暂停任务 | 低 |
| 切读灰度 | 切读回 v1 | 低 |
| 切读完成 | 切读回 v1（v1 仍在双写） | 低 |
| 停老写 | 重新打开 v1 写 + 反向同步增量 | 中 |
| 清理后 | 几乎无法回滚 | 高 |

## 7.2 切读回滚

```python
def rollback_read():
    """秒级回滚切读"""
    config_center.set("dual_write.read_from", "v1")
    config_center.set("v2_gray_percent", 0)
```

## 7.3 紧急回滚（双写阶段）

```bash
# 1. 关闭副写
curl -X POST configcenter/dual_write \
  -d '{"write_to": ["v1"]}'

# 2. 关闭新读
curl -X POST configcenter/dual_read \
  -d '{"read_from": "v1", "v2_gray_percent": 0}'

# 3. 暂停迁移任务
curl -X POST migration/pause

# 4. 通知相关方
```

## 7.4 数据脏污修复

```
回滚后,v2 可能残留部分数据
处置:
  - 短期: 不影响（v1 仍是权威）
  - 长期: 清空 v2 重新开始,或下次扩容继续用
```

---

# 8. 故障处理

## 8.1 副写失败

```
症状: secondary write 失败率上升

排查:
  - 新分片连接数
  - 新分片磁盘空间
  - 新分片 QPS 上限
  - 网络

处置:
  - 写入修复队列
  - 后台异步重试
  - 严重时关闭副写,等修复
```

## 8.2 迁移阻塞

```
症状: 任务长期卡住

排查:
  - 锁等待
  - 主键空洞太大（COUNT 慢）
  - DB 负载高

处置:
  - 拆分任务（小区间）
  - 降低速度
  - 业务低峰期跑
```

## 8.3 对账差异大

```
症状: 抽样发现 1% 以上差异

排查:
  - 双写时机（业务事务边界）
  - 迁移工具 bug
  - 时区问题

处置:
  - 先暂停切读
  - 修复源头问题
  - 重新对账 + 修复差异
```

## 8.4 切读后业务异常

```
症状: 切读到 v2 后查询变慢/出错

排查:
  - v2 索引缺失？
  - v2 数据不全？
  - SQL 兼容性？

处置:
  - 立即回滚（秒级）
  - 修复后再切
```

---

# 9. 性能与限速

## 9.1 迁移速度控制

```yaml
migration:
  rate_limit:
    business_hours:    5000 rows/s   # 工作时间慢
    night:             50000 rows/s  # 夜间快
  
  worker_count:        20
  batch_size:          1000
  
  pause_on:
    src_cpu:           > 80%
    dst_cpu:           > 80%
    src_repl_lag:      > 30s
    dst_repl_lag:      > 30s
```

## 9.2 业务影响评估

```
双写延迟增加:
  正常: < 10ms 增加
  异常: > 50ms 增加 → 调查
  
副写失败:
  容忍: < 0.1%
  超出: 关闭副写
```

## 9.3 资源监控

```
- src DB CPU/IO/连接
- dst DB CPU/IO/连接  
- 主从延迟
- 应用层延迟
```

---

# 10. Checklist

## 10.1 预发布

```
[ ] 容量评估完成
[ ] 资源就位
[ ] 双写代码上线（开关关闭）
[ ] 迁移工具测试通过
[ ] 对账工具测试通过
[ ] 测试环境完整演练
[ ] 应急预案准备
[ ] 通知相关方
[ ] 业务低峰窗口确认
```

## 10.2 双写阶段

```
[ ] 灰度开启双写（1% → 100%）
[ ] 观察 24h 稳定
[ ] 副写失败率 < 0.1%
[ ] 业务延迟未恶化
[ ] 修复队列清零
```

## 10.3 迁移阶段

```
[ ] 任务拆分完成
[ ] Worker 启动
[ ] 速度受控
[ ] 进度大盘可见
[ ] 异常告警就绪
```

## 10.4 对账阶段

```
[ ] 行数对账通过
[ ] 抽样对账通过（差异 < 0.01%）
[ ] 边界对账通过
[ ] 持续对账启动
[ ] 修复队列清零
```

## 10.5 切读阶段

```
[ ] 灰度切读 1%（观察 30 分钟）
[ ] 灰度切读 10%
[ ] 灰度切读 50%
[ ] 灰度切读 100%
[ ] 持续观察 7 天
```

## 10.6 收尾

```
[ ] 关闭老库写入
[ ] 观察 30 天
[ ] 备份老库
[ ] 删除老库
[ ] 释放硬件
[ ] 总结复盘
```

---

# 附录：迁移控制脚本骨架

```python
#!/usr/bin/env python3
"""数据库扩容迁移控制器"""

import argparse
import sys

class MigrationController:
    def __init__(self, config_path):
        self.config = load_config(config_path)
        self.tables = self.config.tables
    
    def cmd_prepare(self):
        """准备阶段"""
        for table in self.tables:
            tasks = split_tasks(
                table.name,
                self.config.src_shards,
                self.config.dst_router,
                slice_size=table.slice_size
            )
            insert_tasks(tasks)
            print(f"created {len(tasks)} tasks for {table.name}")
    
    def cmd_start(self, table=None):
        """启动迁移"""
        scheduler = TaskScheduler(
            workers=self.config.worker_count,
            rate_limit=self.config.rate_limit
        )
        scheduler.run(table_filter=table)
    
    def cmd_pause(self):
        """暂停"""
        set_global_flag("migration_paused", True)
    
    def cmd_resume(self):
        """恢复"""
        set_global_flag("migration_paused", False)
    
    def cmd_status(self):
        """查进度"""
        for table in self.tables:
            stats = get_table_progress(table.name)
            print(f"{table.name}: {stats.done}/{stats.total} ({stats.percent:.1f}%)")
    
    def cmd_verify(self, table, mode="sample"):
        """对账"""
        if mode == "count":
            diffs = count_compare(table)
        elif mode == "sample":
            diffs = sample_compare(table)
        elif mode == "boundary":
            diffs = boundary_compare(table)
        elif mode == "full":
            diffs = hash_compare(table)
        
        if diffs:
            print(f"{len(diffs)} differences found")
            save_diffs(diffs)
        else:
            print("all consistent")
    
    def cmd_repair(self, diff_file):
        """修复差异"""
        diffs = load_diffs(diff_file)
        for diff in diffs:
            repair_diff(diff)
    
    def cmd_switch_read(self, percent):
        """切读灰度"""
        config_center.set("v2_gray_percent", percent)
        print(f"switched read to v2: {percent}%")
    
    def cmd_rollback(self):
        """紧急回滚"""
        config_center.set("v2_gray_percent", 0)
        config_center.set("dual_write.write_to", ["v1"])
        print("rolled back to v1")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=[
        "prepare", "start", "pause", "resume", "status",
        "verify", "repair", "switch-read", "rollback"
    ])
    parser.add_argument("--config", default="migration.yml")
    parser.add_argument("--table")
    parser.add_argument("--percent", type=int)
    parser.add_argument("--mode", default="sample")
    
    args = parser.parse_args()
    ctrl = MigrationController(args.config)
    
    cmd_method = getattr(ctrl, f"cmd_{args.command.replace('-', '_')}")
    cmd_method(**{k: v for k, v in vars(args).items() if v is not None and k != "command"})
```

---

**文档结束** | Version 1.0