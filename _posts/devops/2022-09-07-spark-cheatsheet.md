---
layout:     post
title:      Spark SQL Cheat Sheet
subtitle:   `regexp_extract` / `filter` / DataType 的最小速查
date:       2022-09-07
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Spark
    - SQL
    - Cheat Sheet
---

>原始笔记是几条零散的 Spark / Spark SQL 命令，这里按用途分节整理成速查版本。

## 1. 正则提取字段：`regexp_extract`

从一段日志里抽出某个数字字段的常见写法：

```sql
CAST(regexp_extract(message, '(.*)(online_push=)([0-9]+)(.*)', 3) AS INT)
```

要点：

- 第三个参数 `3` 表示取第 3 个捕获组，对应 `([0-9]+)`
- 正则里如果要匹配特殊字符，记得加 `\`
- 抽出来后通常还要 `CAST` 成目标类型再聚合

## 2. 常用过滤与聚合：`filter` / `groupBy`

DataFrame 上常用片段：

```scala
// 按列求和
dfs.select(sum("online_push")).show()

// 按某列分组计数
dfs_ts_pc.groupBy("ts_pc_type").count.show()

// 先按条件过滤，再分组计数
dfs_rt.filter($"msg_type" === 4).groupBy("cli_platform").count.show()
dfs_rt.filter($"msg_type" >  4).groupBy("cli_platform").count.show()
```

`===` 是 Spark Column 的等值比较；`>`、`<` 等也都重载在 Column 上。

## 3. 文档入口

需要查 join 或字段类型时，直接跳官方文档更稳：

- Join 类型：<https://spark.apache.org/docs/latest/sql-ref-syntax-qry-select-join.html>
- DataType：<https://spark.apache.org/docs/latest/sql-ref-datatypes.html>

原始笔记里两处都指向 DataType 页，这里把 join 改回到对应入口。

## 后续可补的方向

- 常用 window function（`row_number`、`rank`、`lag`）
- 几种 join（broadcast / sort-merge / shuffle hash）的选择经验
- 在线上跑 Spark SQL 时的资源参数模板（`executor` / `memory` / `partitions`）

当前这篇先按速查表用，后续再补查询调优相关内容。
