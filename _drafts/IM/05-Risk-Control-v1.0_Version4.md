# IM 风控规则手册 v1.0

> 适用：风控引擎 / 反垃圾 / 内容安全  
> 目标：识别异常行为、保护用户体验、控制业务风险

---

## 目录

1. 风控总体框架
2. 完整规则清单
3. 特征工程
4. 模型训练
5. 决策与处置
6. A/B 实验
7. 反馈与迭代

---

# 1. 风控总体框架

## 1.1 风控目标

```
1. 反垃圾：广告、营销、骚扰
2. 反欺诈：钓鱼、诈骗、虚假身份
3. 反作弊：脚本、批量操作
4. 内容安全：违法、违规、未成年保护
5. 业务保护：恶意刷接口、爬数据
```

## 1.2 整体架构

```
┌─────────────────────────────────────────────┐
│  业务侧 (Gateway / 业务服务)                  │
│  - 同步快审                                  │
│  - 上报行为事件                              │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  Kafka: user.behavior                       │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  实时风控引擎 (Flink)                         │
│  - 特征聚合                                  │
│  - 规则匹配                                  │
│  - 模型推理                                  │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  决策中心                                    │
│  - 命中规则                                  │
│  - 风险等级                                  │
│  - 处置动作                                  │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  Redis: risk:user:{uid}                     │
│  业务层查询消费                              │
└─────────────────────────────────────────────┘
```

## 1.3 三层风控

```
事前 (preventive):  注册校验、设备指纹
事中 (real-time):   消息发送/接口调用拦截
事后 (post-hoc):    离线分析、批量处理
```

## 1.4 评估指标

| 指标 | 含义 | 目标 |
|---|---|---|
| 准确率 | 拦截中真坏比例 | > 95% |
| 召回率 | 真坏中被拦比例 | > 80% |
| 误伤率 | 好用户被拦比例 | < 0.1% |
| 时延 | 决策耗时 | < 50ms |

---

# 2. 完整规则清单

## 2.1 行为频率规则

| ID | 规则 | 阈值 | 处置 |
|---|---|---|---|
| F001 | 单用户消息频率 | > 200/分钟 | Lv2 降速 |
| F002 | 单用户消息频率 | > 500/分钟 | Lv3 临封 1h |
| F003 | 单用户群发频率 | > 30 次/小时 | Lv3 临封 |
| F004 | 单用户加好友频率 | > 50/天 | Lv2 |
| F005 | 单用户建群频率 | > 10/小时 | Lv3 |
| F006 | 单用户拉人入群 | > 100/小时 | Lv3 |
| F007 | 单 IP 注册数 | > 5/天 | Lv4 |
| F008 | 单 IP 登录用户数 | > 20/天 | Lv3 |
| F009 | 单设备登录账号 | > 5 个 | Lv2 |
| F010 | 历史消息拉取频率 | > 30/分钟 | Lv2 |

## 2.2 行为模式规则

| ID | 规则 | 触发条件 | 处置 |
|---|---|---|---|
| P001 | 短时大量私聊 | 30 分钟给 > 50 个陌生人发 | Lv3 |
| P002 | 同内容多发 | 1 小时同/相似内容发 > 10 次 | Lv3 |
| P003 | 加好友通过率低 | 24h 申请 > 30 通过 < 5% | Lv2 |
| P004 | 只发不收 | 7 天发送 > 100 接收 < 5 | Lv2 |
| P005 | 发后立删 | 发消息后 1min 内撤回 > 50% | Lv2 |
| P006 | 异常活跃时段 | 凌晨 2-5 点高频活动 | Lv1 加验证 |
| P007 | 频繁切设备 | 1 天切 > 5 个设备 | Lv2 |
| P008 | 异地登录 | 2 小时内异地切换 | Lv1 验证码 |
| P009 | 频繁踢人 | 群主 1h 踢 > 20 人 | Lv2 |
| P010 | 拉群轰炸 | 1h 拉 > 5 个群发同样内容 | Lv4 封号 |

## 2.3 内容规则

| ID | 规则 | 检测方式 | 处置 |
|---|---|---|---|
| C001 | 关键词命中 | 黑名单匹配 | 直接 block |
| C002 | URL 黑名单 | 域名 + 完整 URL 双匹配 | block |
| C003 | 仿冒链接 | 域名相似度（编辑距离） | 警告 + Lv2 |
| C004 | 二维码（非好友） | 图片 OCR + 解码 | Lv2 |
| C005 | 联系方式（非好友） | 手机号/微信号正则 | Lv2 |
| C006 | 涉政 | NLP 模型 | block + Lv4 |
| C007 | 涉黄涉暴 | 文本 + 图片模型 | block + Lv4 |
| C008 | 钓鱼诈骗 | 多特征组合（链接+话术） | block + Lv4 |
| C009 | 营销话术 | NLP 分类 | Lv2 |
| C010 | 未成年保护 | 涉未成年敏感内容 | block + 上报 |

## 2.4 关系链规则

| ID | 规则 | 条件 | 处置 |
|---|---|---|---|
| R001 | 新号高频加人 | 注册 < 7 天，加 > 30 人 | Lv2 |
| R002 | 单向关系链多 | 加了很多人，反向少 | Lv1 标记 |
| R003 | 异常社交图谱 | 关系密度异常（图算法） | Lv2 |
| R004 | 团伙特征 | 多账号互相加好友、互相点赞 | Lv3 |
| R005 | 假人特征 | 头像/昵称模式化 | Lv2 |

## 2.5 设备/环境规则

| ID | 规则 | 条件 | 处置 |
|---|---|---|---|
| D001 | 模拟器 | 检测到 emulator | Lv2 |
| D002 | Root/越狱 | 检测到 root | Lv1 标记 |
| D003 | 改机工具 | 设备指纹异常 | Lv3 |
| D004 | 自动化框架 | 检测到 hook/auto-click | Lv4 |
| D005 | 机房 IP | IP 在机房段 | Lv3 |
| D006 | 代理/VPN | IP 异常 | Lv1 标记 |
| D007 | 无浏览器特征 | UA / 行为特征异常 | Lv2 |

## 2.6 账号规则

| ID | 规则 | 条件 | 处置 |
|---|---|---|---|
| A001 | 新号 | 注册 < 24h 高频活动 | Lv2 |
| A002 | 长期不活跃突然活跃 | 30 天未登录后高频发 | Lv2 |
| A003 | 头像可疑 | 默认头像 / 网图 | Lv1 |
| A004 | 昵称可疑 | 命名模式（如 "用户12345"） | Lv1 |
| A005 | 资料完整度低 | 无头像/无昵称/无简介 | Lv1 |
| A006 | 历史封禁 | 曾被封禁 | Lv2 |
| A007 | 关联可疑账号 | 同设备/同 IP 关联坏账号 | Lv2 |

---

# 3. 特征工程

## 3.1 特征分类

```
基础特征:    用户/设备/IP 静态信息
统计特征:    各种维度的计数、比率
时序特征:    时间窗口聚合
关系特征:    社交图谱
内容特征:    文本/图片/链接

实时特征:    秒/分钟级窗口
准实时特征:  小时级
离线特征:    天级
```

## 3.2 核心特征列表

### 用户特征
```
- 注册时长 (天)
- 活跃天数
- 总消息数
- 会话数
- 好友数
- 加群数
- 历史封禁次数
- 最近 7/30/90 天活跃度
- 设备数
- 登录 IP 数
```

### 行为特征（滑动窗口）
```
窗口: 1min / 5min / 1h / 1d / 7d / 30d

- 消息发送数
- 消息接收数
- 收发比
- 群消息数
- 私聊数
- 加好友请求数
- 加好友成功率
- 撤回率
- 编辑率
- 历史拉取次数
- 文件发送数
```

### 内容特征
```
- 平均消息长度
- 链接占比
- 图片占比
- 关键词命中数
- 内容相似度（SimHash）
- 与历史消息相似度
- 多收件人 + 同内容 → 群发指数
```

### 关系特征
```
- 朋友数
- 朋友的朋友数（二度）
- 社交密度
- 单向关系数
- 互动频率
- 与坏账号的距离（图算法）
```

### 设备/环境特征
```
- 设备指纹（IMEI / IDFV / 自定义）
- IP 地理位置
- IP 类型（家庭/机房/代理）
- 网络类型（WiFi/4G/5G）
- 系统版本
- 应用版本
- 模拟器标识
- Root 标识
```

## 3.3 特征存储

```
实时特征: Redis ZSet / HyperLogLog
  rate:msg:{uid}:1min   滑动窗口计数
  recipient:{uid}:1h    HLL 去重收件人数

准实时: Redis Hash + 定时刷新
  user_stats:{uid}      各类计数

离线: HBase / Hive
  user_features         全量特征表
```

## 3.4 特征计算

### 实时窗口计数（Redis）

```lua
-- sliding_window.lua
local key = KEYS[1]
local window = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local member = ARGV[3]

redis.call('ZADD', key, now, member)
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
redis.call('EXPIRE', key, window / 1000)
return redis.call('ZCARD', key)
```

### 流式特征聚合（Flink）

```java
DataStream<BehaviorEvent> events = kafkaSource(...);

events
    .keyBy(e -> e.userId)
    .window(SlidingEventTimeWindows.of(Time.hours(1), Time.minutes(1)))
    .aggregate(new UserStatsAggregator())
    .addSink(redisSink);
```

---

# 4. 模型训练

## 4.1 模型类型

| 模型 | 用途 | 算法 |
|---|---|---|
| 垃圾消息分类 | 文本是否垃圾 | BERT / FastText |
| 用户分群 | 用户类型识别 | XGBoost / LightGBM |
| 异常检测 | 行为异常 | Isolation Forest / AutoEncoder |
| 团伙挖掘 | 团伙账号识别 | Graph Neural Network |
| 图片审核 | 涉黄/涉暴 | CNN (预训练 + 迁移) |

## 4.2 数据准备

### 标注数据来源
```
- 历史封禁账号（正样本）
- 用户举报
- 人工审核
- 内部红队测试
- 公开数据集
```

### 数据质量
```
- 标注一致性 > 95%（双盲标注）
- 正负样本平衡（重采样）
- 时间分布均匀
- 避免 leakage
```

## 4.3 训练流程

```
1. 数据采样
   - 时间窗口
   - 正负比例 1:5 ~ 1:10
   
2. 特征提取
   - 用户特征
   - 行为特征
   - 内容特征
   
3. 特征工程
   - 缺失值填充
   - 标准化
   - 离散化
   
4. 模型训练
   - 划分训练/验证/测试 (7:2:1)
   - 交叉验证
   - 超参搜索
   
5. 模型评估
   - AUC / Precision / Recall / F1
   - 混淆矩阵
   - 业务指标
   
6. 上线发布
   - A/B 测试
   - 灰度
   - 全量
```

## 4.4 模型上线

```
模型存储: TensorFlow Serving / TorchServe / ONNX Runtime
推理服务: 独立部署，水平扩展
推理延迟: P99 < 50ms
监控:
  - QPS
  - 延迟
  - 准确率（线上 sample 对比标注）
  - drift（特征分布漂移）
```

## 4.5 模型迭代

```
每周更新一次:
  - 加新数据
  - 加新特征
  - 调超参

每月评估:
  - 模型效果衰减
  - 是否需要重训

每季度大版本:
  - 模型架构升级
  - 特征体系演进
```

---

# 5. 决策与处置

## 5.1 决策流程

```
事件输入
   │
   ▼
[特征计算]
   │
   ▼
[规则引擎] ─→ 命中规则 → 计算分数
   │                       │
   ▼                       ▼
[模型推理]          [分数聚合]
   │                       │
   └──────────┬────────────┘
              │
              ▼
       [决策器]
              │
              ▼
       [风险等级 0~5]
              │
              ▼
       [处置动作]
              │
              ▼
       [写入 risk:user:{uid}]
```

## 5.2 分数聚合

```python
def calc_risk_score(user, event):
    score = 0
    
    # 规则分
    for rule in matched_rules(user, event):
        score += rule.weight
    
    # 模型分
    model_score = model.predict(features(user, event))
    score += model_score * 100
    
    # 历史分（余热）
    if user.recent_risk_score > 0:
        score += user.recent_risk_score * 0.5
    
    # 上下文调整
    if user.is_vip:
        score *= 0.5  # VIP 容忍度高
    if user.is_new and score > 0:
        score *= 1.5  # 新号严格
    
    return min(score, 100)
```

## 5.3 风险等级映射

```python
def score_to_level(score):
    if score < 20:  return 0  # 正常
    if score < 40:  return 1  # 低风险
    if score < 60:  return 2  # 中风险
    if score < 80:  return 3  # 高风险
    if score < 95:  return 4  # 极高风险
    return 5  # 确认违规
```

## 5.4 处置动作

| 等级 | 动作 | 持续 | 用户感知 |
|---|---|---|---|
| 0 | 无 | - | 无感 |
| 1 | 加验证码 / 二次确认 | 当次 | 轻 |
| 2 | 降速（限流减半） | 1h | 中 |
| 3 | 临时封禁发消息 | 1h~24h | 强 |
| 4 | 临时封号 | 1d~7d | 强 |
| 5 | 永久封号 | 永久 | 强 |

## 5.5 处置组合

```python
def execute_action(user, level):
    if level == 0:
        return
    
    if level >= 1:
        require_captcha(user, ttl=300)
    
    if level >= 2:
        rate_limit(user, multiplier=0.5, ttl=3600)
    
    if level >= 3:
        block_send(user, ttl=3600)
        notify_user("您的账号存在异常行为...")
    
    if level >= 4:
        block_account(user, ttl=86400)
        send_to_review_queue(user)
    
    if level >= 5:
        permanent_ban(user)
        send_to_legal_queue(user)
```

## 5.6 业务集成

```python
# Gateway / 业务层查询
def can_send_message(user_id):
    risk = redis.hgetall(f"risk:user:{user_id}")
    
    level = int(risk.get("level", 0))
    expire_at = int(risk.get("expire_at", 0))
    
    if level == 0 or now() > expire_at:
        return True, None
    
    if level == 1:
        return True, "captcha_required"
    
    if level >= 3:
        return False, risk.get("reason")
    
    return True, "rate_limited"
```

## 5.7 申诉机制

```
用户申诉 → 进入审核队列 → 人工复核 → 决策

复核通过:
  - 解封
  - 调整模型样本（降低误伤）

复核拒绝:
  - 维持处置
  - 告知理由
```

---

# 6. A/B 实验

## 6.1 实验目标

```
1. 验证新规则效果
2. 调整阈值
3. 对比模型版本
4. 评估处置策略
```

## 6.2 实验设计

### 流量分配
```
按 user_id 分组：
  control (50%): 旧规则
  treatment (50%): 新规则

确保同一用户始终在同一组
```

### 实验时长
```
最少 1 周
覆盖周末 + 工作日
样本量足够（统计显著）
```

## 6.3 关键指标

```
正向指标:
  - 拦截违规数（增加）
  - 召回率
  
负向指标 (须监控):
  - 误伤率（上升 → 报警）
  - 用户申诉量
  - DAU / 留存
  - 消息量

业务指标:
  - 整体活跃度
  - 用户体验评分
```

## 6.4 实验流程

```
1. 设计实验
   - 假设
   - 指标
   - 流量
   - 时长
   
2. 灰度上线
   - 1% → 10% → 50%
   
3. 监控
   - 实时大盘
   - 异常自动停止
   
4. 评估
   - 显著性检验
   - 业务影响
   
5. 决策
   - 全量推广 / 调整 / 放弃
   
6. 复盘
```

## 6.5 实验工具

```
平台: 公司内部 A/B 平台 / Optimizely / VWO
分流: 一致性 hash on user_id
日志: 实验组标记，便于离线分析
```

---

# 7. 反馈与迭代

## 7.1 反馈来源

```
1. 用户举报
2. 用户申诉
3. 客服反馈
4. 业务方反馈
5. 监控告警
6. 离线对账
```

## 7.2 标注闭环

```
线上拦截结果
   │
   ▼
抽样 → 人工审核
   │
   ├─ 误伤 → 加入"白样本"
   │         调整规则/模型
   │
   └─ 漏报 → 加入"黑样本"
             补充训练数据
```

## 7.3 模型 drift 监控

```
定期对比:
  - 训练时特征分布
  - 线上特征分布
  
显著漂移 → 触发重训
```

## 7.4 规则维护

```
每月评审:
  - 规则命中量 TOP
  - 规则误伤率
  - 失效规则下线
  - 新增规则评估

每季度大版本:
  - 规则体系重构
  - 特征体系升级
```

## 7.5 红蓝对抗

```
红队:
  - 模拟攻击者
  - 寻找绕过方式
  - 报告漏洞

蓝队:
  - 加固规则
  - 修复漏洞
  - 持续演进
```

---

# 附录：风控数据表

## A.1 规则配置表

```sql
CREATE TABLE risk_rule (
  id          BIGINT PRIMARY KEY,
  rule_code   VARCHAR(32) UNIQUE,
  name        VARCHAR(128),
  description TEXT,
  category    VARCHAR(32),
  expression  TEXT,           -- DSL 或 Groovy
  weight      INT,
  enabled     TINYINT,
  priority    INT,
  created_at  BIGINT,
  updated_at  BIGINT
);
```

## A.2 决策记录表

```sql
CREATE TABLE risk_decision (
  id          BIGINT PRIMARY KEY,
  user_id     BIGINT,
  event_id    VARCHAR(64),
  rules_hit   JSON,           -- 命中的规则
  model_score DECIMAL(5,2),
  total_score DECIMAL(5,2),
  level       TINYINT,
  action      VARCHAR(64),
  context     JSON,
  created_at  BIGINT,
  KEY idx_user_time (user_id, created_at)
) PARTITION BY RANGE (created_at);
```

## A.3 申诉表

```sql
CREATE TABLE risk_appeal (
  id              BIGINT PRIMARY KEY,
  user_id         BIGINT,
  decision_id     BIGINT,
  reason          TEXT,
  evidence        JSON,
  status          TINYINT,    -- 0:pending 1:approved 2:rejected
  reviewer        BIGINT,
  review_note     TEXT,
  created_at      BIGINT,
  reviewed_at     BIGINT
);
```

---

**文档结束** | Version 1.0