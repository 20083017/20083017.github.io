# IM 系统 SRE 运维手册 v1.0

> 适用：值班 SRE / On-Call 工程师  
> 目标：5 分钟定位问题，30 分钟恢复服务

---

## 目录

1. 监控大盘
2. 告警分级与响应
3. 常见故障 Runbook
4. 应急预案
5. 容量管理
6. 变更管理
7. 故障复盘流程

---

# 1. 监控大盘

## 1.1 大盘分层

```
L0 总览大盘:        系统健康概览，1 张图看全貌
L1 业务大盘:        消息/连接/用户核心指标
L2 服务大盘:        每个微服务一张
L3 中间件大盘:      Redis/Kafka/MySQL/ES
L4 基础设施大盘:    主机/网络/K8s
```

## 1.2 L0 总览大盘内容

```
顶部红绿灯:
  ┌─────┬─────┬─────┬─────┬─────┐
  │接入  │消息  │推送  │存储  │风控  │
  │ 🟢  │ 🟢  │ 🟡  │ 🟢  │ 🟢  │
  └─────┴─────┴─────┴─────┴─────┘

核心指标 (实时):
  - 在线用户数
  - 消息 QPS（写入/投递）
  - 端到端延迟 P99
  - 错误率
  - SLA 余额（本月）

异常区域:
  - 当前进行中的告警
  - 最近 1 小时变更
```

## 1.3 L1 业务大盘

```
连接:
  - 实时连接数（按区域/网关分组）
  - 建连速率
  - 连接失败率
  - QUIC 迁移成功率

消息:
  - 发送 QPS（按 msg_type）
  - 入库延迟分布
  - Outbox 堆积
  - Kafka lag (按 topic / partition)
  - 投递成功率
  - 撤回率

推送:
  - 推送 QPS
  - 各厂商成功率（APNs/FCM/华为/小米/...）
  - 推送时延
  - DLQ 堆积

未读:
  - 未读 cursor 更新 QPS
  - 计算延迟
```

## 1.4 大盘工具

- Grafana + Prometheus（指标）
- Kibana（日志）
- Jaeger / SkyWalking（trace）
- 自研业务大盘（核心 KPI）

## 1.5 关键 SLI

| SLI | 计算 | 目标 |
|---|---|---|
| 接入可用性 | 1 - (失败建连/总建连) | > 99.9% |
| 消息成功率 | 成功入库/总请求 | > 99.99% |
| 投递成功率 | 投递成功/已入库 | > 99.95% |
| 端到端延迟 P99 | A 发送到 B 收到 | < 500ms |
| 推送时延 P99 | 入库到 push | < 5s |

---

# 2. 告警分级与响应

## 2.1 告警分级

| 级别 | 含义 | 响应时间 | 通知方式 |
|---|---|---|---|
| **P0** | 核心服务不可用，影响 > 10% 用户 | 5 分钟 | 电话 + IM + 邮件 |
| **P1** | 重要服务异常，影响部分用户 | 15 分钟 | IM + 邮件 |
| **P2** | 服务降级，但可用 | 1 小时 | IM |
| **P3** | 异常但不紧急 | 4 小时 | 邮件 |

## 2.2 P0 告警示例

```
- 接入成功率 < 99% (连续 3 分钟)
- 消息丢失率 > 0.01%
- 主集群整体不可用
- 数据库主从延迟 > 60s
- Kafka 集群不可写
- Redis 集群不可用
```

## 2.3 告警响应流程

```
告警触发
  ▼
On-Call 接收 (5min 内 ack)
  ▼
初步定位 (查大盘 / 日志)
  ▼
是否需要升级？
  ├─ 是 → 拉群（业务/SRE Lead）
  └─ 否 → 处理
  ▼
执行 Runbook
  ▼
确认恢复
  ▼
解除告警 + 简单总结
  ▼
24h 内输出 RCA
```

## 2.4 告警值班

```
轮值: 7×24，每班 12 小时
人数: 主备 2 人
工具: PagerDuty / OpsGenie / 自研
要求:
  - Ack 时间 < 5 min
  - 处理时间 < SLA
  - 每月轮值表提前发布
```

---

# 3. 常见故障 Runbook

## 3.1 [P0] 接入大量失败

### 症状
- 连接成功率骤降
- 客户端反馈连不上
- Gateway 错误日志增多

### 排查步骤

```
[1] 查 LB 健康
    - LB 健康检查通过��
    - LB CPU/内存
    
[2] 查 Gateway
    - 实例数量是否正常
    - CPU/内存/连接数
    - 错误日志关键字: "auth_failed", "tls_failed"
    
[3] 查依赖
    - auth-service 是否健康
    - presence shard 是否健康
    
[4] 查网络
    - LB 到 Gateway 网络
    - DNS 解析
```

### 处置动作

```
快速恢复:
  - LB 故障 → 切换到备用 LB
  - Gateway 实例不足 → HPA 扩容
  - auth 慢 → 临时延长 auth 缓存 TTL
  - 全部失败 → DNS 切到备用集群

根因排查:
  - 看变更窗口是否有发布
  - 看依赖服务变更
  - 看证书是否过期
```

### 升级条件
- 5 分钟内未止血
- 影响 > 30% 用户

---

## 3.2 [P0] 消息延迟增加

### 症状
- 端到端 P99 > 1s
- 用户反馈"消息晚到"

### 排查步骤

```
[1] 定位慢在哪一段
    - 客户端 → Gateway: 网络问题
    - Gateway → MsgWrite: 上游慢
    - MsgWrite → DB: DB 问题
    - Outbox → Kafka: Kafka 问题
    - Kafka → Deliver: Consumer lag
    - Deliver → Gateway: 状态查询慢

[2] 看 Kafka lag
    kafka-consumer-groups.sh --describe --group cg-deliver
    
[3] 看 DB 慢查询
    SHOW PROCESSLIST;
    SELECT * FROM information_schema.innodb_trx;
    
[4] 看 Redis 慢日志
    SLOWLOG GET 10
```

### 处置动作

```
Kafka lag:
  - 扩 Consumer 实例
  - 提高 fetch.max.bytes
  - 检查是否有大消息卡住

DB 慢:
  - 杀长查询: KILL <id>
  - 切只读到从库
  - 临时增加连接数

Redis 慢:
  - 找 hot key
  - 临时关闭非关键写入
  - 主从切换
```

---

## 3.3 [P0] Kafka 集群异常

### 症状
- Producer 写入失败
- Outbox 堆积
- ISR 收缩

### 排查步骤

```
[1] kafka-topics --describe
    - 看每个 topic 的 ISR
    - 是否有 Under-Replicated

[2] kafka-broker-api-versions
    - 节点是否都在线

[3] 磁盘使用率
    - df -h /kafka-data
    
[4] JVM 堆
    - jstat / GC log
```

### 处置动作

```
Broker 挂:
  - 重启 Broker
  - 检查日志: log.recovery
  
ISR 不全:
  - 检查网络
  - 检查磁盘 IO
  
磁盘满:
  - 临时缩短 retention
  - 删除老 topic
  - 紧急扩容磁盘

完全不可用:
  - 启用 Kafka 备集群
  - Producer 切到备集群
  - Outbox 暂存等恢复
```

---

## 3.4 [P0] Redis 集群异常

### 症状
- 缓存 miss 率飙升
- 业务延迟增加
- Redis 连接异常

### 排查步骤

```
[1] redis-cli cluster info
    - cluster_state: ok?
    
[2] redis-cli cluster nodes
    - 节点状态

[3] 内存使用
    INFO memory
    used_memory / maxmemory
    
[4] 慢日志
    SLOWLOG GET 20
```

### 处置动作

```
单节点挂:
  - 等自动 failover (10~30s)
  - 不行手动 failover: CLUSTER FAILOVER

集群失联:
  - 业务降级到 DB 兜底
  - 限流降低 QPS
  - 分批重启节点

内存满:
  - 检查 maxmemory-policy
  - 紧急清理大 key
  - 临时缩短 TTL
```

---

## 3.5 [P1] DB 主从延迟

### 症状
- 从库 Seconds_Behind_Master > 60
- 读从库的业务读到旧数据

### 排查步骤

```
[1] SHOW SLAVE STATUS\G
    - Seconds_Behind_Master
    - Last_Error
    - Slave_SQL_Running_State

[2] 主库写入压力
    - QPS / IOPS
    
[3] 从库 IO
    - iostat
```

### 处置动作

```
延迟增长中:
  - 临时切读到主库
  - 减少主库写入压力
  
单从库慢:
  - 重启该从库 IO 线程
  - 移除该从库出读集群
  
全部慢:
  - 限制主库写入
  - 升级从库硬件
```

---

## 3.6 [P1] 推送大量失败

### 症状
- APNs/FCM 成功率下降
- 用户收不到通知

### 排查步骤

```
[1] 查厂商状态页
    - APNs: developer.apple.com/system-status/
    - FCM: status.firebase.google.com/

[2] 查推送服务日志
    - 错误码分布
    - 是否证书过期

[3] 查推送 DLQ
    kafka-consumer-groups --describe msg.push.high.dlq
```

### 处置动作

```
单厂商挂:
  - 切到备用通道
  - 暂存等恢复

证书过期:
  - 紧急更新证书
  - 重启推送服务

DLQ 大量堆积:
  - 启动 DLQ 消费器
  - 降低重试间隔
```

---

## 3.7 [P1] 单网关失联

### 症状
- 该 Gateway 上的用户掉线
- 监控显示该实例不可达

### 处置

```
1. LB 摘除该实例
2. 等待 K8s 重启 Pod
3. 用户自动重连到其他网关
4. 30s 后状态自愈

如果是宿主机故障:
1. K8s 调度到其他节点
2. 检查节点健康
3. 上报硬件故障
```

---

## 3.8 [P0] 整集群故障

### 症状
- 一整个区域不可用
- 多个核心服务同时告警

### 处置（区域切流）

```
Step 1: 确认范围
  - 单 AZ 还是整 region？
  - 网络问题还是机房断电？

Step 2: 启动切流
  - GSLB 切流量到其他 region
  - 通知客户端重连
  - 数据库 standby 提升
  
Step 3: 通信
  - 内部通报
  - 客服通报（如必要）
  
Step 4: 持续观察
  - 其他 region 是否扛住
  - 是否需要扩容

Step 5: 故障 region 恢复
  - 等待故障消除
  - 灰度引入流量
  - 全量恢复
```

---

## 3.9 [P0] 消息大量丢失

### 症状
- 用户反馈"消息没收到"
- 对账发现差异

### 排查步骤

```
[1] 定位丢失位置
    - 客户端发出但服务端无: 网络或 Gateway
    - 服务端入库但 Kafka 无: Outbox 未投递
    - Kafka 有但 Consumer 没消费: Consumer lag/异常
    - Consumer 处理但用户没收到: 投递失败

[2] 看 Outbox 堆积
    SELECT count(*) FROM outbox_event WHERE status=0
    
[3] 看 DLQ
[4] 看错误日志
```

### 处置动作

```
Outbox 卡住:
  - 重启 Outbox Worker
  - 手动触发处理

Consumer 异常:
  - 重启 Consumer
  - 从指定 offset 重消费

数据真丢失:
  - 启动补偿任务
  - 通过 binlog 重放
  - 用户致歉/补偿
```

---

# 4. 应急预案

## 4.1 战时模式

P0 级故障启动战时模式：

```
1. 拉作战群（IM 群 + 视频会议）
2. 指定 IC（Incident Commander）
3. 角色分工:
   - IC: 决策与协调
   - SRE: 操作系统
   - 业务: 评估影响
   - 沟通: 内外部通报
   
4. 时间线记录
5. 决策记录
```

## 4.2 一键降级开关

```yaml
emergency_switches:
  kill_typing_indicator: false       # 关闭"正在输入"
  kill_read_receipt: false           # 关闭已读回执
  kill_search: false                 # 关闭消息搜索
  kill_history_load: false           # 关闭历史漫游
  kill_large_group_fanout: false     # 大群只读扩散
  
  rate_limit_global_qps: 1000000     # 全局 QPS 上限
  rate_limit_user_msg: 200           # 用户消息频率
  
  force_read_only: false             # 全站只读
  reject_new_login: false            # 拒绝新登录
```

通过配置中心下发，秒级生效。

## 4.3 灾难恢复

### 数据中心丢失
```
RTO: 30 分钟
RPO: 5 分钟

步骤:
1. GSLB 切流
2. 备 region DB standby 提升为主
3. 启动备 Kafka 集群
4. Redis 重建（可接受丢失短期数据）
5. 业务验证
6. 客户端重连
```

### 数据库误删除
```
1. 立即停业务（避免覆盖）
2. 评估影响范围
3. 选择恢复点
4. 全量备份恢复 + binlog 增量
5. 数据对比
6. 切回业务
```

## 4.4 演练机制

```
周期: 每季度一次混沌工程演练

演练类型:
  - 网关故障
  - DB 主切换
  - Kafka broker 挂
  - 区域切流
  - 全链路压测

工具: ChaosMesh / Chaos Monkey
```

---

# 5. 容量管理

## 5.1 容量监控

```
水位告警:
  - 黄: 70%
  - 橙: 85%
  - 红: 95%

监控对象:
  - Gateway 连接数
  - DB 存储 / QPS
  - Redis 内存
  - Kafka 磁盘 / lag
  - 带宽
```

## 5.2 容量预测

```
模型: 基于历史增长率 (LSTM / Prophet)
预测周期: 6 个月
输出:
  - 何时达到 70%
  - 何时需要扩容
  - 扩容多少
```

## 5.3 自动扩缩容

```yaml
HPA (K8s):
  Gateway:
    minReplicas: 20
    maxReplicas: 200
    metrics:
      - cpu: 60%
      - memory: 70%
      - custom: connections_per_pod < 80000
  
  MsgWrite:
    minReplicas: 10
    maxReplicas: 100
    metrics:
      - cpu: 60%
      - kafka_lag: 1000
```

## 5.4 季节性扩容

```
春节: 提前 1 周扩容到 3x
双十一: 提前 1 周扩容到 2x
重大事件: 临时扩容
```

---

# 6. 变更管理

## 6.1 变更分类

| 类型 | 审批 | 窗口 |
|---|---|---|
| 紧急修复 | On-Call 决策 | 任何时间 |
| 普通发布 | 主管审批 | 工作日 10-17 |
| 重大变更 | 架构评审 | 周二/周三 |
| 数据库变更 | DBA 审批 | 业务低峰 |

## 6.2 变更流程

```
1. 提交变更单 (CR)
   - 描述
   - 影响范围
   - 测试结果
   - 回滚方案
   - 风险评估

2. 评审

3. 灰度执行
   - 1% → 10% → 50% → 100%

4. 持续观察

5. 关闭变更单
```

## 6.3 变更窗口禁令

```
禁止变更时段:
  - 周五下午
  - 节假日
  - 大型活动期
  - 灰度未结束的相邻变更
```

---

# 7. 故障复盘流程

## 7.1 复盘原则

```
1. 不追责，找根因
2. 事实优先
3. 改进可落地
4. 时间内完成（24h 内初稿，1 周内定稿）
```

## 7.2 复盘模板

```markdown
# 故障复盘：[标题]

## 基本信息
- 时间：YYYY-MM-DD HH:MM ~ HH:MM
- 影响：影响用户数 / 业务损失
- 级别：P0 / P1 / P2
- 主要负责：XX

## 时间线
- HH:MM 告警触发
- HH:MM On-Call 响应
- HH:MM 定位为 XX
- HH:MM 执行 XX 操作
- HH:MM 服务恢复

## 根本原因
- 直接原因：
- 根本原因：
- 为什么 1：
- 为什么 2：
- 为什么 3：

## 影响分析
- 受影响用户：
- 受影响功能：
- 业务损失：

## 处置评估
- 做得好的：
- 不足之处：

## 改进项 (Action Items)
| 改进 | 负责人 | 截止 | 状态 |
|---|---|---|---|
| XX | XX | YYYY-MM-DD | 进行中 |

## 经验教训
```

## 7.3 改进���跟踪

```
所有 Action Item 必须有 owner + deadline
每周进度 review
未按期 → 升级
```

---

# 附录：常用命令速查

## A.1 K8s

```bash
# 查 Pod 状态
kubectl get pods -n im -l app=gateway

# 查 Pod 日志
kubectl logs -f -n im gateway-xxx

# 进入 Pod
kubectl exec -it gateway-xxx -- bash

# 重启 Deployment
kubectl rollout restart deployment/gateway -n im

# 扩容
kubectl scale deployment/gateway --replicas=50 -n im
```

## A.2 Kafka

```bash
# 列 topic
kafka-topics --bootstrap-server kafka:9092 --list

# 描述 topic
kafka-topics --bootstrap-server kafka:9092 --describe --topic msg.fanout.normal

# 查 consumer lag
kafka-consumer-groups --bootstrap-server kafka:9092 --describe --group cg-deliver-normal

# 重置 offset
kafka-consumer-groups --bootstrap-server kafka:9092 --group cg-xxx --reset-offsets --to-earliest --execute --topic xxx
```

## A.3 Redis

```bash
# 集群信息
redis-cli -h xxx cluster info
redis-cli -h xxx cluster nodes

# 慢日志
redis-cli -h xxx SLOWLOG GET 20

# 监控
redis-cli -h xxx --stat

# 大 key 扫描
redis-cli -h xxx --bigkeys
```

## A.4 MySQL

```sql
-- 当前会话
SHOW PROCESSLIST;

-- 慢查询
SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 20;

-- 主从状态
SHOW SLAVE STATUS\G

-- innodb 状态
SHOW ENGINE INNODB STATUS\G

-- 杀连接
KILL <id>;
```

---

**文档结束** | Version 1.0