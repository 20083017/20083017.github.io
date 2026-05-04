# IM SRE 运维手册 v1.0

> 适用对象：SRE / 运维 / On-Call 工程师  
> 目的：快速响应、标准化处理

---

## 目录

1. [On-Call 制度](#1-on-call-制度)
2. [告警分级与响应](#2-告警分级与响应)
3. [监控大盘](#3-监控大盘)
4. [故障 Runbook](#4-故障-runbook)
5. [应急预案](#5-应急预案)
6. [变更管理](#6-变更管理)
7. [复盘机制](#7-复盘机制)
8. [常用工具与命令](#8-常用工具与命令)

---

# 1. On-Call 制度

## 1.1 轮班制度

```
On-Call 轮班: 每人 7 天
主 On-Call:    1 人 (P0/P1 第一响应)
副 On-Call:    1 人 (主无响应时升级)
团队 Lead:     P0 时介入
```

## 1.2 响应 SLA

| 级别 | 首次响应 | 介入处理 | 升级 |
|---|---|---|---|
| P0 | 5 min | 立即 | 主+副+Lead |
| P1 | 15 min | 30 min | 主+副 |
| P2 | 1 h | 4 h | 主 |
| P3 | 1 工作日 | 1 工作日 | 主 |

## 1.3 工具准备

每个 On-Call 必备：
- 告警手机（24h 不静音）
- VPN 接入
- 监控大盘账号
- 跳板机权限
- IM 群组（应急群常驻）
- 此手册（离线版）

---

# 2. 告警分级与响应

## 2.1 P0 告警（业务大面积影响）

| 触发条件 | 渠道 |
|---|---|
| 接入成功率 < 95% 持续 2 min | 电话 + IM + 邮件 |
| 消息送达率 < 99% 持续 5 min | 电话 + IM |
| P99 延迟 > 5s 持续 5 min | 电话 + IM |
| 主集群整体不可用 | 电话立即 |
| 数据库主库宕机 | 电话立即 |
| Kafka 不可用 | 电话立即 |

### 响应动作
```
1. 5 min 内承认告警 + 进战时群
2. 第一时间评估影响范围
3. 决策: 修复 vs 回滚 vs 切流
4. 同步业务 / 客服 / 高层
5. 操作 + 验证
6. 解除告警
7. 启动复盘
```

## 2.2 P1 告警（局部异常）

| 触发条件 |
|---|
| 接入成功率 < 99% 持续 5 min |
| 单分片 DB 不可用 |
| 单 Kafka topic lag > 10万 |
| Redis 主从延迟 > 30s |
| Push 失败率 > 5% |

## 2.3 P2 告警（潜在风险）

| 触发条件 |
|---|
| 磁盘使用 > 80% |
| 内存使用 > 85% |
| 单实例连接数 > 90% |
| 慢查询数突增 |
| 异常封禁数突增 |

## 2.4 告警自愈

可自愈场景：
- 单 Pod 异常 → K8s 自动重启
- 单连接卡死 → 心跳超时关闭
- Outbox 短暂滞留 → Worker 自动重试
- Redis 主挂 → Sentinel 自动切主

不需人工介入，但要记录与统计。

---

# 3. 监控大盘

## 3.1 总览大盘（首页）

```
┌─────────────────────────────────────────────┐
│  实时业务指标                                │
│  在线用户: 920万    消息 QPS: 45万            │
│  P50: 80ms          P99: 320ms               │
│  送达率: 99.992%    错误率: 0.008%            │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│  各服务健康状态 (实例数 / 健康数)            │
│  Gateway:    50/50   ✓                       │
│  MsgWrite:   30/30   ✓                       │
│  Deliver:    20/20   ✓                       │
│  Push:       20/19   ⚠️                       │
│  ...                                         │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│  数据层水位                                  │
│  MySQL:  CPU 35% / IO 40% / Conn 50%         │
│  Redis:  Mem 55% / Hit 99.2%                 │
│  Kafka:  Lag 1.2万 / Disk 60%                │
└─────────────────────────────────────────────┘
```

## 3.2 核心子大盘

### 接入层大盘
- 各 Gateway 连接数
- 建连/秒
- 协议分布（QUIC/WS）
- TLS 握手延迟
- QUIC 迁移成功率
- 心跳成功率
- 各 Gateway CPU/内存/网络

### 消息链路大盘
- 写入 QPS（按消息类型）
- 写入延迟分布
- Outbox 堆积量
- Kafka 各 topic 生产/消费速率
- 各 partition lag
- 投递成功率（按目标网关）
- 离线收件箱写入速率

### 数据层大盘
- MySQL：QPS、慢查询、连接数、主从延迟
- Redis：QPS、内存、命中率、慢查询
- Kafka：吞吐、ISR、Under-Replicated
- HBase：RegionServer 状态、Compaction

### 业务大盘
- DAU / 在线
- 消息发送趋势
- 群活跃度
- @ 消息量
- 撤回 / 编辑速率
- Push 成功率（按厂商）
- 风控封禁数

### SLO 大盘
- 各服务可用性（5min/1h/24h/7d）
- 错误预算消耗
- 长期趋势

## 3.3 关键查询语句（PromQL）

```promql
# 消息成功率
sum(rate(msg_write_success[5m])) / sum(rate(msg_write_total[5m]))

# 单 Gateway 连接数 TOP10
topk(10, gateway_connection_count)

# Kafka lag
sum by (topic, partition) (kafka_consumer_lag)

# 各分片 MySQL CPU
mysql_global_status_threads_running{shard=~".*"}

# Redis 命中率
redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)
```

---

# 4. 故障 Runbook

## 4.1 Gateway 大量掉线

### 症状
- 在线用户骤降
- 客户端集中重连
- 接入层 QPS 突增

### 排查
```
1. 看哪些 Gateway 异常
   kubectl get pods -l app=gateway | grep -v Running
   
2. 看是否单 AZ / 单地域问题
   按 AZ 分组的连接数监控
   
3. 看是否 LB 异常
   curl edge.im.example.com/health
```

### 处理
```
单 Pod 异常: K8s 自动重启，等待
单 AZ 异常: 流量自动切到其他 AZ，无需操作
LB 异常: 联系网络组
全集群异常: 切流到其他区域，详见 §5.1
```

## 4.2 消息延迟陡增

### 症状
- P99 延迟 > 1s
- 客户端反馈"消息慢"

### 排查
```
1. 链路打点：哪一段慢？
   - Gateway → MsgWrite
   - MsgWrite → DB
   - Outbox → Kafka
   - Kafka → Deliver
   - Deliver → Gateway → Client
   
2. 查 trace_id 追踪具体一条消息

3. 查各组件资源水位
```

### 常见原因与处理

| 原因 | 处理 |
|---|---|
| DB 慢 | 看慢查询，KILL，优化 |
| DB 连接池满 | 加连接数 / 重启应用 |
| Kafka lag | 扩 consumer / 排查消费者 |
| Redis 慢 | 看 SLOWLOG，看大 key |
| GC 频繁 | dump heap，调 JVM |
| 网络丢包 | 联系网络组 |

## 4.3 Kafka Topic Lag 飙升

### 症状
- consumer group lag > 10万
- 离线消息延迟、Push 延迟

### 排查
```bash
# 看具体哪个 topic / partition lag
kafka-consumer-groups --describe --all-groups | sort -k5 -n | tail

# 看消费者实例状态
kubectl get pods -l app=consumer-xxx
```

### 处理
```
1. 消费实例不够 → 扩容 consumer
   kubectl scale deploy consumer-xxx --replicas=20
   
2. 消费者代码慢 → 临时调大 max.poll.records
   
3. 下游 DB 慢 → 看下游
   
4. 单 partition 热点 → 临时增加 partition (注意顺序)
   
5. 实在追不上 → 临时跳过或降低消费精度
```

## 4.4 数据库主库挂

### 症状
- 写入失败
- DB 监控告警
- 应用大量超时

### 自动切主流程
```
MHA / Orchestrator 自动选主:
1. 探测主库不可用 (3 次失败 ≈ 30s)
2. 选取数据最新的从库
3. 提升为新主
4. 应用通过 DNS / VIP 切到新主
5. 旧主修复后作为从加回

期间应用应自动重连
```

### 手动切主（自动失败时）
```bash
# 1. 确认主库真的死了
mysqladmin -h db15-master ping  # connection refused
ssh db15-master 'systemctl status mysql'

# 2. 选取新主（找最新的从）
mysql -h db15-slave1 -e "SHOW SLAVE STATUS\G" | grep Position

# 3. 提升从为主
mysql -h db15-slave1 -e "STOP SLAVE; RESET MASTER;"

# 4. 修改其他从指向新主
mysql -h db15-slave2 -e "CHANGE MASTER TO MASTER_HOST='db15-slave1', ..."

# 5. 切换应用 DNS
update_dns "db15-master.im" → db15-slave1
```

## 4.5 Redis 主挂

```
Sentinel 自动切主:
1. 探测 30s 内 quorum 个 Sentinel 都认为主挂
2. 选取从库提升为主
3. 通知客户端

期间影响:
- 写入：30s 不可用
- 读：从库仍可用
```

应急：限流降级，DB 兜底。

## 4.6 大群消息洪水

### 症状
- 单 conv 消息 QPS 异常飙升
- 该 conv 的 partition lag 暴涨
- 群成员投诉"消息延迟"

### 处理
```
1. 临时提高该群消息限流到 2/s
   curl config-center/api/set?key=rate.conv.{convId}&value=2

2. 该群移到大群专属 topic
   curl config-center/api/set?key=large_conv:{convId}&value=true

3. 必要时临时禁言群
   API: /admin/group/{convId}/mute?duration=10m
```

## 4.7 Push 大面积失败

### 症状
- Push 失败率 > 10%
- 离线用户收不到通知

### 排查
```
1. 看是哪个厂商通道失败
   Push 监控按 channel 分组
   
2. 联系厂商确认（APNs/FCM/华为/小米/OPPO/vivo）
```

### 处理
```
- 单厂商挂 → 切到备用厂商
- 多厂商挂（如海外 GFW 问题）→ 联系运营
- token 过期批量 → 推动客户端升级
```

## 4.8 攻击事件

### 症状
- 单 IP 大量建连
- 单用户高频发消息
- 异常 token 请求

### 处理
```
1. 立即拉入黑名单
   curl risk/api/block_ip?ip=x.x.x.x&duration=24h
   
2. 提高全局限流阈值（防扩散）
   
3. 排查攻击模式
   日志聚合分析
   
4. 上��安全组
```

## 4.9 数据误删 / 误更新

```
立即操作:
1. 停止应用写入相关表
2. 记录误操作时间点
3. 从 binlog 找到操作前状态
4. 恢复数据 (基于备份+binlog重放)
5. 校验后恢复服务

工具: 
- mysqlbinlog
- xtrabackup
- 自研回滚工具
```

---

# 5. 应急预案

## 5.1 整地域切流

### 触发条件
- 单地域 > 30% 服务不可用
- 单地域机房断电 / 网络中断
- 单地域不可恢复故障 > 30 min

### 操作步骤
```
[决策] T+0 min
  - On-Call 评估，与 Lead 确认
  - 通知业务方

[切流] T+5 min
  - 修改 GSLB 配置
    把 East 区流量切到 South 区 50%
  - DNS TTL 已设 60s，1 分钟生效

[数据] T+10 min
  - South 区 DB Standby 提升为主
  - 启动跨区数据同步追平
  
[观察] T+15 min
  - 客户端重连成功率
  - 业务指标恢复
  
[完成] T+30 min
  - 全量切完
  - 通知业务

恢复时反向操作。
```

## 5.2 全站只读模式

### 触发条件
- 写入链路严重故障
- 数据一致性风险
- 需要紧急维护

### 操作
```
1. 配置中心下发 force.read_only=true
2. 各服务收到后:
   - 拒绝写消息（返回 503）
   - 仍允许读 / 拉历史
3. 客户端 UI 提示"系统维护中"
```

## 5.3 紧急限流降级

```bash
# 全局降级
curl config-center/set \
  -d '{"key":"rate.global.qps","value":100000}'

# 关闭非核心功能
curl config-center/set -d '{"key":"kill.typing","value":true}'
curl config-center/set -d '{"key":"kill.read_receipt","value":true}'
curl config-center/set -d '{"key":"kill.large_group_fanout","value":true}'

# 关闭历史搜索
curl config-center/set -d '{"key":"kill.search","value":true}'
```

## 5.4 数据回填 / 补偿

某下游消费失败导致数据缺失：

```
1. 确认缺失范围 (时间窗 + 维度)
2. 从源（im_message / Kafka 历史）重放
3. 重放时下游必须保证幂等
4. 校验补齐成功

例：inbox 写入丢失
  Kafka 还在 → 重置 consumer offset 重新消费
  Kafka 已过期 → 从 im_message 扫描重新生成事件
```

## 5.5 流量洪峰预案

大型活动 / 春节红包 / 突发热点：

```
赛前准备:
- 资源扩容 30~50%
- 限流阈值预调整
- 大 V / 热点群预识别
- 演练熔断/降级

赛中:
- 实时大盘观察
- 必要时���动限流
- 关闭非核心功能

赛后:
- 资源回收
- 复盘
```

---

# 6. 变更管理

## 6.1 变更分级

| 级别 | 影响 | 审批 | 窗口 |
|---|---|---|---|
| L0 | 配置 / 灰度 | 直接 | 任意 |
| L1 | 应用发布 | Team Lead | 工作时间 |
| L2 | DB 变更 | DBA + Lead | 业务低谷 |
| L3 | 架构变更 | 架构组 + 总监 | 计划窗口 |

## 6.2 变更窗口

```
✓ 推荐: 周二/周三 10:00-17:00
⚠️ 谨慎: 周五下午（防止周末爆雷）
✗ 禁止: 节假日、大促前后、重大活动期间
```

## 6.3 变更检查表

参考主规范文档 §14.6。

## 6.4 高风险变更（必须演练）

- 协议升级
- 数据库 schema 变更
- Kafka topic 重组
- 跨地域同步链路变更
- 路由规则变更

---

# 7. 复盘机制

## 7.1 复盘原则

- 不追责，重总结
- 时间线必须清晰
- 根因分析（5 Why）
- 改进项可落地、可追踪

## 7.2 复盘模板

```markdown
# 故障复盘: {故障编号}

## 基本信息
- 时间: 2026-05-04 14:23 ~ 14:48 (25 min)
- 级别: P1
- 影响: 华东区 5% 用户消息延迟 > 5s
- 责任团队: 消息组

## 时间线
14:23  告警触发: msg_p99_latency > 5s
14:25  On-Call 进群
14:28  定位: Kafka msg.fanout topic lag 暴涨
14:32  发现: 某大群被刷消息
14:35  执行: 群临时限流
14:42  lag 恢复
14:48  告警解除

## 根因
- 直接原因: 大群 conv_id=xxx 被脚本刷消息
- 根本原因: 大群限流阈值过高 (50/s)
- 触发条件: 攻击者使用慢速攻击绕过单用户限流

## 改进项
| 编号 | 描述 | 负责人 | 截止 |
|---|---|---|---|
| 1 | 大群限流降至 20/s | @张三 | 2026-05-08 |
| 2 | 风控加入慢速刷消息检测 | @李四 | 2026-05-15 |
| 3 | Kafka 大群独立 topic | @王五 | 2026-05-30 |

## 经验教训
- 监控对单 conv 的消息速率不敏感，需补
- 限流阈值需按群规模分级
```

## 7.3 复盘频率

```
P0: 24h 内复盘
P1: 3 天内
P2: 1 周
重大变更: 必复盘
```

---

# 8. 常用工具与命令

## 8.1 K8s

```bash
# 看异常 Pod
kubectl get pods -A | grep -v Running

# 查 Pod 日志
kubectl logs -f gateway-xxx --tail=1000

# 进 Pod
kubectl exec -it gateway-xxx -- bash

# 滚动重启
kubectl rollout restart deploy/gateway

# 扩容
kubectl scale deploy/consumer --replicas=30

# 回滚
kubectl rollout undo deploy/msg-write
```

## 8.2 MySQL

```sql
-- 当前连接
SHOW PROCESSLIST;

-- 慢查询
SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 10;

-- KILL 查询
KILL <query_id>;

-- 表大小
SELECT table_name, table_rows, data_length/1024/1024 AS size_mb 
FROM information_schema.tables 
WHERE table_schema='im' ORDER BY size_mb DESC;

-- 主从状态
SHOW MASTER STATUS;
SHOW SLAVE STATUS\G
```

## 8.3 Redis

```bash
# 监控
redis-cli --stat

# 慢查询
redis-cli SLOWLOG GET 10

# 大 key 扫描
redis-cli --bigkeys

# 内存分析
redis-cli MEMORY USAGE <key>

# 集群状态
redis-cli CLUSTER INFO
redis-cli CLUSTER NODES
```

## 8.4 Kafka

```bash
# topic 列表
kafka-topics --list

# topic 详情
kafka-topics --describe --topic msg.fanout

# consumer group lag
kafka-consumer-groups --describe --group cg-deliver

# 重置 offset
kafka-consumer-groups --group cg-deliver \
  --topic msg.fanout --reset-offsets --to-datetime 2026-05-04T10:00:00.000 --execute

# 看消息
kafka-console-consumer --topic msg.fanout --from-beginning --max-messages 10
```

## 8.5 网络排查

```bash
# 连接数
ss -s
netstat -an | awk '/^tcp/ {S[$NF]++} END {for(a in S) print a, S[a]}'

# 端口监听
ss -tlnp

# 抓包
tcpdump -i eth0 -nn 'port 443' -w /tmp/cap.pcap

# 网络延迟
mtr edge.im.example.com
```

## 8.6 自研运维 API

```
# 切流
POST /sre/api/switch_traffic
  {"region":"east","target":"south","percent":50}

# 应急开关
POST /sre/api/emergency_switch
  {"key":"kill.typing","value":true}

# 强制踢用户
POST /sre/api/kick_user
  {"user_id":1001,"reason":"abuse"}

# 黑名单
POST /sre/api/blacklist
  {"type":"ip","value":"x.x.x.x","duration":3600}
```

---

# 文档维护

- 文档负责人: SRE 组
- 评审周期: 月度
- 更新触发: 每次故障后必须更新对应 Runbook

*Version 1.0 | 最后更新: 2026-05-04*