---
layout:     post
title:      spark cheat sheet
subtitle:   工具网站
date:       2022-09-07
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Tool
---

>随便整理的一些spark sql命令


# regex

  CAST(regexp_extract(message, '(.*)(online_push=)([0-9]+)(.*)', 3) AS INT)   

# filter
  dfs.select(sum("online_push")).show();   
  dfs_ts_pc.groupBy("ts_pc_type").count.show();   
  dfs_rt.filter($"msg_type"=== 4).groupBy("cli_platform").count.show();   
  dfs_rt.filter($"msg_type" > 4).groupBy("cli_platform").count.show();   


# join
https://spark.apache.org/docs/latest/sql-ref-datatypes.html

# DataType
https://spark.apache.org/docs/latest/sql-ref-datatypes.html

#### 创建仓库（初始化）


