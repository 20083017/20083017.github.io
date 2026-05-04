# 全链路压测方案 v1.0

> 适用：千万 DAU IM 系统的容量评估、性能验证、故障演练  
> 目标：在生产环境模拟真实流量，发现瓶颈、验证 SLA、保障大促/活动稳定

---

## 目录

1. 压测目标与原则
2. 压测分类
3. 压测工具选型
4. 数据准备
5. 流量模型构建
6. 流量回放
7. 全链路改造（影子库/影子链路）
8. 执行流程
9. 性能瓶颈定位
10. 压测报告
11. 大促压测实战
12. 风险控制与回滚
13. 常用脚本与命令

---

# 1. 压测目标与原则

## 1.1 压测目标

压测不是为了“把系统打挂”，而是为了回答下面这些问题：

1. **系统当前容量上限是多少**
2. **在哪一层先成为瓶颈**
3. **瓶颈出现前的预警指标是什么**
4. **扩容后收益是否线性**
5. **在目标峰值下 SLA 能否达标**
6. **故障场景下是否还能维持核心服务**

## 1.2 压测核心指标

| 维度 | 目标 |
|---|---|
| 接入建连成功率 | > 99.9% |
| 消息发送成功率 | > 99.99% |
| 同地域消息延迟 P99 | < 500ms |
| 跨地域消息延迟 P99 | < 1s |
| Kafka lag | 可控，不持续增长 |
| Redis 查询延迟 P99 | < 5ms |
| DB 写入延迟 P99 | < 20ms |
| Push 延迟 P99 | < 5s |

## 1.3 压测原则

### 原则 1：逐层压，不要一上来全链路最大流量
先单模块，再联调，再全链路。

### 原则 2：真实流量模型比纯 QPS 更重要
IM 不是简单 API 压测，必须模拟：

- 长连接
- 心跳
- 收发比
- 单聊/群聊比例
- 消息大小分布
- 在线/离线用户比例
- 多端在线比例

### 原则 3：能在预发完成的，不要直接上生产
生产压测只做最终验证，不做首次发现问题。

### 原则 4：生产压测必须走影子链路或严格隔离
避免污染真实用户数据。

---

# 2. 压测分类

## 2.1 按目标分类

### 1）基准压测（Benchmark）
测单服务在固定资源下的基线能力。

例如：

- 单 Gateway 最大连接数
- 单 MsgWrite 的写入能力
- 单 Redis 节点 QPS
- 单 Kafka partition 吞吐

### 2）容量压测（Capacity Test）
逐步加流量，找系统容量拐点。

### 3）稳定性压测（Soak Test）
长时间（6h / 12h / 24h）持续跑，观察：

- 内存泄漏
- 线程堆积
- Kafka lag 累积
- 连接漂移
- GC 异常

### 4）突刺压测（Spike Test）
模拟热点事件或瞬时洪峰。

例如：

- 万人群短时间刷屏
- 推送流量暴涨
- 大 V 发消息后 fanout 激增
- 服务恢复后重连风暴

### 5）故障压测（Chaos Test）
在压测过程中主动注入故障：

- 杀 Gateway
- 切 Redis 主从
- Kafka broker 下线
- DB 主切换
- 网络抖动/丢包

---

## 2.2 按链路分类

### A. 接入层压测
验证：

- 建连速度
- 长连接数量
- 心跳稳定性
- QUIC/WS 切换能力

### B. 消息主链路压测
验证：

- 消息发送
- 落库
- outbox
- Kafka
- deliver
- 客户端接收

### C. 离线链路压测
验证：

- inbox 写入
- 离线同步
- push 发送
- 冷启动拉消息

### D. 管理/辅助链路压测
验证：

- 在线状态
- 已读回执
- @消息
- 撤回/编辑
- 群成员变更

---

# 3. 压测工具选型

## 3.1 工具总览

| 场景 | 推荐工具 | 说明 |
|---|---|---|
| HTTP API | k6 / wrk2 / JMeter | 简单 REST 压测 |
| WebSocket 长连接 | k6 ws / Tsung / 自研 | 必须支持长连接与消息交互 |
| QUIC 压测 | 自研 / quic-go bench / h2load(h3) | QUIC 现成工具较少 |
| Kafka 压测 | kafkacat / kafka-producer-perf-test | topic 吞吐 |
| Redis 压测 | redis-benchmark / memtier_benchmark | cache QPS |
| MySQL 压测 | sysbench / go-sql-bench | 数据库读写 |
| 全链路压测 | 自研压测平台 | IM 最终还是要自研 |

## 3.2 为什么 IM 需要自研压测平台

因为 IM 压测有这些特殊性：

- 长连接保持
- 双向消息交互
- 心跳
- 登录态
- 连接断开重连
- 订阅状态变化
- 收件端真实消费
- 推拉结合
- 多种消息类型混合

这些用 JMeter/k6 只能覆盖一部分，**最终必须自研一个 IM 压测客户端集群**。

---

## 3.3 自研压测平台模块

```
┌──────────────────────────────────────────┐
│ 压测控制台                                │
│ - 配置场景                               │
│ - 设置用户规模                            │
│ - 设置消息模型                            │
│ - 实时观测                                │
└─────────────┬────────────────────────────┘
              │
              ▼
┌───────────────���──────────────────────────┐
│ 压测调度器                                │
│ - 任务下发                               │
│ - Agent 编排                              │
│ - 限流控制                                │
└─────────────┬────────────────────────────┘
              │
   ┌──────────┼──────────┐
   ▼          ▼          ▼
┌──────┐   ┌──────┐   ┌──────┐
│Agent1│   │Agent2│   │AgentN│
│模拟用户│  │模拟用户│  │模拟用户│
└──────┘   └──────┘   └──────┘
```

### Agent 职责
- 模拟用户登录
- 建立长连接
- 发送消息
- 收消息
- 上报结果
- 模拟心跳
- 模拟断网重连

---

# 4. 数据准备

## 4.1 为什么数据准备很重要

IM 系统性能和数据分布高度相关，不能只造“空用户”。

要准备：

- 用户数据
- 好友关系
- 群关系
- 会话分布
- 消息历史
- token / 鉴权信息
- push token
- 大群 / 大 V 样本

## 4.2 用户模型

### 用户分层
建议至少拆成 4 类：

| 用户类型 | 比例 | 特征 |
|---|---|---|
| 轻度用户 | 60% | 少量会话，少发消息 |
| 中度用户 | 30% | 常规聊天 |
| 重度用户 | 9% | 高频收发 |
| 超级用户 | 1% | 大 V / 客服 / 群主 |

### 数据字段
```json
{
  "user_id": 100001,
  "device_count": 2,
  "region": "east",
  "friend_count": 200,
  "group_count": 30,
  "role": "normal",
  "is_vip": false
}
```

## 4.3 关系数据准备

### 好友关系
- 每用户平均 100~300 好友
- 长尾分布
- 大 V 可有 10万+ 粉丝

### 群关系
- 小群：3~20 人
- 中群：20~200 人
- 大群：200~5000 人
- 超大群：5000~100000 人

### 分布建议
| 群类型 | 比例 |
|---|---|
| 小群 | 80% |
| 中群 | 15% |
| 大群 | 4% |
| 超大群 | 1% |

## 4.4 历史消息准备

为了验证同步、离线、搜索等功能，需要灌入历史数据：

- 每个活跃会话 100~1000 条
- 大群 1万~10万条历史
- 包含多种消息类型：
  - text
  - image
  - file
  - reply
  - mention
  - recall

## 4.5 测试账号与 token

压测用户要提前生成：

- user_id
- auth token
- device_id
- push token（可伪造/影子通道）
- 地域归属

压测框架启动前从账号池拉取。

---

# 5. 流量模型构建

## 5.1 IM 流量组成

压测不能只压“发送消息”，还要包含整套行为：

| 行为 | 比例参考 |
|---|---|
| 心跳 | 所有在线连接持续 |
| 登录/重连 | 低频，但关键 |
| 发送消息 | 业务核心 |
| 接收消息 | 与发送成对出现 |
| 拉同步 | 断线/上线/补偿 |
| 已读上报 | 中频 |
| 正在输入 | 低频 |
| 撤回/编辑 | 低频 |
| @消息 | 中低频 |
| push | 离线链路需要 |

## 5.2 消息类型分布

建议按真实业务比例：

| 类型 | 比例 |
|---|---|
| 文本 | 75% |
| 图片 | 15% |
| 文件 | 3% |
| 语音 | 3% |
| 视频 | 1% |
| 自定义/卡片 | 3% |

## 5.3 会话类型分布

| 会话类型 | 比例 |
|---|---|
| 单聊 | 70% |
| 小群 | 20% |
| 中群 | 7% |
| 大群 | 2% |
| 超大群 | 1% |

## 5.4 在线/离线比例

压测中要区分：

| 状态 | 比例 |
|---|---|
| 在线用户 | 30% |
| 后台用户 | 30% |
| 离线用户 | 40% |

因为：

- 在线用户走实时通道
- 后台用户可能触发 push
- 离线用户走 inbox + push + 上线同步

## 5.5 多端分布

| 设备组合 | 比例 |
|---|---|
| 单设备在线 | 70% |
| 双设备在线 | 25% |
| 三设备在线 | 5% |

用于验证多端同步和去重。

---

# 6. 流量回放

## 6.1 回放的来源

### 方案 A：线上真实流量采样（推荐）
从生产日志采样出匿名化流量：

- 发送频率
- 消息大小
- 会话类型
- 用户活跃时间分布

### 方案 B：人工构造流量模型
适合早期没有生产数据的阶段。

## 6.2 真实流量回放流程

```
生产日志
  │
  ▼
脱敏处理
  - user_id 映射
  - conv_id 映射
  - 内容脱敏/替换
  │
  ▼
回放事件文件
  │
  ▼
压测 Agent 读取回放
  │
  ▼
按原时间比例 / 加速比例发送
```

## 6.3 脱敏规则

不能把真实用户数据直接压测使用。

建议脱敏：

- `user_id -> hash 映射`
- `conv_id -> hash 映射`
- 文本内容 -> 模板化替换
- 图片/file url -> 压测专用对象地址
- push token -> 影子 token

## 6.4 回放速度

### 1x 回放
按真实时间速率回放。

### 2x / 5x / 10x 回放
用于容量评估。

### 突刺模式
把某个时间窗口的流量压缩到更短时间内。

例如：
- 原来 10 分钟的流量，1 分钟打完

## 6.5 回放实现示例

```python
class ReplayEngine:
    def __init__(self, events):
        self.events = events

    def run(self, speed=1.0):
        start_wall = time.time()
        start_event_ts = self.events[0]["ts"]

        for event in self.events:
            target = (event["ts"] - start_event_ts) / speed
            now = time.time() - start_wall
            if target > now:
                time.sleep(target - now)

            self.dispatch(event)

    def dispatch(self, event):
        if event["type"] == "send_msg":
            self.agent.send_message(event["user"], event["conv"], event["content"])
        elif event["type"] == "read":
            self.agent.report_read(event["user"], event["conv"], event["seq"])
        elif event["type"] == "login":
            self.agent.login(event["user"])
```

---

# 7. 全链路改造（影子库 / 影子链路）

## 7.1 为什么需要影子链路

生产压测如果直接打真实链路，会有风险：

- 污染真实 DB
- 真实用户收到压测消息
- Kafka topic 混入测试事件
- push 被真实发出

所以需要**影子环境隔离**。

## 7.2 影子链路设计

### 方式 A：Header 标记（推荐）
压测请求带标记：

```http
X-Pressure-Test: true
X-PT-Biz: im
```

服务端识别后：

- 走影子 DB
- 走影子 Redis key 前缀
- 走影子 Kafka topic
- 走影子 Push 通道

### 方式 B：独立域名/入口
压测客户端走单独接入域名：
- `pt-im.example.com`

缺点是与生产真实路径不完全一致。

---

## 7.3 影子资源规划

| 组件 | 生产 | 压测影子 |
|---|---|---|
| DB | `im_message` | `pt_im_message` 或独立库 |
| Redis | `presence:*` | `pt:presence:*` |
| Kafka | `msg.fanout.normal` | `pt.msg.fanout.normal` |
| Push | 真厂商 | Mock / 沙箱 |
| ES | `im_search` | `pt_im_search` |

## 7.4 影子 Topic 设计

```
生产: msg.fanout.normal
影子: pt.msg.fanout.normal
```

压测消费者只消费 `pt.*`。

## 7.5 影子 Push

压测时不能触发真实 push。

方案：

- APNs：sandbox 环境
- FCM：测试项目
- 厂商通道：mock server
- 或统一直接 mock

---

# 8. 执行流程

## 8.1 标准压测流程

### Step 1：明确目标
例如：
- 验证 50 万消息 QPS 是否可支撑
- 验证 100 万在线用户是否稳定
- 验证大群峰值 5 万 fanout/s 是否正常

### Step 2：准备数据
- 构造账号池
- 构造关系图
- 灌历史数据

### Step 3：环境检查
- 所有组件健康
- 监控就位
- 告警降噪
- 影子链路就位

### Step 4：预热
- 先建立连接
- 先灌入基础在线状态
- 让缓存热起来

### Step 5：逐步加压
建议曲线：

```
10% → 30% → 50% → 70% → 100% → 120%
每阶段持续 10~30 分钟
```

### Step 6：稳态观察
在目标流量维持 30 分钟以上，观察：

- CPU
- 延迟
- lag
- error rate
- 内存
- GC
- 连接稳定性

### Step 7：故障注入（可选）
在稳态流量下：

- 杀 1 台 Gateway
- Kafka broker 下线
- Redis 主切换
- DB 主切换

验证系统是否自动恢复。

### Step 8：收尾
- 结束压测
- 清理影子数据
- 导出报告

---

# 9. 性能瓶颈定位

全链路压测最重要的是定位**第一个瓶颈点**。

## 9.1 典型瓶颈层级

### 1）Gateway 先满
现象：
- 建连变慢
- 消息收发延迟上升
- CPU 高
- send queue 堵塞

定位指标：
- `gateway_connections_active`
- `gateway_send_blocked_total`
- 网络带宽
- epoll wait

### 2）MsgWrite 写入瓶颈
现象：
- 发送 ACK 慢
- DB 写入延迟增加
- outbox 堆积

定位指标：
- DB QPS
- DB P99 latency
- thread pool queue
- 慢查询

### 3）Redis 瓶颈
现象：
- 在线状态查询慢
- 未读计算慢
- 限流误触发

定位指标：
- Redis ops/s
- CPU
- hit ratio
- slowlog
- hot key

### 4）Kafka 瓶颈
现象：
- lag 持续增长
- 消费延迟变大
- 推送延迟增加

定位指标：
- partition lag
- producer retry
- broker network
- ISR 变化

### 5）Deliver / InboxWriter 瓶颈
现象：
- 在线用户消息延迟增加
- 离线消息入 inbox 慢

定位指标：
- deliver rpc latency
- inbox insert latency
- consumer backlog

### 6）Push 瓶颈
现象：
- push 延迟变大
- 厂商错误码增多

定位指标：
- push success rate
- rate limited
- channel fallback ratio

---

## 9.2 瓶颈定位方法论

### 方法 1：看延迟分布链路
把消息拆成多个 span：

- client_send → gateway_recv
- gateway_recv → db_commit
- db_commit → kafka_publish
- kafka_publish → deliver_consume
- deliver_consume → gateway_push
- gateway_push → client_recv

哪一段 P99 开始突增，就是瓶颈点。

### 方法 2：看队列
任何队列增长，都是瓶颈信号：

- Gateway send queue
- RPC thread pool queue
- outbox pending
- Kafka lag
- inbox write queue
- push queue

### 方法 3：看资源不是看平均值
平均 CPU 50% 不代表没问题，可能某个分片已经 100%。

重点看：
- 按实例
- 按 shard
- 按 partition
- 按 hot key

### 方法 4：控制变量
一次只调一个参数，比如：
- 增加 Gateway 副本数
- 增加 Kafka partition
- 增加 Redis 节点数

看瓶颈是否后移。

---

# 10. 压测报告

## 10.1 报告模板

```markdown
# IM 全链路压测报告

## 一、目标
- 验证 100 万在线
- 验证 50 万 msg/s
- 验证大群 fanout

## 二、环境
- 集群规模
- 版本
- 压测时间
- 压测工具

## 三、流量模型
- 在线用户数
- 单聊/群聊比例
- 消息类型分布
- 多端比例
- 离线比例

## 四、结果
### 4.1 核心指标
- 连接成功率
- 消息成功率
- P50/P99 延迟
- Kafka lag
- push 成功率

### 4.2 资源指标
- CPU
- 内存
- 网络
- 存储
- GC

### 4.3 瓶颈点
- 首个瓶颈组件
- 临界流量
- 触发条件

## 五、故障演练结果
- 杀 Gateway
- Kafka broker 故障
- DB 切主
- Redis 切主

## 六、结论
- 当前最大安全容量
- 建议上线容量
- 风险点

## 七、改进项
| 改进项 | Owner | 截止时间 |
|---|---|---|
```

## 10.2 输出结论要明确

压测报告不能只说“系统正常”，必须给出：

- **当前最大安全在线数**
- **当前最大安全 QPS**
- **哪一层先满**
- **扩容建议**
- **大促前建议冗余倍数**

---

# 11. 大促压测实战

## 11.1 大促前目标

例如双十一前，要求：
- 平峰 3 倍容量
- 峰值 1.5 倍冗余
- 核心链路全部压过一遍
- 关键故障演练至少 3 次

## 11.2 大促特征流量

- 系统通知多
- 群消息多
- push 多
- 登录重连多
- 客服/机器人多

所以压测要重点覆盖：

1. 大群广播
2. push 高峰
3. 重连风暴
4. Kafka 消费 lag 恢复
5. Redis 热 key 抗性

## 11.3 推荐流程

```
T-30 天：完成单模块压测
T-21 天：完成全链路压测
T-14 天：完成第一次故障演练
T-7 天：完成复测
T-3 天：冻结核心变更
T-1 天：小流量拨测 + 监控确认
```

---

# 12. 风险控制与回滚

## 12.1 压测风险

- 误入真实链路
- 打爆共享中间件
- 触发真实告警风暴
- 厂商 push 误触发
- 影子数据堆积影响存储

## 12.2 风险控制措施

1. 影子链路强隔离
2. 压测前确认告警降噪
3. 设置全局熔断阈值
4. 压测客户端白名单
5. 压测窗口提前报备
6. SRE 现场值守

## 12.3 回滚/停止压测条件

满足任一立即停压：

- 生产用户错误率上升
- 核心服务 CPU > 90% 持续 5 分钟
- Kafka lag 持续增长且不可恢复
- Redis 命中率崩塌
- DB 主从延迟失控
- 误触真实 push

## 12.4 一键停压

压测平台必须支持：
- 停止新请求
- 逐步断开压测连接
- 停止流量回放
- 清理影子数据

---

# 13. 常用脚本与命令

## 13.1 Kafka 性能测试

```bash
kafka-producer-perf-test.sh \
  --topic pt.msg.fanout.normal \
  --num-records 1000000 \
  --record-size 512 \
  --throughput -1 \
  --producer-props bootstrap.servers=kafka:9092 acks=all compression.type=lz4
```

## 13.2 Redis 压测

```bash
memtier_benchmark \
  --server=redis-host \
  --port=6379 \
  --protocol=redis \
  --clients=100 \
  --threads=8 \
  --test-time=60 \
  --ratio=1:10
```

## 13.3 MySQL 压测

```bash
sysbench oltp_write_only \
  --mysql-host=db-host \
  --mysql-port=3306 \
  --mysql-user=test \
  --mysql-password=xxx \
  --mysql-db=im \
  --tables=16 \
  --table-size=1000000 \
  --threads=64 \
  --time=300 run
```

## 13.4 K6 WebSocket 示例

```javascript
import ws from 'k6/ws';
import { check } from 'k6';

export default function () {
  const url = 'wss://pt-im.example.com/ws';
  const res = ws.connect(url, {}, function (socket) {
    socket.on('open', function () {
      socket.send(JSON.stringify({ cmd: 'login', token: 'test-token' }));
      socket.setInterval(function () {
        socket.send(JSON.stringify({ cmd: 'heartbeat' }));
      }, 30000);

      socket.setTimeout(function () {
        socket.send(JSON.stringify({
          cmd: 'send_msg',
          conv_id: 123,
          content: 'hello'
        }));
      }, 1000);
    });

    socket.on('message', function (data) {
      // 校验消息
    });

    socket.on('close', function () {
      // 连接关闭
    });
  });

  check(res, { 'status is 101': (r) => r && r.status === 101 });
}
```

## 13.5 自研 Agent 命令

```bash
./im-pt-agent \
  --dispatch=https://pt-dispatch.example.com \
  --users=100000 \
  --regions=east,south \
  --scenario=send_and_receive \
  --msg-rate=50000 \
  --group-ratio=0.3 \
  --offline-ratio=0.4 \
  --duration=30m
```

---

# 总结

> 全链路压测不是“把 QPS 打上去看看”，而是：
>
> - 用**真实流量模型**模拟真实 IM 业务
> - 通过**影子链路**保证生产安全
> - 覆盖**接入、写入、Kafka、投递、同步、push**全链路
> - 用**延迟分段、队列堆积、资源水位**定位第一个瓶颈点
> - 最终输出**容量边界、瓶颈组件、扩容建议、风险清单**
>
> 对千万并发 IM 来说，压测必须是一套**长期机制**，而不是上线前一次性动作。

---

**文档结束** | Version 1.0