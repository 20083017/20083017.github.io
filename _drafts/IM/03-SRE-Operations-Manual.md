# SRE 运维手册 v1.0

> 千万并发 IM 系统 - 故障 Runbook、监控大盘、应急预案  
> 关键词：可观测 / 应急响应 / 容量管理 / 故障演练

## 目录
1. [SRE 工作框架](#1-sre-工作框架)
2. [监控大盘](#2-监控大盘)
3. [告警规范](#3-告警规范)
4. [常见故障 Runbook](#4-常见故障-runbook)
5. [应急响应流程](#5-应急响应流程)
6. [容量管理](#6-容量管理)
7. [变更管理](#7-变更管理)
8. [故障演练](#8-故障演练)
9. [应急工具箱](#9-应急工具箱)
10. [复盘与改进](#10-复盘与改进)

---

# 1. SRE 工作框架

## 1.1 SLI/SLO 体系

```
SLI (Service Level Indicator):  实际度量值
SLO (Service Level Objective):  目标值
SLA (Service Level Agreement):  对外承诺
```

### 核心 SLO

| 服务 | SLI | SLO | 错误预算 |
|---|---|---|---|
| 接入可用性 | 连接成功率 | 99.95% | 21min/月 |
| 消息送达率 | 端到端成功率 | 99.99% | 4min/月 |
| 消息延迟 | P99 (同区) | < 500ms | 见监控 |
| 消息丢失率 | 丢失 / 总数 | < 0.001% | - |
| 数据持久性 | 数据丢失率 | 99.999999% | - |

### 错误预算策略

```
本月已用 70% 预算 → 暂停非关键变更
本月已用 100% 预算 → 全面冻结，专注稳定性
连续 3 月达标 → 可以加速创新
```

## 1.2 工程角色与职责

| 角色 | 职责 |
|---|---|
| On-Call SRE | 7×24 应急响应、值班 |
| 服务负责人 | 服务设计、容量规划 |
| Tech Lead | 架构决策、跨服务协调 |
| 安全工程师 | 安全事件、合规审计 |
| 数据库 DBA | 数据层运维、备份恢复 |

---

# 2. 监控大盘

## 2.1 大盘分层

```
┌────────────────────────────────────────┐
│ Tier 1: 业务大盘 (CEO/PM 视角)          │
│ DAU, 消息总量, 收入, 投诉              │
├────────────────────────────────────────┤
│ Tier 2: SLO 大盘 (SRE 主视图)          │
│ SLI 实时值, 错误预算, 趋势             │
├────────────────────────────────────────┤
│ Tier 3: 服务大盘 (每个服务一个)         │
│ QPS, 延迟, 错误率, 资源                │
├────────────────────────────────────────┤
│ Tier 4: 基础设施大盘                    │
│ DB, Redis, Kafka, K8s, 网络            │
└────────────────────────────────────────┘
```

## 2.2 SLO 大盘（核心）

### 关键面板

```
┌──────────────────────────────────────┐
│  消息送达率 (last 1h)                 │
│  ████████████░ 99.991%               │
│  目标: 99.99%   ✅                   │
├──────────────────────────────────────┤
│  消息延迟 P50/P99/P999                │
│  P50:  45ms   P99: 380ms             │
│  P999: 850ms                         │
├──────────────────────────────────────┤
│  错误预算 (本月剩余)                   │
│  ████████████░ 78%                   │
├─────────────────────────────────────��┤
│  按服务错误率                          │
│  Gateway:    0.001%                  │
│  MsgWrite:   0.005%                  │
│  Deliver:    0.012%  ⚠️              │
└──────────────────────────────────────┘
```

## 2.3 Gateway 监控

| 指标 | 单位 | 告警阈值 |
|---|---|---|
| 在线连接数 | 万 | > 80% 容量 |
| 新连接 QPS | qps | > 5K/s |
| 上行消息 QPS | qps | > 50K/实例 |
| 下行投递 QPS | qps | > 100K/实例 |
| TLS 握手 P99 | ms | > 200 |
| 心跳超时率 | % | > 0.1% |
| QUIC 迁移成功率 | % | < 95% |
| CPU 使用率 | % | > 75% |
| 内存使用率 | % | > 80% |
| 网络流入 | Mbps | > 80% 网卡 |

### 关键 PromQL 示例

```promql
# 在线连接数
sum(gateway_active_connections) by (region)

# 消息延迟 P99
histogram_quantile(0.99, 
  sum(rate(msg_e2e_latency_bucket[1m])) by (le, region))

# 错误率
sum(rate(gateway_request_total{code!~"2.."}[1m])) 
/ sum(rate(gateway_request_total[1m]))
```

## 2.4 数据库监控

```
MySQL/TiDB:
  - QPS / TPS
  - 慢查询数
  - 连接数 / 连接池等待
  - 主从延迟 (binlog lag)
  - InnoDB 缓冲池命中率
  - 锁等待 / 死锁
  - 磁盘 IOPS / 使用率

Redis:
  - QPS / 连接数
  - 内存使用率 / 淘汰数
  - 命中率
  - 慢查询
  - 主从延迟
  - cluster slots ok

Kafka:
  - Broker 状态
  - Topic Partition Lag (按 consumer group)
  - ISR shrink
  - Under-Replicated Partitions
  - 磁盘使用率
  - Producer / Consumer QPS
```

## 2.5 业务大盘

```
日活/月活:        DAU/MAU 趋势
消息量:           按 1min/5min/1h 聚合
新增用户:         注册量
群活跃:           活跃群数
异常事件:         风控封禁数 / 客诉数
推送送达:         APNs/FCM 成功率
存储增长:         GB/天
```

## 2.6 大盘工具栈

```
数据采集:    Prometheus + node_exporter + 业务 SDK
日志:        ELK / Loki
追踪:        OpenTelemetry + Jaeger / Tempo
可视化:      Grafana
告警:        AlertManager + 自研告警平台
事件管理:    PagerDuty / 自研
```

---

# 3. 告警规范

## 3.1 告警分级

| 级别 | 含义 | 响应 SLA | 通知方式 |
|---|---|---|---|
| **P0** | 业务大面积不可用 | 5 min | 电话 + 短信 + IM + 邮件 |
| **P1** | 部分功能不可用 | 15 min | 短信 + IM + 邮件 |
| **P2** | 性能下降，未影响 SLO | 1 h | IM + 邮件 |
| **P3** | 趋势异常，需关注 | 4 h | 邮件 |
| **P4** | 信息提醒 | - | 仅记录 |

## 3.2 告警规则模板

```yaml
# Prometheus AlertManager
groups:
- name: im_critical
  rules:
  - alert: MessageDeliveryRateCritical
    expr: |
      (sum(rate(msg_delivery_success[5m])) 
       / sum(rate(msg_delivery_total[5m]))) < 0.999
    for: 2m
    labels:
      severity: P0
      service: deliver
    annotations:
      summary: "消息送达率跌破 99.9%"
      runbook: "https://wiki.../runbook/msg-delivery"
      
  - alert: GatewayConnectionDrop
    expr: |
      delta(gateway_active_connections[1m]) < -10000
    for: 1m
    labels:
      severity: P0
    annotations:
      summary: "Gateway 连接数 1 分钟掉 1 万+"
```

## 3.3 告警规范

```
✅ 必须:
  - 描述清晰（一眼看出是什么问题）
  - 关联 Runbook 链接
  - 有所有者（service owner）
  - 可操作（不是"CPU 60%"这种没用的）

❌ 禁止:
  - 单纯阈值告警没有 for 条件
  - 重复告警（多个规则同一问题）
  - "万一可能"型告警
  - 没人响应的告警
```

## 3.4 告警治理

```
每周告警 review:
  - 误报率 > 30% → 调整规则
  - 噪音告警 → 合并或删除
  - 漏报案例 → 补充规则
  - 响应时长 → 优化 Runbook
```

---

# 4. 常见故障 Runbook

> 每个 Runbook 必须包含：现象 → 影响 → 排查步骤 → 应急处置 → 根因记录

## 4.1 Gateway 大量掉线

### 现象
- `gateway_active_connections` 短时间下跌
- 客户端报"连接断开"
- 重连风暴

### 排查步骤

```
1. 看告警源:
   - 哪些实例掉？(单实例 / 一区域 / 全部)
   
2. 看实例状态:
   kubectl get pods -l app=gateway
   
3. 看实例日志:
   kubectl logs gateway-xxx --tail=100
   关键字: panic, OOM, connection refused
   
4. 看 LB 状态:
   - 健康检查通过率
   - 是否摘除节点
   
5. 看上游依赖:
   - 业务服务是否健康
   - Redis 是否正常
   - DB 是否正常
   
6. 看资源:
   - CPU / 内存 / 网络是否打满
```

### 应急处置

```
情况 A: 单实例 OOM/Panic
  → K8s 自动重启
  → 客户端重连到其他实例
  → 排查代码问题，下次发布修复

情况 B: 一个 AZ 网络故障
  → LB 自动摘除该 AZ
  → DNS 切流到其他 AZ
  → 等待网络恢复

情况 C: 全部实例打满
  → 扩容 (kubectl scale)
  → 临时调高单实例容量
  → 启用排队接入

情况 D: 重连风暴
  → 配置中心下发"接入限流"开关
  → Dispatcher 按比例放量
  → 逐步恢复
```

### 根因记录模板

```markdown
## 故障：Gateway 大量掉线
- 时间：2026-XX-XX HH:MM
- 持续：N 分钟
- 影响：M 用户掉线
- 根因：...
- 改进：...
```

## 4.2 消息延迟突增

### 现象
- 消息延迟 P99 > 1s 持续
- 用户反馈"消息发不出"
- 客户端显示"发送中"长时间

### 排查链路

```
1. 全链路 Trace 找瓶颈:
   client → gateway → msg-write → DB → kafka → deliver
                                ↑
                        看哪一段最慢

2. 常见瓶颈:
   a. DB 慢查询 → 看 slow_log
   b. Redis 卡 → 看 INFO slowlog
   c. Kafka 积压 → 看 consumer lag
   d. 网络抖动 → 看 RTT
   e. GC 长停顿 → 看 GC 日志
```

### 应急处置

```
DB 慢:
  - 临时杀死慢 query: KILL <pid>
  - 切到只读副本
  - 启用查询缓存

Kafka 积压:
  - 扩容 consumer
  - 提高 batch size
  - 临时降级低优 topic

Redis 卡:
  - 关闭非必要查询（如已读回执）
  - 切换到本地缓存
```

## 4.3 消息丢失

### 现象
- 用户反馈"消息没收到"
- `msg_loss_rate` > 0.001%
- 客户端 `client_msg_id` 在服务端查不到

### 排查步骤

```
1. 拿到 client_msg_id 和时间
2. 查 Gateway 日志:
   - 是否到达 Gateway?
3. 查 MsgWrite 日志:
   - 是否写库成功?
4. 查 DB:
   - 是否真的有这条记录?
5. 查 Outbox:
   - 是否进入 outbox?
6. 查 Kafka:
   - 是否被 produce / consume?
7. 查 Deliver/Inbox:
   - 是否成功投递 / 写 inbox?
```

### 常见根因

```
- 客户端没真的发出（网络问题）
- Gateway 限流丢弃但客户端未感知
- DB 写入成功但 Outbox 失败（应用层 bug）
- Kafka 消息被错误删除
- 接收端 inbox 写失败但被吞掉
- 多端同步逻辑 bug
```

### 应急处置

```
小范围:
  - 人工补偿（从其他副本/日志重发）
  
大范围（严重事故）:
  - 立即冻结写入
  - 启动应急通道
  - 从 Kafka / binlog 重放
  - 数据修复后恢复
```

## 4.4 Redis 集群异常

### 现象
- Redis 命中率突降
- Redis 报错激增
- 业务依赖 Redis 的接口超时

### 处置

```
1. 看节点状态:
   redis-cli --cluster check redis-host:port

2. 主从切换:
   - 自动切换是否成功
   - 失败 → 手动 cluster failover

3. 内存压力:
   - INFO memory
   - 清理大 key (SCAN + DEL)
   - 调整 maxmemory-policy

4. 慢查���:
   - SLOWLOG GET 100
   - 找出热 key

5. 网络问题:
   - 看 PING 延迟
   - 看连接数

6. 兜底:
   - 业务降级到本地缓存
   - 关闭非核心 Redis 依赖
```

## 4.5 Kafka 严重 Lag

### 现象
- consumer group lag > 10 万
- 消息延迟激增
- 下游处理不过来

### 处置

```
1. 找出 lag 最严重的 topic 和 partition:
   kafka-consumer-groups.sh --describe \
     --group cg-deliver-normal

2. 分析原因:
   a. 消费者太少 → 扩容
   b. 单条处理慢 → 优化代码 / 加并发
   c. 单 partition 热点 → 加盐 / 分流
   d. 下游卡 → 修下游
   e. Broker 慢 → 看 broker 监控

3. 临时方案:
   - 临时跳过不重要消息（修改 offset）
   - 启用 backup consumer 池
   - 关闭低优 consumer 让位

4. 紧急丢弃:
   - 极端情况: 重置 offset 到 latest
   - 仅适用于"过期就没意义"的消息（如 typing）
```

## 4.6 数据库主从延迟

### 现象
- `Seconds_Behind_Master` > 60s
- 读从库的业务出现"幻读"

### 处置

```
1. 看从库状态:
   SHOW SLAVE STATUS\G

2. 常见原因:
   a. 大事务 → 拆分
   b. 从库 IO 满 → 升级硬件
   c. 网络问题 → 排查
   d. 锁等待 → 杀死阻塞

3. 应急:
   - 业务读切回主库
   - 关闭非核心读
   - 等待追上后切回
```

## 4.7 跨区网络故障

### 现象
- 跨区延迟激增
- MirrorMaker lag
- 跨区调用超时

### 处置

```
1. 确认网络问题:
   - traceroute 跨区
   - 联系网络团队

2. 业务降级:
   - 跨区调用改为最终一致
   - 关闭非必要跨区同步

3. 流量切换:
   - DNS 切到健康区
   - 用户重连本地区
```

## 4.8 Push 大面积失败

### 现象
- APNs/FCM 成功率突降
- 用户反馈"收不到推送"

### 处置

```
1. 看哪个厂商:
   - APNs / FCM / 华为 / 小米
   
2. 厂商状态页:
   - https://developer.apple.com/system-status/

3. 切换通道:
   - 自动切到备用厂商
   - 失败的进入重试队列

4. 异常 token:
   - 批量 token 失效 → 客户端重新注册
```

---

# 5. 应急响应流程

## 5.1 故障响应阶段

```
[发现] → [评估] → [止损] → [修复] → [复盘]
   ↓        ↓        ↓        ↓        ↓
 5 min   5 min   立即    根据 P 级    24h 内
```

## 5.2 故障应急流程图

```
告警触发
   ↓
On-Call SRE 接警
   ↓
1. ��认告警是否真实 (5 min)
   ↓
2. 评估影响范围与级别
   ↓
3. 是否需要升级?
   ├ P0/P1 → 立即拉群（IC + Tech Lead）
   └ P2/P3 → SRE 自行处理
   ↓
4. 按 Runbook 处置
   ↓
5. 沟通透明:
   - 客服群同步状态
   - 状态页更新
   - 内部群通报
   ↓
6. 故障恢复验证
   ↓
7. 复盘 (24-72h 内)
```

## 5.3 战时模式（IC 模式）

```
P0 故障启动战时模式:
  IC (Incident Commander):  统筹指挥
  Ops Lead:                 实际操作
  Comms Lead:               对外沟通
  Scribe:                   记录时间线

会议室或 Zoom 持续在线
所有操作必须在群里通报
```

## 5.4 故障沟通模板

```
【故障通报 #001】2026-XX-XX HH:MM
现象:    XXX 服务 XX% 用户受影响
影响:    无法发送消息 / 部分群组
范围:    华东区域
状态:    定位中 / 处置中 / 已恢复
预计恢复: 30 分钟内
负责人:  @xxx
下次更新: HH:MM
```

## 5.5 客户沟通规范

```
对外发声原则:
  - 不要技术细节（敏感）
  - 透明承认问题
  - 明确恢复时间
  - 致歉

模板:
  "您好，我们检测到部分用户出现 XXX 问题，
   工程师正在紧急处理，预计 XX 分钟内恢复。
   给您带来的不便深表歉意。"
```

---

# 6. 容量管理

## 6.1 容量基线

每月更新一次容量基线：

```yaml
gateway:
  max_capacity:    100K conns/instance
  current_peak:    75K
  utilization:     75%
  next_action:     monitor (>80% 加机器)

mysql_msg:
  max_qps:         8K/instance
  current_peak:    5.5K
  utilization:     69%
  
kafka:
  max_throughput:  500MB/s
  current_peak:    300MB/s
  utilization:     60%
```

## 6.2 容量预测

```python
# 月度容量评估
预计 3 月后:
  DAU 增长: 1.2x
  消息量增长: 1.5x (单用户活跃度提升)
  → 需要扩容: Gateway + MsgWrite + Inbox

行动项:
  - 提前 1 月采购硬件
  - 准备扩容预案
  - 压测验证
```

## 6.3 扩容触发

| 资源 | 黄线 (规划扩) | 橙线 (执行扩) | 红线 (紧急扩) |
|---|---|---|---|
| 连接数 | 70% | 80% | 90% |
| QPS | 70% | 80% | 90% |
| 存储 | 70% | 80% | 95% |
| Kafka 磁盘 | 70% | 80% | 90% |
| Redis 内存 | 70% | 80% | 90% |

## 6.4 压测演练

```
季度压测:
  - 模拟峰值流量 1.5 倍
  - 全链路压测
  - 验证扩容方案
  - 验证降级方案

工具: 自研压测平台 / k6 / locust
```

---

# 7. 变更管理

## 7.1 变更分级

| 级别 | 定义 | 审批 |
|---|---|---|
| L1 | 配置项调整、扩容 | SRE Lead |
| L2 | 服务发布、参数变更 | SRE Lead + Tech Lead |
| L3 | 架构变更、DB 变更 | 架构组 + 总监 |
| L4 | 高风险（迁移、协议） | CTO |

## 7.2 变更窗口

```
推荐时段: 工作日 10:00 - 17:00
禁止时段:
  - 周五下午（防周末爆雷）
  - 节假日前后
  - 大型活动期（如 618、双十一、春节）
  - 上午 9-10 点（高峰）
  - 晚 8-10 点（高峰）

紧急修复: 7×24 (但需 P1 批准)
```

## 7.3 变更流程

```
[提议] → [评审] → [审批] → [灰度] → [全量] → [验证]
              ↓
         风险评估
         回滚预案
         监控就绪
         通知客服
```

## 7.4 变更检查清单

```
[ ] 设计文档已 review
[ ] 测试通过（单元/集成/性能）
[ ] 监控/告警已配置
[ ] 灰度计划明确
[ ] 回滚预案验证
[ ] 业务方已知晓
[ ] 客服话术已准备
[ ] On-Call 已 brief
[ ] 变更窗口合规
```

---

# 8. 故障演练

## 8.1 演练类型

| 类型 | 频率 | 范围 |
|---|---|---|
| Chaos 实验 | 每周 | 单服务 |
| AZ 故障演练 | 每月 | 单 AZ |
| Region 故障演练 | 每季 | 单区域 |
| 全链路故障 | 每半年 | 全系统 |

## 8.2 Chaos 工具

```
- Chaos Mesh / Chaos Monkey
- 注入故障类型:
  * Pod kill
  * 网络分区
  * 网络延迟
  * 磁盘满
  * CPU/内存压力
  * 时钟漂移
  * DNS 失败
```

## 8.3 演练剧本示例

```yaml
演练: Redis 主节点宕机
背景: 验证主从切换 + 业务降级
准备:
  - 选择非高峰时段
  - 通知所有相关方
  - 准备恢复脚本
  
执行:
  T+0:    kill Redis 主进程
  T+5s:   观察 sentinel 切主
  T+30s:  验证业务可用性
  T+1m:   恢复原主，验证回切

验证点:
  - 主从切换 < 30s
  - 业务无明显影响
  - 监控告警准确
  - 业务降级生效

后续:
  - 总结暴露问题
  - 输出改进项
```

## 8.4 GameDay

每半年组织"故障日"：

```
全员参与:
  - 红队: 注入故障
  - 蓝队: 应急响应
  - 观察员: 记录评估

考核:
  - MTTR (修复时间)
  - 决策正确性
  - 沟通有效性
  
奖励:
  - 优秀响应表彰
  - 改进项归档
```

---

# 9. 应急工具箱

## 9.1 一键开关（配置中心）

| 开关 | 用途 |
|---|---|
| `kill.typing` | 关闭"输入中" |
| `kill.read_receipt` | 关闭已读回执 |
| `kill.large_group_fanout` | 大群停止 fanout |
| `kill.search` | 关闭搜索 |
| `kill.history_pull` | 关闭历史拉取 |
| `kill.media_message` | 关闭文件/图片消息 |
| `force.read_only` | 全局只读 |
| `rate.global.qps` | 全局 QPS 上限 |
| `gateway.reject_new` | 拒绝新连接 |

## 9.2 紧急脚本库

```bash
# 杀慢查询
mysql_kill_slow.sh --threshold 5s

# 重启 Gateway 实例
gateway_rolling_restart.sh --batch 5%

# 清理 Redis 大 key
redis_cleanup_bigkey.sh --threshold 1MB

# Kafka 重置 offset
kafka_reset_offset.sh --group cg-xx --to latest

# 强制下线 Pod
k8s_force_evict.sh --pod xxx
```

## 9.3 排查工具

```
日志:        kibana / loki
追踪:        jaeger
监控:        grafana
DB 慢日志:   pt-query-digest
压测:        k6 / locust
抓包:        tcpdump / wireshark
性能:        pprof / perf
```

## 9.4 联系人清单

```yaml
on_call:
  primary: "@sre-oncall"
  secondary: "@sre-backup"

escalation:
  L1: SRE Lead
  L2: Tech Lead
  L3: 架构组
  L4: CTO

vendors:
  cloud: "云厂商支持热线"
  cdn: "CDN 厂商"
  sms: "短信厂商"
  push: "厂商通道"
  
internal:
  pm: "@pm-lead"
  cs: "@customer-service"
  pr: "@public-relations"
```

---

# 10. 复盘与改进

## 10.1 复盘原则

```
✅ 对事不对人
✅ 寻找系统性问题
✅ 改进可落地
✅ 时间线清晰

❌ 追责
❌ 推卸
❌ 流于形式
```

## 10.2 复盘文档模板

```markdown
# 故障复盘：YYYY-MM-DD-XX

## 一、事件概览
- 标题: 
- 影响时间: 
- 影响范围: 
- 影响用户数: 
- 故障级别: P0/P1/P2

## 二、时间线
- HH:MM 现象出现
- HH:MM 告警触发
- HH:MM 接警响应
- HH:MM 定位根因
- HH:MM 处置完成
- HH:MM 业务恢复
- HH:MM 完全恢复

## 三、根因分析（5 Why）
直接原因: 
- 第二层: 
- 第三层: 
- 第四层: 
- 根本原因: 

## 四、做得好的
- ...
- ...

## 五、需改进的
- 监控盲区: 
- 响应延迟: 
- 沟通失误: 
- 工具缺失: 

## 六、改进项
| 项 | 负责人 | 截止 | 状态 |
|---|---|---|---|
| 加监控 XX | @xxx | DD | 进行中 |
| 优化告警 | @xxx | DD | 待开始 |

## 七、其他
- 需要的资源
- 风险预估
```

## 10.3 改进项跟踪

```
所有改进项进入 Jira 跟踪
每�� review 进度
逾期未完成 → 升级到 Tech Lead
重大改进 → 季度 review

完成率目标: 80%/月
```

## 10.4 知识沉淀

```
故障 Runbook 必须更新:
  - 新故障 → 新 Runbook
  - 已有 Runbook 不准确 → 修订
  - 季度 review 所有 Runbook

知识库结构:
  /runbook/
    /gateway/
    /msg-write/
    /database/
    /redis/
    /kafka/
    /...
  /postmortem/
    /2026/
      /YYYY-MM-DD-incident-name.md
```

---

# 附录：值班与排班

## A. 值班规范

```
值班周期: 1 周
轮换: 周一 10:00 交接
覆盖: 7×24
最大连续: 2 周

要求:
  - 30 min 响应（电话）
  - 1h 内到达办公室或远程接入
  - 处置期间专注故障
  - 交接 brief 充分
```

## B. 值班准备

```
[ ] 确认应急联系人通畅
[ ] 测试 VPN / 监控访问
[ ] 准备值班机
[ ] 阅读最近 Runbook 更新
[ ] 了解近期变更
[ ] 与上一班交接
```

## C. 值班补贴

略（按公司政策）

---

**文档结束**

*Version 1.0 | SRE 运维手册*