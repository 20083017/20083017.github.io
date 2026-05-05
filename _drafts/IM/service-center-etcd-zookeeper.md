# etcd + ZooKeeper 服务中心设计详解

> 适用：IM、大规模分布式服务注册发现、配置中心、选主、分布式锁、任务调度  
> 目标：高可用、强一致、大规模支撑 IM 或微服务架构  
> 最近更新：2026-05

---

## 1. 背景与选型

在 IM/微服务/分布式大促系统领域，常见的服务中心选型包括：

- **ZooKeeper**（Apache）：老一代分布式一致性协调中心，Paxos→ZAB协议，CP，写放大，连接压力大。
- **etcd**（CoreOS/Cloud Native）：后起之秀，Raft算法，云原生生态，性能好，API简洁，普及率高。
- **Consul**、**Eureka** 等也常见但此处不重点分析。

### 为什么常同时存在？

- **etcd 用于云原生/配置中心/服务发现/K8s 生态/高并发短连接**  
- **ZooKeeper 用于老项目、任务调度、Kafka/HBase/Hadoop/Solr 依赖组件、分布式锁、强一致小数据协调**

大中型公司常见“etcd + ZK 双中心”模式：  
- 新增业��全部用 etcd，保留 ZK 作为兼容与部分强一致订阅需求、“重量级选主”组件。  
- 架构宜优先 etcd，逐步将ZK淘汰只保留Kafka/HBase系统本身可靠性一环，避免新业务依赖。

---

## 2. 场景与能力矩阵

| 能力/场景      | ZooKeeper | etcd    | 推荐实践                |
|----------------|-----------|---------|--------------------------|
| 服务注册发现   | ✔️         | ✔️       | etcd 优先               |
| 配置中心        | ✔️         | ✔️       | etcd 优先               |
| 选主（分布式锁）| ✔️         | 单一锁弱 | ZK强一致，etcd 3.3+带lease支持 |
| 配置推送/订阅   | ✔️         | ✔️       | etcd v3 watch机制优越    |
| 节点监控        | ✔️         | ✔️       | etcd性能更优             |
| 队列/Barrier    | ✔️         | ×       | 只ZK支持                 |
| 复杂树结构      | ✔️         | Key-Value| ZK层级强，etcd前缀遍历  |

---

## 3. 架构部署

### etcd 集群设计

- **奇数节点**，推荐 3、5、7
- 部署区域策略：单region用3-5节点，跨region需网络稳定
- 节点自选ID，静态peer配置
- 内网通讯加密需配置证书
- 生产只读节点请用 etcd proxy，不建议直接连主集群

### ZooKeeper 集群设计

- **奇数节点**，3/5/7（有failover）；ZAB算法要求
- 建议单机单实例，不混布
- 服务发现注册各自路径隔离（如 /im /kafka /hbase）
- 限制单Client并发Session数，短连接谨慎
- 自动快照清理
- 跨IDC需关注Leader选举压制

---

## 4. 服务注册与发现

### etcd 实现（IM常用）

1. 服务自注册

```bash
# 注册key
PUT /v3/kv/put
{
  "key": base64("services/gateway/10.0.1.2:8181"),
  "value": base64("{\"weight\":100,\"zone\":\"east\"}"),
  "lease": 1234
}
```
带 lease，注册即有自动过期。协同健康检查，微服务失活 key 自动丢。

2. 服务发现

```bash
# 获取所有gateway服务
GET /v3/kv/range
{
  "key": base64("services/gateway/"),
  "range_end": base64("services/gateway0")
}
```
客户端可以 watch key前缀，自动感知上下线。

### ZK 实现（兼容遗留/分布式锁）

1. 服务注册

利用临时节点，服务下线自动消失。

```
/services/gateway
    /10.0.1.2:8181 (ephemeral)
    /10.0.1.3:8181 (ephemeral)
```
2. 发现和监听

客户端 watch /services/gateway 下的children，节点变化收到通知。

---

## 5. 配置中心设计

### etcd 方式

- key 模型采用前缀树，比如 `/config/im/gateway.yaml`，按业务/环境/集群/功能多级分层
- 支持热更新（watcher 监听配置key变化，自动推送到业务内存或重加载）
- 配置滚动升级可用短ttl+多版本key，客户端watch新key切流

### ZK 方式（次选）

- key分层如 `/config/im/gateway`
- 服务监听节点值变化（getData/watch）
- 写大文件用 get/setChildren 拆key

推荐新业务一律 etcd 配置，保证K8s原生兼容。

---

## 6. 分布式锁与选主

### etcd 分布式锁实现

- v3 Lease + CAS
- 典型 Go 代码如下（简化）：

```go
// 加锁
lease, _ := client.Grant(context, 20) // 20s租期
// 原子 put 如果不存在
txn := client.Txn(context).
    If(Compare(CreateRevision(lockKey), "=", 0)).
    Then(OpPut(lockKey, ownerID, WithLease(lease.ID)))
if txn.Commit().Succeeded {
    // 获得锁
}
// 失败重试 or wait
```
- 续约靠 Lease keepalive

### ZK 分布式锁/选主实现

- 临时有序节点 `/lock/im/
    /lock/im/lock-00000001 (ephemeral, clientA)
    /lock/im/lock-00000002 (ephemeral, clientB)
`
- 谁序号小谁为leader，其余client watch上一个节点
- 选主算法最成熟可靠（kafka、hbase等核心依赖）

IM场景一般推荐 etcd简化弱锁/leader，ZK留给系统核心状态协调。

---

## 7. 配置、服务中心高可用与运维

### etcd 高可用经验

- 严格**奇数节点**，部署在不同物理/虚拟机
- 集群不要单点过大（3/5/7，9节点起raft性能剧降）
- 写压力大时可加只读proxy节点服务读流量
- ETCD Quorum丢一半-1还能工作，网络分区则需主节点选举
- 定期快照备份（避免数据丢失）

### ZooKeeper 高可用经验

- 强依赖本地磁盘IO和网络（磁盘慢会影响整个集群）
- 生产部署应有3节点+，且主分布于不同机柜
- 运维监控四大值：Session数，节点数，队列长度，磁盘使用
- 配置自动快照清理，防止日志炸满盘

---

## 8. Watch/订阅机制

|      | etcd           | ZooKeeper      |
|------|----------------|---------------|
| 订阅单位 | Key/Prefix     | Node+children |
| 性能   | 优，push型      | 适中，触发频繁时延迟 |
| 断线重连| 自动续watch    | 需重建watch   |
| 响应方式| gRPC 推流       | 长连回复一次  |

IM注册中心推荐分组/服务做前缀watch，配置中心单点/全量watch。

---

## 9. 典型API与最佳实践

### etcd API关键用法

- 服务注册：`PUT` + `lease`
- 服务发现：`GET` + `watch`前缀
- 配置下发：`watch`配置key
- 锁/选主：`Txn` + `lease`/`revoke`
- 客户端推荐：官方Go/Java/Python客户端，gRPC native高性能

### ZooKeeper API核心用法

- 创建临时节点：`create -e`
- 子节点监听：`getChildren`+`watch`
- 数据节点监听：`getData`+`watch`
- 多client推荐Curator（Netflix Java库）：自动重连、leader选举、分布式锁

---

## 10. 监控与可观测

### etcd 监控

- `etcdctl endpoint status --write-out=table`
- `/metrics` Prometheus
- 关注指标：leader changes、applied index、db size、raft term、watchers
- 告警：leader频繁切换，commit超时，落后节点，磁盘用量，丢失quorum

### ZooKeeper 监控

- `mntr`四字命令
- `srvr`命令
- `zkruok`探活
- 关注指标：zk_avg_latency，zk_packets_received，zk_outstanding_requests，zk_watch_count
- 告警：follower落后、磁盘空间临界、session耗尽

---

## 11. 服务治理典型难题与实践

### 11.1 雪崩/穿透问题

集中注销/重连接/瞬时压力高峰需限流、指数退避

### 11.2 大量watch

分批订阅、合理分层、不能拿ZK/etcd当“分布式事件总线”用！

### 11.3 分布式锁过期

保证租约续签可靠，否则锁提前失效会造成脏写  
两步锁写：Leader先拿锁再业务，“持有锁即责任”

### 11.4 数据过大

- etcd每value最大1MB
- ZooKeeper每node最大1MB，节点数不宜过多

### 11.5 配置切换一致性

- 多Key批量更新用revision，etcd支持事务性变更，ZK推荐分批安插版本戳。

---

## 12. 线上案例推荐规范配置

### etcd 推荐关键配置

```ini
[member]
name: "etcd-1"
data-dir: "/data/etcd"
listen-peer-urls: "http://0.0.0.0:2380"
listen-client-urls: "http://0.0.0.0:2379"
advertise-client-urls: "http://10.0.1.1:2379"
initial-advertise-peer-urls: "http://10.0.1.1:2380"
initial-cluster: "etcd-1=http://10.0.1.1:2380,etcd-2=http://10.0.1.2:2380,etcd-3=http://10.0.1.3:2380"
auto-compaction-retention: 24
quota-backend-bytes: 8589934592    # 8GB
max-txn-ops: 128
max-request-bytes: 1572864
```

### ZooKeeper 推荐关键配置

```ini
tickTime=2000
initLimit=10
syncLimit=5
clientPort=2181
maxClientCnxns=500
autopurge.snapRetainCount=3
autopurge.purgeInterval=1
dataDir=/data/zk
server.1=10.0.1.1:2888:3888
server.2=10.0.1.2:2888:3888
server.3=10.0.1.3:2888:3888
```

---

## 13. 运维与故障恢复

**etcd**

- 三节点允许 1 节��挂，单节点写即刻告警  
- 日志快照每 30min/1h  
- 备份 & 回滚训练  
- 定期升级至社区 LTS版，修复安全漏洞

**ZooKeeper**

- 自动快照与日志清理，防止磁盘炸满  
- leader升降监控  
- 更换leader不会丢数据但会有连接抖动

---

## 14. 总结（IM & 云原生最佳实践）

- **新业务首选 etcd，老业务兼容ZK**，逐步用etcd实现“配置中心+注册中心+分布式锁+选主”。
- **服务注册发现、配置推送、选主、分布式锁**均推荐etcd，ZK仅对极低延迟、复杂树协同任务/Barrier场景下保留。
- **强一致+单点支撑建议3/5节点，避免超大集群**，并和应用共用连接池，限流watch规模。
- **结合K8s生态**，etcd一统天下（云原生最佳实践），ZK为大数据遗留系统兜底。
- **定期归档watch/leader信息、自动告警**，问题早发现早恢复。

如需深入List-实现细节、Client代码模板、云原生(K8s/operator)无痛集成、分布式锁完整代码、灰度切换方案、请继续指定详细方向。

---

**文档结束** | Version 1.0