# 消息搜索引擎设计 v1.0

> 适用：IM 历史消息全文搜索、@我搜索、文件搜索  
> 选型：Elasticsearch 8.x  
> 目标：千亿级消息、P99 < 200ms、相关性优秀

---

## 目录

1. 设计目标与挑战
2. 整体架构
3. ES 索引设计
4. 写入链路
5. 分片策略
6. 查询优化
7. 相关性排序
8. 隐私与权限
9. 容量与成本
10. 监控与运维

---

# 1. 设计目标与挑战

## 1.1 业务需求

```
1. 全局搜索: 用户搜自己所有消息
2. 会话内搜索: 在某个群/会话内搜
3. @ 我搜索: 找历史 @ 我的消息
4. 文件搜索: 按文件名/类型
5. 联系人搜索: 找消息里提到某人
6. 高级筛选: 时间范围 / 发送者 / 类型
```

## 1.2 挑战

```
数据量:        千亿级消息，PB 级
写入吞吐:     50 万消息/秒
查询时延:     P99 < 200ms
中文分词:     IK / jieba
权限隔离:     用户只能搜自己有权访问的
长尾用户:     有人有 10 万会话，有人有 10 个
冷热不均:     新消息查得多，老消息查得少
```

## 1.3 设计目标

| 指标 | 目标 |
|---|---|
| 写入吞吐 | 50 万 docs/s |
| 写入延迟 | P99 < 5s（消息→可搜） |
| 查询 P99 | < 200ms |
| 召回率 | > 95% |
| 准确率 | > 90% |
| 数据保留 | 1 年（可配置） |

---

# 2. 整体架构

## 2.1 架构图

```
┌──────────────────────────────────────────────┐
│  消息写入服务 (MsgWrite)                      │
└───────────────┬──────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Kafka: search.index                         │
└───────────────┬──────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Indexer 服务（消费 + 加工 + 写 ES）          │
│  - 内容预处理（分词、清洗）                    │
│  - 富化（用户名、群名）                        │
│  - 批量写入                                    │
└───────────────┬──────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Elasticsearch 集群（按时间+用户分片）        │
└───────────────┬──────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Search API 服务                             │
│  - 权限校验                                  │
│  - 查询构造                                  │
│  - 结果排序与高亮                            │
└──────────────────────────────────────────────┘
                ▲
                │
        客户端搜索请求
```

## 2.2 核心组件

| 组件 | 职责 |
|---|---|
| **Indexer** | 消费 Kafka、文档加工、批量写 ES |
| **ES Cluster** | 倒排索引、分布式查询 |
| **Search API** | 查询接口、权限、聚合 |
| **Admin** | 索引管理、reindex、归档 |

---

# 3. ES 索引设计

## 3.1 索引命名

按时间分索引，便于归档和滚动：

```
im_messages_2026_05    ← 2026年5月的消息
im_messages_2026_04    ← 2026年4月
im_messages_2026_03
...
```

每月一个索引，共 12 个滚动。1 年前的归档/删除。

## 3.2 索引模板

```json
PUT _index_template/im_messages_template
{
  "index_patterns": ["im_messages_*"],
  "template": {
    "settings": {
      "number_of_shards": 64,
      "number_of_replicas": 1,
      "refresh_interval": "5s",
      "index.translog.durability": "async",
      "index.translog.sync_interval": "30s",
      "index.routing.allocation.total_shards_per_node": 4,
      
      "analysis": {
        "analyzer": {
          "ik_smart_pinyin": {
            "type": "custom",
            "tokenizer": "ik_smart",
            "filter": ["lowercase", "pinyin_filter"]
          },
          "ik_max_word_pinyin": {
            "type": "custom",
            "tokenizer": "ik_max_word",
            "filter": ["lowercase", "pinyin_filter"]
          }
        },
        "filter": {
          "pinyin_filter": {
            "type": "pinyin",
            "keep_first_letter": true,
            "keep_full_pinyin": true,
            "keep_original": true
          }
        }
      }
    },
    "mappings": {
      "_source": {
        "excludes": ["content_raw_blob"]
      },
      "properties": {
        "server_msg_id": { "type": "keyword" },
        "conv_id":       { "type": "keyword" },
        "sender_id":     { "type": "keyword" },
        "msg_type":      { "type": "keyword" },
        "visible_seq":   { "type": "long" },
        
        "text": {
          "type": "text",
          "analyzer": "ik_max_word_pinyin",
          "search_analyzer": "ik_smart_pinyin",
          "fields": {
            "keyword": { "type": "keyword", "ignore_above": 256 }
          }
        },
        
        "sender_name": {
          "type": "text",
          "analyzer": "ik_max_word",
          "fields": {
            "keyword": { "type": "keyword" }
          }
        },
        
        "conv_name": {
          "type": "text",
          "analyzer": "ik_max_word"
        },
        
        "mentioned_users": { "type": "keyword" },
        "has_mention_all": { "type": "boolean" },
        
        "files": {
          "type": "nested",
          "properties": {
            "name":  { "type": "text", "analyzer": "ik_max_word" },
            "type":  { "type": "keyword" },
            "size":  { "type": "long" },
            "url":   { "type": "keyword", "index": false }
          }
        },
        
        "urls":          { "type": "keyword" },
        "is_recalled":   { "type": "boolean" },
        "is_edited":     { "type": "boolean" },
        
        "created_at":    { "type": "date", "format": "epoch_millis" },
        
        "members":       { "type": "keyword" }    // 该消息可见的用户
      }
    },
    "aliases": {
      "im_messages": {}
    }
  }
}
```

## 3.3 字段说明

| 字段 | 类型 | 用途 |
|---|---|---|
| `server_msg_id` | keyword | 唯一 ID（去重） |
| `conv_id` | keyword | 会话过滤 |
| `sender_id` | keyword | 发送者过滤 |
| `text` | text | 全文搜索主字段 |
| `sender_name` | text | 搜"张三发的消息" |
| `mentioned_users` | keyword | 搜 @我 |
| `files` | nested | 文件附件搜索 |
| `created_at` | date | 时间范围 |
| `members` | keyword | **权限过滤** |

## 3.4 关键设计：members 字段

为了实现权限隔离，每条消息冗余一个 `members` 数组，包含**该消息可见的所有用户 ID**。

```
私聊消息: members = [sender_id, receiver_id]
群消息:   members = [所有当前群成员]
```

查询时：

```json
{
  "bool": {
    "must": [{ "match": { "text": "项目计划" } }],
    "filter": [{ "term": { "members": "u_1001" } }]
  }
}
```

只能搜到自己有权访问的消息。

### 群成员变更怎么办？

**问题**：用户加入群后，能不能搜到加群之前的消息？

```
策略 A: 不能搜（推荐）
  - members 字段记录消息发送时的成员
  - 新加入者不更新历史 members
  - 简单、快、合规

策略 B: 能搜
  - 群成员变更时 reindex 历史消息
  - 代价大（万人群每次变更要更新所有历史）
  - 不推荐
```

实战推荐 A。

## 3.5 分词器选择

### 中文分词
```
ik_max_word: 最细粒度，索引用
ik_smart:    粗粒度，搜索用
```

### 拼音支持
```
"张三" 用户能搜到 "zhangsan" / "zs"
通过 pinyin filter 实现
```

### 多语言
```
全球版需要其他语言:
  英文: standard analyzer
  日文: kuromoji
  韩文: nori
  
按语言/字段选择分析器
```

---

# 4. 写入链路

## 4.1 数据流

```
MsgWrite
   │ 写消息库 + Outbox
   ▼
Kafka: search.index
   │ 消费
   ▼
Indexer
   │ 富化（查用户名、群名、成员）
   │ 加工（分词预处理、敏感字段过滤）
   │ 批量
   ▼
Elasticsearch
```

## 4.2 事件结构

```json
{
  "event_type": "MESSAGE_CREATED",
  "server_msg_id": "s_99001",
  "conv_id": "c123",
  "conv_type": "group",
  "sender_id": "u_1001",
  "msg_type": "text",
  "content": {
    "text": "@张三 看一下这个计划",
    "mentions": [{ "user_id": "u_2001" }]
  },
  "files": [],
  "visible_seq": 850,
  "created_at": 1710000000000
}
```

## 4.3 Indexer 实现

```go
type Indexer struct {
    consumer    *kafka.Consumer
    esClient    *elasticsearch.Client
    enricher    *Enricher
    batchSize   int
    flushPeriod time.Duration
}

func (idx *Indexer) Run(ctx context.Context) error {
    buffer := make([]*Document, 0, idx.batchSize)
    timer := time.NewTimer(idx.flushPeriod)
    
    for {
        select {
        case <-ctx.Done():
            idx.flush(buffer)
            return nil
            
        case msg := <-idx.consumer.Messages():
            event := decode(msg.Value)
            
            // 过滤不需要索引的
            if !idx.shouldIndex(event) {
                continue
            }
            
            // 富化
            doc := idx.enricher.Build(event)
            buffer = append(buffer, doc)
            
            if len(buffer) >= idx.batchSize {
                idx.flush(buffer)
                buffer = buffer[:0]
                timer.Reset(idx.flushPeriod)
            }
            
        case <-timer.C:
            if len(buffer) > 0 {
                idx.flush(buffer)
                buffer = buffer[:0]
            }
            timer.Reset(idx.flushPeriod)
        }
    }
}

func (idx *Indexer) flush(docs []*Document) {
    if len(docs) == 0 {
        return
    }
    
    // 构造 _bulk 请求
    var buf bytes.Buffer
    for _, doc := range docs {
        buf.WriteString(fmt.Sprintf(`{"index":{"_index":"%s","_id":"%s"}}`+"\n",
            doc.IndexName(), doc.ID))
        buf.Write(doc.JSON())
        buf.WriteByte('\n')
    }
    
    resp, err := idx.esClient.Bulk(bytes.NewReader(buf.Bytes()))
    // 处理结果，部分失败重试
}
```

## 4.4 富化（Enrichment）

Indexer 需要补充原始消息没有的字段：

```go
type Enricher struct {
    userCache  *UserCache
    convCache  *ConvCache
    groupCache *GroupMemberCache
}

func (e *Enricher) Build(event *MessageEvent) *Document {
    sender, _ := e.userCache.Get(event.SenderID)
    conv, _ := e.convCache.Get(event.ConvID)
    
    var members []string
    if event.ConvType == "group" {
        members, _ = e.groupCache.GetMembers(event.ConvID)
    } else {
        members = []string{event.SenderID, event.ReceiverID}
    }
    
    return &Document{
        ID:           event.ServerMsgID,
        ConvID:       event.ConvID,
        SenderID:     event.SenderID,
        SenderName:   sender.Name,
        ConvName:     conv.Name,
        Text:         extractText(event.Content),
        MentionedUsers: extractMentions(event.Content),
        HasMentionAll: hasMentionAll(event.Content),
        Members:      members,
        CreatedAt:    event.CreatedAt,
    }
}
```

## 4.5 撤回 / 编辑

```
撤回:
  PARTIAL UPDATE: { "is_recalled": true, "text": "" }
  或：DELETE 文档（推荐）

编辑:
  PARTIAL UPDATE: { "text": "new content", "is_edited": true }
```

## 4.6 群成员变更

```
新成员加入: 不动历史索引（策略 A）
成员退出:   不动历史索引（保留搜索权）

或者:
成员退出后立即:
  for doc in conv 的所有历史:
    UPDATE doc.members 移除该用户
  代价大,通常不做
```

## 4.7 批量优化

```
batch_size:    1000 docs
flush_period:  1s
```

单 Indexer 实例：

```
1000 docs/batch × 1 batch/s = 1K docs/s
扩展: 50 个实例 = 50K docs/s
```

不够时增加 Kafka 分区 + Indexer 实例。

---

# 5. 分片策略

## 5.1 时间分片（主分片维度）

```
im_messages_2026_01
im_messages_2026_02
...
```

好处：
- 老数据归档简单
- 单索引大小可控
- 查询时可按时间过滤索引

## 5.2 按月切分理由

```
日切: 索引太多(365 个),元数据负担重
月切: 12 个/年,合适
年切: 单索引太大,扩容难
```

## 5.3 主分片数

```
单索引: 64 主分片
单分片: 30~50GB
单月数据: 64 × 50GB = 3.2TB
```

## 5.4 副本

```
number_of_replicas: 1
高可用 + 读扩展
```

## 5.5 路由（routing）

将同一会话的消息路由到同一分片，加速会话内搜索：

```
PUT im_messages_2026_05/_doc/s_99001?routing=c123
```

查询时也带 routing：

```
GET im_messages/_search?routing=c123
{ "query": ... }
```

只查 1 个分片而不是 64 个，**性能提升 60 倍**。

## 5.6 分片热点

```
大群 (万人群): 消息多,单分片热点

解决:
  - 大群消息不带 routing,分散到所有分片
  - 或用 hash(conv_id, time_bucket) 加盐
```

---

# 6. 查询优化

## 6.1 典型查询

### 全局搜索

```json
GET im_messages/_search
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "项目计划",
            "fields": ["text^2", "sender_name", "files.name"]
          }
        }
      ],
      "filter": [
        { "term": { "members": "u_1001" } },
        { "term": { "is_recalled": false } }
      ]
    }
  },
  "highlight": {
    "fields": { "text": {} }
  },
  "sort": [
    "_score",
    { "created_at": "desc" }
  ],
  "size": 20
}
```

### 会话内搜索

```json
GET im_messages/_search?routing=c123
{
  "query": {
    "bool": {
      "must": [{ "match": { "text": "计划" } }],
      "filter": [
        { "term": { "conv_id": "c123" } },
        { "term": { "members": "u_1001" } }
      ]
    }
  }
}
```

### @ 我搜索

```json
GET im_messages/_search
{
  "query": {
    "bool": {
      "should": [
        { "term": { "mentioned_users": "u_1001" } },
        { "term": { "has_mention_all": true } }
      ],
      "minimum_should_match": 1,
      "filter": [{ "term": { "members": "u_1001" } }]
    }
  },
  "sort": [{ "created_at": "desc" }]
}
```

### 时间范围

```json
{
  "filter": [
    {
      "range": {
        "created_at": {
          "gte": 1710000000000,
          "lte": 1712000000000
        }
      }
    }
  ]
}
```

## 6.2 索引选择优化

后端根据时间范围选索引：

```go
func selectIndices(from, to time.Time) []string {
    var indices []string
    cur := from
    for !cur.After(to) {
        indices = append(indices, fmt.Sprintf("im_messages_%04d_%02d", cur.Year(), cur.Month()))
        cur = cur.AddDate(0, 1, 0)
    }
    return indices
}

// 查询时只查命中的索引,而不是 alias
GET im_messages_2026_05,im_messages_2026_04/_search
```

不带时间范围的查询：默认查近 3 个月，超出范围提示用户加时间过滤。

## 6.3 查询分级

```
快速搜索: 近 7 天 (热索引,SSD)
普通搜索: 近 30 天
深度搜索: 30天 ~ 1 年
归档搜索: > 1 年 (单独冷集群)
```

## 6.4 分页

### 浅分页（前 1 万条）
```
from + size
```

### 深分页（搜索结果超过 1 万）
```
search_after (推荐)
  上次最后一条的 sort 值作为下页 anchor
  
GET /im_messages/_search
{
  "size": 20,
  "sort": [
    { "created_at": "desc" },
    { "_id": "desc" }
  ],
  "search_after": [1710000000000, "s_99001"]
}
```

不要用 `scroll`，已被弃用。

## 6.5 缓存

### Filter cache
ES 内置，filter 子句自动缓存。**多用 filter 少用 must**。

### 应用层缓存
```
热门查询缓存 5min
"周报"、"计划" 等高频词
```

### 用户最近查询
```
Redis: search:recent:{userId}
LRU 保留 20 条
```

## 6.6 索引 warmup

新索引刚创建时缓存冷，可预热：

```
GET /im_messages_2026_05/_search
{
  "query": { "match_all": {} },
  "size": 0
}
```

---

# 7. 相关性排序

## 7.1 默认排序

ES 用 BM25 默认评分。

```
score = ∑(IDF × TF × normalization)
```

## 7.2 自定义评分

IM 搜索除了文本相关性，还要考虑业务因素：

```json
{
  "query": {
    "function_score": {
      "query": {
        "multi_match": {
          "query": "项目计划",
          "fields": ["text^2", "sender_name"]
        }
      },
      "functions": [
        {
          "filter": { "range": { "created_at": { "gte": "now-7d" } } },
          "weight": 2
        },
        {
          "filter": { "term": { "is_recent_active_conv": true } },
          "weight": 1.5
        },
        {
          "gauss": {
            "created_at": {
              "origin": "now",
              "scale": "30d",
              "decay": 0.5
            }
          }
        }
      ],
      "score_mode": "sum",
      "boost_mode": "multiply"
    }
  }
}
```

## 7.3 排序维度

| 因子 | 权重 |
|---|---|
| 文本相关性 (BM25) | 1.0 |
| 时间衰减 (gauss) | 0.5 |
| 是否当前会话 | +1 |
| 是否高频联系人 | +0.5 |
| @ 我的消息 | +1 |
| 文件类型匹配 | +0.5 |

## 7.4 个性化（高级）

```
用户 A 经常搜"周报"
→ "周报" 相关结果 boost
→ 个性化排序模型 (LTR)
```

实现：Learning to Rank 插件，基于用户点击行为训练模型。

## 7.5 排序模式

```
默认: 按相关性
最新: 按时间倒序
最旧: 按时间正序

UI 提供切换
```

---

# 8. 隐私与权限

## 8.1 权限模型

```
能搜到的消息 = 自己有权访问的所有消息
- 自己发的私聊消息
- 收到的私聊消息
- 加入的群里的消息（加入后的，看策略）
- 自己被 @ 的消息
```

## 8.2 实现

通过 `members` 字段过滤：

```json
"filter": [{ "term": { "members": "<current_user_id>" } }]
```

后端 Search API 强制注入此过滤，客户端无法绕过。

## 8.3 退群后的搜索

```
策略 A: 退群即不可搜（推荐合规）
  - 退群事件 → 删除该用户在该群所有索引中的 members 项
  - 代价: 万人群退一个人要更新很多文档
  - 优化: 标记 ban_user 字段 + 查询时过滤
  
策略 B: 退群保留历史搜索权（用户体验好）
  - 不动索引
  - 但合规风险
  
推荐 A，加优化:
  - 不实时改 members
  - 加 left_users 字段 + 退群时间
  - 查询时: members 包含 + (left_users 不包含 OR 消息时间 < 退群时间)
```

## 8.4 撤回消息

```
撤回后不能搜
  - 撤回事件 → ES 标记 is_recalled=true
  - 查询 filter: { "term": { "is_recalled": false } }
```

## 8.5 内容脱敏

```
搜索结果高亮时:
  - 手机号脱敏: 138****8888
  - 身份证脱敏
  - 银行卡脱敏

存储时已脱敏 vs 展示时脱敏:
  推荐展示时,保留原始全文便于精确搜索
```

## 8.6 数据合规

```
GDPR / 等保 要求:
  - 用户注销 → 删除其所有索引数据
  - 数据出境 → 跨地域索引隔离
  - 审计 → 搜索行为日志
```

---

# 9. 容量与成本

## 9.1 容量估算

```
日消息量: 200 亿条
单条索引大小: ~500 字节
日索引大小: 10 TB
月索引: 300 TB (主分片)
+ 1 副本: 600 TB

保留 1 年: 7.2 PB
```

## 9.2 成本优化

### 冷热分离
```
hot:    近 7 天 - SSD - 高 QPS
warm:   7~30 天 - SSD - 中 QPS
cold:   30~365 天 - HDD - 低 QPS
frozen: > 1 年 - 对象存储 - 极低 QPS
```

ILM (Index Lifecycle Management) 自动管理：

```json
PUT _ilm/policy/im_messages_policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": { "max_size": "100GB", "max_age": "30d" }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 16 },
          "forcemerge": { "max_num_segments": 1 },
          "allocate": { "include": { "tier": "warm" } }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "freeze": {},
          "allocate": { "include": { "tier": "cold" } }
        }
      },
      "delete": {
        "min_age": "365d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

### 不索引非搜索字段
```
url, file_url 等设 "index": false
减小索引大小
```

### 压缩
```
"index.codec": "best_compression"
节省 30~50% 存储,代价是查询慢一点
```

## 9.3 节点规格

```
hot 节点:    32C / 128GB / 4TB SSD × 50 个
warm 节点:   16C / 64GB / 8TB SSD × 30 个
cold 节点:   16C / 32GB / 16TB HDD × 20 个
master 节点: 8C / 32GB / 100GB SSD × 3 个 (专用)
```

---

# 10. 监控与运维

## 10.1 关键指标

| 指标 | 告警 |
|---|---|
| `cluster.status` | 非 green |
| `indices.indexing.index_current` | > 阈值 |
| `indices.search.query_time_in_millis` (P99) | > 200ms |
| `nodes.jvm.mem.heap_used_percent` | > 75% |
| `nodes.fs.available_in_bytes` | < 20% |
| `indices.refresh.total_time_in_millis` | 异常增长 |
| `indexer_lag` (Kafka) | > 10K |

## 10.2 慢查询日志

```yaml
index.search.slowlog.threshold.query.warn: 1s
index.search.slowlog.threshold.query.info: 500ms
```

## 10.3 索引管理

```bash
# 查看索引
GET _cat/indices/im_messages_*?v&s=index

# 查看分片分布
GET _cat/shards/im_messages_*?v

# 强制 merge
POST im_messages_2026_03/_forcemerge?max_num_segments=1

# 手动 rollover
POST im_messages/_rollover
```

## 10.4 reindex

字段变更时需要 reindex：

```json
POST _reindex
{
  "source": { "index": "im_messages_2026_05_v1" },
  "dest":   { "index": "im_messages_2026_05_v2" }
}
```

通过 alias 切换：

```json
POST _aliases
{
  "actions": [
    { "remove": { "index": "im_messages_2026_05_v1", "alias": "im_messages" } },
    { "add":    { "index": "im_messages_2026_05_v2", "alias": "im_messages" } }
  ]
}
```

## 10.5 备份

```
SLM (Snapshot Lifecycle Management):
  - 每天快照到 S3/OSS
  - 保留 30 天
  - 灾难恢复用
```

---

**文档结束** | Version 1.0