# 数据库扩容实战手册 v1.0

> 适用：MySQL/TiDB 在线扩容、分片重平衡  
> 目标：业务无感、零数据丢失、可回滚

---

## 目录

1. 扩容触发条件
2. 扩容方式选型
3. 双写迁移完整流程
4. 数据迁移工具
5. 对账校验脚本
6. 切读流程
7. 回滚预案
8. 演练与发布

---

# 1. 扩容触发条件

## 1.1 触发指标

```
存储水位:
  - 单库 > 70% → 黄色预警
  - 单库 > 85% → 启动扩容
  - 单库 > 95% → 紧急扩容

性能水位:
  - QPS > 80% 容量
  - 慢查询比例 > 5%
  - 连接数 > 80%

业务预估:
  - 6 个月内将达到水位
```

## 1.2 评估文档模板

```
# 扩容评估单
当前规模:
  - 库数: 32
  - 单库容量: 800GB / 1TB
  - 总数据: 25TB
  - 月增长: 3TB
  
扩容目标:
  - 库数: 64
  - 单库目标: < 50%
  - 余量: 24 个月
  
影响:
  - 业务停机: 0
  - 风险: ...
  - 回滚: ...
```

---

# 2. 扩容方式选型

## 2.1 方式对比

| 方式 | 适用 | 复杂度 | 停机 | 数据迁移量 |
|---|---|---|---|---|
| **垂直扩容** | 短期顶 | 低 | 短 | 0 |
| **加 slave** | 读瓶颈 | 低 | 0 | 0 |
| **双倍扩容** | 容量瓶颈 | 高 | 0 | 50% |
| **加分表** | 单库容量 | 中 | 0 | 0 |
| **一致性 hash** | 热点 | 高 | 0 | 1/N |

## 2.2 推荐：双倍扩容

```
原: 32 库
新: 64 库

迁移规则:
  按 hash 高位:
    db_msg_00 旧 → db_msg_00 新（保留一半）+ db_msg_32 新（迁移一半）
    
具体:
  原: shard = hash(key) % 32
  新: shard = hash(key) % 64
  
  原 shard 0 上的数据:
    hash % 32 == 0
    → 在新模式下:
       hash % 64 == 0   (留 db_msg_00)
       hash % 64 == 32  (迁到 db_msg_32)
```

每个原库的数据 1/2 留下，1/2 迁出。

---

# 3. 双写迁移完整流程

## 3.1 总览

```
Phase 1: 准备 (1 周)
  ├─ 部署新分片
  ├─ 路由层支持双写
  └─ 灰度环境验证

Phase 2: 双写 (1 周)
  ├─ 业务双写
  ├─ 持续观察
  └─ 对账验证

Phase 3: 历史迁移 (按数据量)
  ├─ 批量复制
  ├─ 增量同步
  └─ 对账

Phase 4: 切读 (1 天)
  ├─ 灰度切读
  ├─ 全量切读
  └─ 观察

Phase 5: 停老 (30 天后)
  ├─ 停老库写入
  ├─ 数据保留 30 天
  └─ 删除老库
```

## 3.2 Phase 1: 准备

### 部署新分片
```bash
# 创建新库
for i in $(seq 32 63); do
  mysql -h dbops -e "CREATE DATABASE db_msg_$(printf %02d $i)"
  
  # 创建表（与老库 schema 一致）
  for j in $(seq 0 15); do
    mysql -h db_msg_$(printf %02d $i) < schema/im_message.sql
  done
done
```

### 路由层支持双写

```java
public class DualWriteRouter {
    private boolean dualWriteEnabled;
    
    public void insert(String table, Object key, Map<String, Object> data) {
        // 1. 写老分片
        Shard oldShard = oldRouter.route(table, key);
        oldShard.insert(data);
        
        // 2. 双写新分片（异步，失败记录）
        if (dualWriteEnabled) {
            try {
                Shard newShard = newRouter.route(table, key);
                newShard.insert(data);
            } catch (Exception e) {
                // 记录失败，不影响主路径
                dualWriteFailureLog.record(table, key, data, e);
            }
        }
    }
}
```

### 灰度开关
```yaml
# 配置中心 (etcd)
dual_write:
  im_message: false       # 各表独立开关
  mention_index: false
  inbox: false
```

## 3.3 Phase 2: 双写

### 启用双写

```bash
# 配置中心下发
etcdctl put /config/dual_write/im_message true
```

业务侧实时生效。

### 监控双写一致性

```python
# 每分钟检查
def monitor_dual_write():
    last_id = get_last_checked_id("im_message")
    new_rows = old_db.query(
        "SELECT * FROM im_message WHERE id > ? LIMIT 1000",
        last_id
    )
    
    diffs = []
    for row in new_rows:
        new_shard = new_router.route("im_message", row.conv_id)
        new_row = new_shard.query("SELECT * FROM im_message WHERE id = ?", row.id)
        if not new_row or not row_equal(row, new_row):
            diffs.append(row.id)
    
    if diffs:
        alert(f"Dual-write inconsistency: {len(diffs)} rows")
        repair(diffs)
    
    save_last_checked_id("im_message", new_rows[-1].id)
```

### 修复失败

```python
def repair(ids):
    for id in ids:
        row = old_db.query("SELECT * FROM im_message WHERE id = ?", id)
        new_shard = new_router.route("im_message", row.conv_id)
        new_shard.upsert(row)
```

## 3.4 Phase 3: 历史迁移

### 迁移工具（核心代码）

```python
import threading
import time
from queue import Queue

class MigrationTool:
    def __init__(self, old_router, new_router, table, parallelism=8):
        self.old_router = old_router
        self.new_router = new_router
        self.table = table
        self.parallelism = parallelism
        self.queue = Queue(maxsize=1000)
        
    def migrate_shard(self, old_shard_id, batch_size=1000):
        last_id = self._load_progress(old_shard_id)
        old_shard = self.old_router.get_shard(old_shard_id)
        
        while True:
            rows = old_shard.query(
                f"SELECT * FROM {self.table} WHERE id > %s ORDER BY id LIMIT %s",
                last_id, batch_size
            )
            if not rows:
                break
            
            # 按新分片归类
            by_new_shard = {}
            for row in rows:
                new_shard = self.new_router.route(self.table, row.conv_id)
                by_new_shard.setdefault(new_shard, []).append(row)
            
            # 批量写入
            for new_shard, batch in by_new_shard.items():
                new_shard.batch_upsert(batch)
            
            last_id = rows[-1].id
            self._save_progress(old_shard_id, last_id)
            
            # 限速
            self._rate_limit()
            
            # 进度
            print(f"Shard {old_shard_id}: migrated up to {last_id}")
    
    def _rate_limit(self):
        # 限制 10K rows/s per shard
        time.sleep(0.1)
    
    def run(self):
        threads = []
        for shard_id in range(32):
            t = threading.Thread(target=self.migrate_shard, args=(shard_id,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
```

### 迁移性能

```
单线程: 10K rows/s
32 线程: 30W rows/s (受限于 DB IO)

100 亿行迁移:
  100亿 / 30万 = 33,000 秒 ≈ 9 小时
```

实际控制在业务低峰期分多次完成。

### 增量补漏

```
迁移开始时记录 watermark = max(id)
迁移结束后:
  补漏: 把 watermark 之后到现在的数据再扫一遍
  
循环直到无新增 (双写期间)
```

## 3.5 Phase 4: 切读

### 灰度切读

```yaml
# 配置中心
read_strategy:
  im_message:
    new_shard_percent: 0    # 默认 0%
```

```java
public Object query(String table, Object key) {
    int percent = config.getInt("read_strategy.im_message.new_shard_percent");
    if (random() * 100 < percent) {
        return newShard.query(...);
    }
    return oldShard.query(...);
}
```

切读节奏：

```
T+0: percent=0 → 1
T+1h: percent=1 → 5
T+1d: percent=5 → 20
T+2d: percent=20 → 50
T+3d: percent=50 → 100
```

每个阶段观察：
- 错误率
- 延迟
- 业务功能正常

### 全量切读

```yaml
read_strategy:
  im_message:
    new_shard_percent: 100
```

老分片仍在双写，但不再读。

## 3.6 Phase 5: 停老

```
T+30d (切读后 30 天):
  关闭对老分片的写入
  保留数据再 30 天
  最终 DROP DATABASE
```

为什么等这么久？防止发现问题需要回滚。

---

# 4. 数据迁移工具

## 4.1 工具特性要求

```
- 支持断点续传
- 限速可配
- 多线程并行
- 进度可见
- 失败重试
- 一致性校验
```

## 4.2 完整工具实现

```python
#!/usr/bin/env python3
"""
DB Migration Tool
Usage: python migrate.py --table im_message --shards 0-31 --rate 10000
"""

import argparse
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

class Migrator:
    def __init__(self, config):
        self.config = config
        self.old_db = self._connect_old()
        self.new_db = self._connect_new()
        self.progress_file = config['progress_file']
        self.progress = self._load_progress()
        self.lock = threading.Lock()
    
    def _load_progress(self):
        try:
            with open(self.progress_file) as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def _save_progress(self):
        with self.lock:
            with open(self.progress_file, 'w') as f:
                json.dump(self.progress, f)
    
    def migrate_shard(self, shard_id):
        progress_key = f"{self.config['table']}:shard:{shard_id}"
        last_id = self.progress.get(progress_key, 0)
        
        old_conn = self.old_db.connect(shard_id)
        
        total = 0
        start = time.time()
        
        while True:
            rows = self._fetch_batch(old_conn, last_id)
            if not rows:
                break
            
            self._write_batch(rows)
            
            last_id = rows[-1]['id']
            self.progress[progress_key] = last_id
            
            total += len(rows)
            
            # 进度
            if total % 100000 == 0:
                elapsed = time.time() - start
                rate = total / elapsed
                logging.info(f"Shard {shard_id}: {total} rows, {rate:.0f} rows/s")
                self._save_progress()
            
            # 限速
            self._rate_limit(len(rows))
        
        self._save_progress()
        logging.info(f"Shard {shard_id} done: {total} rows")
    
    def _fetch_batch(self, conn, last_id):
        sql = f"""
            SELECT * FROM {self.config['table']}
            WHERE id > %s
            ORDER BY id
            LIMIT %s
        """
        return conn.query(sql, last_id, self.config['batch_size'])
    
    def _write_batch(self, rows):
        # 按新分片分组
        groups = {}
        for row in rows:
            new_shard_id = self._calc_new_shard(row)
            groups.setdefault(new_shard_id, []).append(row)
        
        for new_shard_id, batch in groups.items():
            new_conn = self.new_db.connect(new_shard_id)
            new_conn.upsert_batch(self.config['table'], batch)
    
    def _calc_new_shard(self, row):
        shard_key = self.config['shard_key']  # e.g. 'conv_id'
        return hash(row[shard_key]) % self.config['new_shard_count']
    
    def _rate_limit(self, n):
        delay = n / self.config['rate']
        time.sleep(delay)
    
    def run(self, shards):
        with ThreadPoolExecutor(max_workers=self.config['parallelism']) as executor:
            futures = [executor.submit(self.migrate_shard, s) for s in shards]
            for f in futures:
                f.result()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--shards', required=True)
    args = parser.parse_args()
    
    config = json.load(open(args.config))
    shards = parse_range(args.shards)
    
    Migrator(config).run(shards)
```

## 4.3 配置示例

```json
{
  "table": "im_message",
  "shard_key": "conv_id",
  "new_shard_count": 64,
  "old_shard_count": 32,
  "batch_size": 1000,
  "parallelism": 16,
  "rate": 100000,
  "progress_file": "/var/lib/migration/progress.json",
  "old_db": {
    "hosts": ["db_msg_old:3306"],
    "user": "...",
    "password": "..."
  },
  "new_db": {
    "hosts": ["db_msg_new:3306"],
    "user": "...",
    "password": "..."
  }
}
```

## 4.4 进度可视���

```
启动 web 界面 / Prometheus 暴露指标:

migration_total_rows{table, shard} 
migration_processed_rows{table, shard}
migration_rate_rows_per_sec{table, shard}
migration_eta_seconds{table, shard}
```

---

# 5. 对账校验脚本

## 5.1 抽样对账

```python
def sample_verify(table, sample_count=10000):
    diffs = []
    
    for shard_id in range(old_shard_count):
        old_conn = old_db.connect(shard_id)
        
        # 随机抽样
        rows = old_conn.query(f"""
            SELECT * FROM {table}
            ORDER BY RAND()
            LIMIT {sample_count // old_shard_count}
        """)
        
        for row in rows:
            new_shard_id = calc_new_shard(row)
            new_conn = new_db.connect(new_shard_id)
            new_row = new_conn.query(
                f"SELECT * FROM {table} WHERE id = %s", row['id']
            )
            
            if not new_row or not row_equal(row, new_row):
                diffs.append({
                    'id': row['id'],
                    'old': row,
                    'new': new_row
                })
    
    return diffs
```

## 5.2 全量哈希对账

```python
def full_verify_by_hash(table):
    """按时间分桶比对哈希值"""
    
    for hour_bucket in time_buckets():
        old_hash = old_db.query(f"""
            SELECT 
              COUNT(*) as cnt,
              SUM(CRC32(CONCAT(id, content, sender_id))) as checksum
            FROM {table}
            WHERE created_at BETWEEN %s AND %s
        """, hour_bucket.start, hour_bucket.end)
        
        new_hash = new_db.query(f"""
            SELECT 
              COUNT(*) as cnt,
              SUM(CRC32(CONCAT(id, content, sender_id))) as checksum
            FROM {table}
            WHERE created_at BETWEEN %s AND %s
        """, hour_bucket.start, hour_bucket.end)
        
        if old_hash != new_hash:
            print(f"DIFF at {hour_bucket}: old={old_hash} new={new_hash}")
            drill_down(hour_bucket)

def drill_down(hour_bucket):
    """缩小范围定位差异"""
    for minute in minute_buckets(hour_bucket):
        # ... 递归
```

## 5.3 行级对账

```python
def row_level_verify(table, time_range):
    """逐行对比"""
    
    old_iter = old_db.iter(f"""
        SELECT * FROM {table} 
        WHERE created_at BETWEEN %s AND %s
        ORDER BY id
    """, time_range.start, time_range.end)
    
    new_iter = new_db.iter_all_shards(f"""
        SELECT * FROM {table} 
        WHERE created_at BETWEEN %s AND %s
        ORDER BY id
    """)
    
    diffs = []
    while True:
        old_row = next(old_iter, None)
        new_row = next(new_iter, None)
        
        if old_row is None and new_row is None:
            break
        
        if not old_row or not new_row or old_row.id != new_row.id:
            diffs.append((old_row, new_row))
        elif not row_equal(old_row, new_row):
            diffs.append((old_row, new_row))
    
    return diffs
```

## 5.4 自动修复

```python
def auto_repair(diffs):
    for old_row, new_row in diffs:
        if old_row and not new_row:
            # 新库缺，补
            new_shard = calc_new_shard(old_row)
            new_db.upsert(table, old_row, new_shard)
        elif new_row and not old_row:
            # 老库缺（不应发生），告警
            alert(f"Row in new but not old: {new_row.id}")
        else:
            # 内容不一致，老为准
            new_shard = calc_new_shard(old_row)
            new_db.upsert(table, old_row, new_shard)
```

## 5.5 持续对账（双写期间）

```python
# 每 5 分钟扫一次最近的双写数据
def continuous_verify():
    while True:
        last_check = load_last_check_time()
        now = time.time()
        
        diffs = row_level_verify(table, TimeRange(last_check, now))
        
        if diffs:
            metrics.dual_write_diff.inc(len(diffs))
            auto_repair(diffs)
        
        save_last_check_time(now)
        time.sleep(300)
```

---

# 6. 切读流程

## 6.1 灰度配置

```python
def query(table, key):
    config = get_config(f"read_strategy.{table}")
    
    if should_use_new(key, config.percent):
        return new_router.query(table, key)
    return old_router.query(table, key)

def should_use_new(key, percent):
    # 用 key 的 hash 决定，确保同一 key 始终走同一边
    return (hash(key) % 100) < percent
```

## 6.2 双读对比

切读初期，可双读对比：

```python
def query_with_compare(table, key):
    old_result = old_router.query(table, key)
    new_result = new_router.query(table, key)
    
    if old_result != new_result:
        log_diff(table, key, old_result, new_result)
    
    return old_result  # 返回老库为准
```

只在抽样比例（如 1%）做双读，避免性能 2x。

## 6.3 切读节奏

```
建议节奏:
  T+0:  1%  (观察 1 小时)
  T+1h: 5%  (观察 4 小时)
  T+1d: 20% (观察 1 天)
  T+2d: 50% (观察 1 天)
  T+3d: 100%
  
每阶段观察:
  - 错误率
  - 延迟 P99
  - 业务功能正常
  - 对账无差异
```

---

# 7. 回滚预案

## 7.1 各阶段回滚

### Phase 1 准备阶段
```
回滚: 删除新分片，无影响
```

### Phase 2 双写阶段
```
回滚: 关闭双写开关
  etcdctl put /config/dual_write/im_message false

老分片不受影响
新分片数据废弃
```

### Phase 3 迁移阶段
```
回滚: 暂停迁移工具
  迁移已完成的数据保留
  老分片是 source of truth
  
重启后从断点续传
```

### Phase 4 切读阶段
```
回滚: 切读比例���回 0
  etcdctl put /config/read_strategy/im_message/new_shard_percent 0

立即生效
老分片提供查询
```

### Phase 5 停老阶段
```
30 天内可回滚:
  重新启用双写
  重新切读到老
  
30 天后:
  老分片删除，无法回滚
  必须从新分片反向迁移
```

## 7.2 紧急回滚流程

```
1. 确认问题
2. 配置中心切回老路由 (秒级)
3. 业务恢复正常
4. 排查问题
5. 修复后重新尝试
```

---

# 8. 演练与发布

## 8.1 演练环境

```
预生产环境:
  - 真实数据规模（缩小 10x）
  - 同样的迁移流程
  - 完整演练 Phase 1~5
  - 验证回滚
```

## 8.2 演练 checklist

```
[ ] 部署新分片成功
[ ] 双写成功率 > 99.99%
[ ] 历史迁移完成
[ ] 抽样对账无差异
[ ] 全量哈希对账无差异
[ ] 灰度切读 1% 正常
[ ] 全量切读正常
[ ] 回滚演练成功
[ ] 性能对比通过
```

## 8.3 发布前评审

```
- 容量数据
- 迁移时间预估
- 风险点
- 应急预案
- 值守安排
- 回滚演练记录
```

## 8.4 发布安排

```
时间窗口: 业务低峰
人员: SRE + DBA + 业务负责人
工具: 实时大盘 + 操作记录
通信: 战时群 + 视频会议

每 30 分钟同步进展
```

## 8.5 发布后

```
- 1 周内每日对账
- 监控异常指标
- 准备应急
- 30 天后清理
```

---

**文档结束** | Version 1.0