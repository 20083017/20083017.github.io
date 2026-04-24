---
layout:     post
title:      Redis Cheat Sheet
subtitle:   常用命令速查与线上使用注意事项
date:       2026-04-24
author:     BY
header-img: img/post-bg-unix-linux.jpg
catalog: true
tags:
    - Redis
    - Database
    - Linux
---

>这份速查表主要用于回忆命令语法。真正在线上执行前，先确认 Redis 版本、数据规模和命令复杂度，避免把实验环境命令直接带到生产环境。

参考：

- http://www.mykeep.fun/redis
- https://github.com/LeCoupa/awesome-cheatsheets

## 基础

```bash
redis-server /path/redis.conf        # 按指定配置启动 Redis
redis-cli                            # 打开 redis 命令行
sudo systemctl restart redis.service # 重启 Redis（不同发行版服务名可能不同）
sudo systemctl status redis          # 查看 Redis 状态
```

## Strings

```text
APPEND key value
BITCOUNT key [start end]
SET key value
SETNX key value
SETRANGE key offset value
STRLEN key
MSET key value [key value ...]
MSETNX key value [key value ...]
GET key
GETRANGE key start end
MGET key [key ...]
INCR key
INCRBY key increment
INCRBYFLOAT key increment
DECR key
DECRBY key decrement
DEL key
EXPIRE key 120
TTL key
```

## Lists

```text
RPUSH key value [value ...]
RPUSHX key value
LPUSH key value [value ...]
LPUSHX key value
LRANGE key start stop
LINDEX key index
LINSERT key BEFORE|AFTER pivot value
LLEN key
LPOP key
LSET key index value
LREM key number_of_occurrences value
LTRIM key start stop
RPOP key
RPOPLPUSH source destination
BLPOP key [key ...] timeout
BRPOP key [key ...] timeout
```

## Sets

```text
SADD key member [member ...]
SCARD key
SREM key member [member ...]
SISMEMBER myset value
SMEMBERS myset
SUNION key [key ...]
SINTER key [key ...]
SMOVE source destination member
SPOP key [count]
```

## Sorted Sets

```text
ZADD key [NX|XX] [CH] [INCR] score member [score member ...]
ZCARD key
ZCOUNT key min max
ZINCRBY key increment member
ZRANGE key start stop [WITHSCORES]
ZRANK key member
ZREM key member [member ...]
ZREMRANGEBYRANK key start stop
ZREMRANGEBYSCORE key min max
ZSCORE key member
ZRANGEBYSCORE key min max [WITHSCORES] [LIMIT offset count]
```

## Hashes

```text
HGET key field
HGETALL key
HSET key field value
HSETNX key field value
HSET key field value [field value ...]   # 新版本通常直接用 HSET 多字段
HINCRBY key field increment
HDEL key field [field ...]
HEXISTS key field
HKEYS key
HLEN key
HSTRLEN key field
HVALS key
```

`HMSET` 在较新的 Redis 文档里已经不再推荐作为首选写法，通常直接使用支持多字段参数的 `HSET` 即可。

## HyperLogLog

```text
PFADD key element [element ...]
PFCOUNT key [key ...]
PFMERGE destkey sourcekey [sourcekey ...]
```

## Pub/Sub

```text
PSUBSCRIBE pattern [pattern ...]
PUBSUB subcommand [argument [argument ...]]
PUBLISH channel message
PUNSUBSCRIBE [pattern [pattern ...]]
SUBSCRIBE channel [channel ...]
UNSUBSCRIBE [channel [channel ...]]
```

## 线上环境要特别注意的命令

不要把下面这些命令默认当成“随手可用”：

- `KEYS pattern`：会阻塞扫描整个 keyspace，实例大时非常危险
- `SMEMBERS` / `HGETALL`：集合或哈希很大时，返回量可能失控
- `LRANGE 0 -1`：大列表上会把整个列表拉回客户端

线上排查 key 时，优先使用：

```text
SCAN 0 MATCH pattern COUNT 100
```

如果只是确认某个大 key 的规模，也优先使用更轻量的长度类命令，例如 `LLEN`、`SCARD`、`HLEN`、`STRLEN`。
