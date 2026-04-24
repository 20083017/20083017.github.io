---
layout:     post
title:      MySQL 常用操作记录
subtitle:   导出查询结果与大表删除的安全做法
date:       2026-04-24
author:     BY
header-img: img/post-bg-unix-linux.jpg
catalog: true
tags:
    - MySQL
    - Database
    - Linux
---

>本文保留几个常用 MySQL 片段，但涉及批量删除时请先在测试环境验证，并确认备份、回滚方案和主从延迟监控都已准备好。

## 导出查询结果到文件

避免把密码直接写进命令行；命令行参数会进入 shell history，也可能被同机其他用户看到。更安全的方式是交互输入密码，或使用 `mysql_config_editor` 预置登录信息。

```bash
mysql -h <host> -P <port> -u <user> -p \
  --batch --skip-column-names \
  -e "SELECT id FROM bdim_roam._tablet_789" > /tmp/tablet_ids.txt
```

如果需要导出带表头的 TSV/CSV，优先使用 `SELECT ... INTO OUTFILE` 或专门的导出工具，并确认目标路径权限与字符集配置。

## INNER JOIN 示例

```sql
SELECT *
FROM im_msgroaming
INNER JOIN im_user1 ON im_msgroaming.uid1 = im_user1.uid1
INNER JOIN im_user2 ON im_msgroaming.uid2 = im_user2.uid2;
```

实际线上查询时，建议只取需要的字段，并确认关联列上已有索引，避免把示例 SQL 直接带到大表环境中造成全表扫描。

## 大表批量删除的风险

假设表引擎为 InnoDB，且数据量达到千万级以上。一次性执行大范围 `DELETE` 时，通常会带来这些问题：

- 长事务与大范围锁竞争，影响线上读写
- 大量 binlog / redo log，放大主从同步压力
- 删除标记与页碎片增多，空间不会立刻回收
- 回滚时间长，失败时恢复代价高

因此不要直接执行“无条件大删”，而是优先选择**按主键或其他有索引的条件分批删除**。

## 更稳妥的删除方式

```sql
DELETE FROM your_table
WHERE id > ? AND id <= ?
ORDER BY id
LIMIT 1000;
```

建议做法：

- 以主键或有索引的时间列分段
- 单批量控制在小事务范围内，例如 500~5000 行
- 每批之间短暂 sleep，持续观察 QPS、锁等待和从库延迟
- 先删冷数据，再安排业务低峰执行

如果只是需要“归档 + 清空间”，很多场景下更适合：

1. 新建目标表并回填保留数据
2. 在维护窗口内切换表名
3. 最后删除旧表

这种“重建并切换”的方式虽然更重，但通常比在原表上长时间删除更可控。

## 关于表重建

删除完成后，如果确实需要回收空间，可以再评估 `OPTIMIZE TABLE` 或重建表。但这一步不是默认动作，必须结合：

- MySQL 版本与存储引擎能力
- 业务是否允许维护窗口
- 表大小、磁盘空间余量、复制拓扑

不要把“删完就在线重建表”当成固定脚本直接执行。

## 关于触发器双写

“新表 + 触发器同步 + 切换”的思路只适合经过充分测试的迁移方案。触发器本身会增加写入链路复杂度，调试和回滚也更困难；如果只是临时清理历史数据，不建议把触发器方案当成默认选项。
