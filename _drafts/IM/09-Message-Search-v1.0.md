# 消息搜索引擎设计 v1.0

> 适用：IM 历史消息搜索、聊天记录全文检索、@我聚合查询  
> 选型：Elasticsearch 8.x  
> 目标：万亿级消息、毫秒级查询、写入不阻塞主流程

---

## 目录

1. 设计目标与挑战
2. 索引设计
3. 分片策略
4. 写入链路
5. 查询优化
6. 相关性排序
7. 安全与隔离
8. 容量规划
9. 运维与监控

---

# 1. 设计目标与挑战

## 1.1 业务场景

```
1. 会话内搜索:    "在与张三的聊天里搜 'ES 设计'"
2. 全局搜索:      "我的所有消息中搜 'kubectl'"
3. 联系人搜索:    "搜张三发过的关于 Kafka 的消息"
4. 时间范围:      "上周的所有 @我"
5. 消息类型筛选:  "搜张三发的图片"
6. 高级语法:      AND/OR/NOT/短语
```

## 1.2 挑战

| 挑战 | 说明 |
|---|---|
| 数据量大 | 万亿级消息 |
| 写入高并发 | 50万 QPS |
| 多租户隔离 | 不能跨用户搜到 |
| 时效性 | 新消息秒级可搜 |
| 删除合规 | 撤回/封禁要清理 |
| 成本控制 | 不能每条都全字段索引 |

## 1.3 设计目标

```
写入延迟 P99: < 5s (消息可搜)
查询延迟 P99: < 200ms
查询召回率:   > 95%
存储成本:     原始消息的 1.5x
```

---

# 2. 索引设计

## 2.1 索引拆分策略

### 按时间分索引（推荐）

```
msg_2026_05      ← 2026 年 5 月数据
msg_2026_06      ← 6 月
msg_2026_07      ← 7 月
...
```

**优点**：
- 老数据可整体冷存储 / 删除
- 查询时按时间范围只命中部分索引
- 写入热点集中在最新索引

### 按用户分索引（不推荐）

```
msg_user_{shard}_{date}
```

每个用户独立 shard 太多，元数据爆炸。

### IM 推荐方案

```
msg_{yyyy_MM}        ← 按月分索引
索引内 routing = userId  ← 路由到特定 shard
```

兼顾时间分区和用户隔离。

## 2.2 字段映射

```json
PUT msg_2026_05
{
  "settings": {
    "number_of_shards": 32,
    "number_of_replicas": 1,
    "refresh_interval": "5s",
    "index.codec": "best_compression",
    "index.translog.durability": "async",
    "index.translog.sync_interval": "5s",
    
    "analysis": {
      "analyzer": {
        "im_analyzer": {
          "type": "custom",
          "tokenizer": "ik_smart",
          "filter": ["lowercase", "stop"]
        },
        "im_search_analyzer": {
          "type": "custom",
          "tokenizer": "ik_max_word",
          "filter": ["lowercase"]
        }
      }
    }
  },
  
  "mappings": {
    "properties": {
      "server_msg_id": {
        "type": "keyword"
      },
      "conv_id": {
        "type": "keyword"
      },
      "sender_id": {
        "type": "keyword"
      },
      "recipient_id": {
        "type": "keyword"   // 私聊接收者，群消息为空
      },
      "owner_id": {
        "type": "keyword"   // 这条消息所属用户（搜索权限）
      },
      "msg_type": {
        "type": "keyword"
      },
      "content_text": {
        "type": "text",
        "analyzer": "im_analyzer",
        "search_analyzer": "im_search_analyzer",
        "fields": {
          "raw": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "mention_user_ids": {
        "type": "keyword"
      },
      "has_url": {
        "type": "boolean"
      },
      "has_image": {
        "type": "boolean"
      },
      "has_file": {
        "type": "boolean"
      },
      "file_name": {
        "type": "text",
        "analyzer": "im_analyzer"
      },
      "send_time": {
        "type": "date",
        "format": "epoch_millis"
      },
      "visible_seq": {
        "type": "long"
      },
      "status": {
        "type": "byte"   // 0:normal 1:recalled 2:deleted
      }
    }
  }
}
```

## 2.3 关键设计点

### owner_id 字段（最重要）

每条消息要给**每个能看到它的用户**建一个文档？这会爆炸。

**推荐方案**：消息只索引一份，**搜索时用 conv_id + 权限过滤**。

```
索引一条消息:
  conv_id = "c_123"
  sender_id = "u_1001"

搜索时:
  user U 想搜:
    1. 先查 U 加入了哪些 conv (Redis 缓存)
    2. 在 ES 查: WHERE conv_id IN [...] AND content MATCHES "xxx"
```

**为什么不复制多份**：
- 万人群一条消息要写 1 万份索引
- 写入放大严重
- 撤回/编辑要更新所有副本

### mention_user_ids 字段

```
"@我" 的快速过滤:
  GET msg_*/_search
  {
    "query": {
      "bool": {
        "must": [
          {"term": {"mention_user_ids": "u_1002"}},
          {"range": {"send_time": {"gte": "now-7d"}}}
        ]
      }
    }
  }
```

### content_text 不存原文

```
"index": true,        // 建索引（搜索）
"store": false        // 不存原文（节省）
```

显示时按 `server_msg_id` 回查 MySQL/HBase 拿原文。

## 2.4 索引模板

每月自动创建索引：

```json
PUT _index_template/msg_template
{
  "index_patterns": ["msg_*"],
  "template": {
    "settings": { /* 同上 */ },
    "mappings": { /* 同上 */ }
  },
  "data_stream": {}   // 或不用 data stream，用 alias 管理
}
```

---

# 3. 分片策略

## 3.1 分片数量

```
单 shard 推荐大小: 30~50 GB
单月数据量预估: 32 shard × 50GB = 1.6TB

算法:
  shard 数 = 月数据量 / 50GB
  
50亿消息/月 × 1KB = 5TB → 100 shards
```

## 3.2 副本数

```
生产环境: 1~2 副本
读多写少:  2 副本
读写均衡:  1 副本
```

## 3.3 Routing（路由）

```
PUT msg_2026_05/_doc/abc?routing=u_1001
{ ... }
```

让同一用户的消息落同一 shard，**搜索时只查目标 shard**：

```
GET msg_*/_search?routing=u_1001
```

减少 90% 的 shard 查询。

但群消息怎么办？群消息有多个相关用户...

### 推荐方案：按 conv_id routing

```
routing = hash(conv_id)
```

- 私聊：双方 conv_id 一致 → 同 shard
- 群聊：群内所有消息同 shard
- 用户搜索：先查会话列表 → 多 routing 并行查

```
GET msg_*/_search?routing=conv_1,conv_2,conv_3
{
  "query": {
    "bool": {
      "must": [
        {"terms": {"conv_id": ["conv_1", "conv_2", "conv_3"]}},
        {"match": {"content_text": "xxx"}}
      ]
    }
  }
}
```

## 3.4 索引生命周期管理（ILM）

```json
PUT _ilm/policy/msg_policy
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "1.5TB",
            "max_age": "30d"
          }
        }
      },
      "warm": {
        "min_age": "30d",
        "actions": {
          "shrink": {"number_of_shards": 1},
          "forcemerge": {"max_num_segments": 1},
          "allocate": {"include": {"box_type": "warm"}}
        }
      },
      "cold": {
        "min_age": "180d",
        "actions": {
          "freeze": {},
          "allocate": {"include": {"box_type": "cold"}}
        }
      },
      "delete": {
        "min_age": "365d",
        "actions": {"delete": {}}
      }
    }
  }
}
```

```
hot:    SSD,  最近 30 天
warm:   HDD,  30~180 天
cold:   归档, 180~365 天
delete: 删除, 1 年以上
```

---

# 4. 写入链路

## 4.1 写入架构

```
消息入库
   │
   ▼
Kafka: search.index   (msg.fanout 衍生)
   │
   ▼
SearchIndexer (Consumer)
   │
   ├─ 内容提取
   ├─ 字段构造
   └─ Bulk 写 ES
   │
   ▼
ES Cluster
```

## 4.2 SearchIndexer 实现

```go
type SearchIndexer struct {
    consumer    *kafka.Consumer
    esClient    *elasticsearch.Client
    bulkBuf     []*Document
    bulkSize    int
    flushTimer  *time.Timer
}

func (s *SearchIndexer) Run(ctx context.Context) error {
    for {
        select {
        case <-ctx.Done():
            s.flush()
            return nil
        default:
            msg, err := s.consumer.ReadMessage(100 * time.Millisecond)
            if err != nil {
                continue
            }
            
            doc := s.buildDocument(msg)
            s.bulkBuf = append(s.bulkBuf, doc)
            
            if len(s.bulkBuf) >= s.bulkSize {
                s.flush()
            }
        }
    }
}

func (s *SearchIndexer) buildDocument(msg *kafka.Message) *Document {
    var event MessageEvent
    proto.Unmarshal(msg.Value, &event)
    
    // 内容提取（剥离格式，提取纯文本）
    contentText := extractText(event.Content)
    
    return &Document{
        ID: event.ServerMsgID,
        Index: indexName(event.SendTime),  // msg_2026_05
        Routing: event.ConvID,
        Body: map[string]interface{}{
            "server_msg_id":     event.ServerMsgID,
            "conv_id":           event.ConvID,
            "sender_id":         event.SenderID,
            "msg_type":          event.MsgType,
            "content_text":      contentText,
            "mention_user_ids":  event.MentionUserIDs,
            "has_url":           hasURL(contentText),
            "has_image":         event.MsgType == "image",
            "has_file":          event.MsgType == "file",
            "file_name":         event.FileName,
            "send_time":         event.SendTime,
            "visible_seq":       event.VisibleSeq,
            "status":            0,
        },
    }
}

func (s *SearchIndexer) flush() error {
    if len(s.bulkBuf) == 0 {
        return nil
    }
    
    var bulkBody bytes.Buffer
    for _, doc := range s.bulkBuf {
        meta := map[string]map[string]interface{}{
            "index": {
                "_index":   doc.Index,
                "_id":      doc.ID,
                "routing":  doc.Routing,
            },
        }
        json.NewEncoder(&bulkBody).Encode(meta)
        json.NewEncoder(&bulkBody).Encode(doc.Body)
    }
    
    resp, err := s.esClient.Bulk(bytes.NewReader(bulkBody.Bytes()))
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    
    // 检查每个 item 的错误
    var bulkResp BulkResponse
    json.NewDecoder(resp.Body).Decode(&bulkResp)
    if bulkResp.Errors {
        s.handlePartialFailure(bulkResp)
    }
    
    s.consumer.CommitMessages(...)
    s.bulkBuf = s.bulkBuf[:0]
    return nil
}
```

## 4.3 关键参数

```
bulk size:        500~1000 docs / batch
flush interval:   1 秒（保证时效）
parallel writers: 16 (匹配 ES shard)
retry policy:     指数退避，3 次
```

## 4.4 撤回 / 删除处理

```go
// 撤回事件 → 更新文档 status
func (s *SearchIndexer) handleRecall(event *RecallEvent) {
    s.esClient.Update(
        indexName(event.SendTime),
        event.ServerMsgID,
        map[string]interface{}{
            "doc": map[string]interface{}{"status": 1},
        },
    )
}

// 永久删除 → DELETE
func (s *SearchIndexer) handleDelete(event *DeleteEvent) {
    s.esClient.Delete(
        indexName(event.SendTime),
        event.ServerMsgID,
    )
}
```

## 4.5 消息内容预处理

```go
func extractText(content *MessageContent) string {
    switch content.Type {
    case "text":
        return content.Text
    case "image":
        return content.Caption  // 图片描述
    case "file":
        return content.FileName
    case "rich_text":
        return stripFormatting(content.Blocks)
    case "card":
        return content.Title + " " + content.Subtitle
    default:
        return ""
    }
}
```

## 4.6 重建索引

```
场景: 索引结构变更，需重建

方法 1: Reindex API
POST _reindex
{
  "source": {"index": "msg_2026_05"},
  "dest": {"index": "msg_2026_05_v2"}
}

方法 2: 从 Kafka / DB 重新消费
  Kafka 设置较长 retention
  或从 DB 反向重建
```

---

# 5. 查询优化

## 5.1 典型查询

### 会话内搜索

```json
GET msg_*/_search?routing=conv_123
{
  "query": {
    "bool": {
      "filter": [
        {"term": {"conv_id": "conv_123"}},
        {"term": {"status": 0}}
      ],
      "must": [
        {"match": {"content_text": "kubectl"}}
      ]
    }
  },
  "sort": [
    {"send_time": "desc"}
  ],
  "size": 20,
  "highlight": {
    "fields": {"content_text": {}}
  }
}
```

### 全局搜索（用户视角）

```json
GET msg_*/_search?routing=conv_1,conv_2,...,conv_N
{
  "query": {
    "bool": {
      "filter": [
        {"terms": {"conv_id": ["conv_1", "conv_2", ...]}},
        {"term": {"status": 0}},
        {"range": {"send_time": {"gte": "now-90d"}}}
      ],
      "must": [
        {
          "multi_match": {
            "query": "kubernetes",
            "fields": ["content_text^2", "file_name"],
            "type": "best_fields"
          }
        }
      ]
    }
  },
  "size": 20
}
```

### @我搜索

```json
GET msg_*/_search
{
  "query": {
    "bool": {
      "filter": [
        {"term": {"mention_user_ids": "u_1002"}},
        {"range": {"send_time": {"gte": "now-30d"}}}
      ]
    }
  },
  "sort": [{"send_time": "desc"}],
  "size": 50
}
```

## 5.2 查询优化技巧

### 1. filter 优于 must

```
filter:    无评分,可缓存,快
must:      有评分,慢

只在需要相关性的字段用 must
```

### 2. 限制时间范围

```
默认: 最近 90 天
深度: 最近 1 年
极深: 全部 (单独入口,慢)
```

### 3. 限制返回字段

```json
"_source": ["server_msg_id", "conv_id", "send_time"]
```

只返回必要字段，详情按 ID 回查 DB。

### 4. 避免深分页

```
错误: from=10000, size=20 → 性能爆炸

正确: search_after
{
  "sort": [{"send_time": "desc"}, {"server_msg_id": "desc"}],
  "search_after": [1710000000000, "s_888"]
}
```

### 5. 利用查询缓存

```
filter context 自动缓存
高频 filter 用 term/terms,不用 range
```

## 5.3 高亮

```json
"highlight": {
  "pre_tags": ["<em>"],
  "post_tags": ["</em>"],
  "fields": {
    "content_text": {
      "fragment_size": 100,
      "number_of_fragments": 1
    }
  }
}
```

## 5.4 模糊查询 / 拼写纠错

```json
{
  "match": {
    "content_text": {
      "query": "kuberntes",  // 拼错
      "fuzziness": "AUTO"
    }
  }
}
```

## 5.5 短语查询

```json
{
  "match_phrase": {
    "content_text": {
      "query": "Elasticsearch 设计",
      "slop": 2
    }
  }
}
```

---

# 6. 相关性排序

## 6.1 默认排序

```
按时间倒序: 最新消息优先（IM 主流场景）
```

## 6.2 综合排序（function_score）

```json
{
  "query": {
    "function_score": {
      "query": {
        "match": {"content_text": "kubectl"}
      },
      "functions": [
        {
          "exp": {
            "send_time": {
              "origin": "now",
              "scale": "30d",
              "decay": 0.5
            }
          },
          "weight": 2
        },
        {
          "filter": {"term": {"sender_id": "u_friend"}},
          "weight": 1.5
        }
      ],
      "score_mode": "sum",
      "boost_mode": "multiply"
    }
  }
}
```

## 6.3 排序维度

```
1. 文本相关性 (BM25 默认)
2. 时间衰减 (越新越好)
3. 发送者亲密度 (常聊的人优先)
4. 会话活跃度
5. 消息类型 (文本 > 图片 > 文件)
```

## 6.4 个性化

```
用户最近搜过/点过的关键词 → boost 相关结果
基于用户行为微调
```

---

# 7. 安全与隔离

## 7.1 多租户隔离

```
1. 索引按 app_id 隔离 (大客户独立索引)
2. 查询必须带 app_id filter
3. ES 用户权限按 app 分配
```

## 7.2 用户权限

```
查询前置:
  1. 鉴权用户身份
  2. 查询用户加入的 conv_ids
  3. 过滤条件强制带 conv_ids
  4. 不允许跨用户搜索
```

## 7.3 敏感内容

```
合规要求:
  - 涉政/涉黄消息不入索引
  - 写入前过 内容审核
  - 已索引的违规消息触发删除
```

---

# 8. 容量规划

## 8.1 容量预估

```
日消息量:    20 亿
单文档大小:  500 字节 (索引)
日索引增量:  20亿 × 500B = 1TB
月增量:      30TB
保留 1 年:   360TB

副本 ×2:     720TB
```

## 8.2 节点规划

```
Hot 节点:
  - 数据: 最近 30 天 (30TB × 2 = 60TB)
  - SSD,  16C 64G
  - 单节点 5TB → 12 节点

Warm 节点:
  - 数据: 30~180 天 (180TB)
  - HDD,  16C 64G
  - 单节点 10TB → 18 节点

Cold 节点:
  - 数据: 180~365 天
  - HDD,  低规格
  - 单节点 20TB → 18 节点

Master 节点: 3 个 (奇数)
Coordinator: 4 个 (查询专用)

总计: ~55 节点
```

## 8.3 内存

```
heap: 31GB (不超过 32GB)
filesystem cache: 32GB
```

---

# 9. 运维与监控

## 9.1 关键指标

```
- index rate
- search rate
- indexing latency
- search latency p99
- JVM heap usage
- GC time
- queue rejection
- shard 健康
- 节点数
- 磁盘水位
```

## 9.2 告警

```
P0: 集群 red
P0: 写入失败率 > 5%
P1: 查询延迟 P99 > 1s
P1: 单节点磁盘 > 85%
P2: 索引未及时滚动
```

## 9.3 常见故障

### shard 分配失败

```bash
GET _cluster/allocation/explain

# 常见原因:
# - 磁盘水位
# - 分片限制
# - 节点过滤
```

### 慢查询

```
GET _nodes/hot_threads
GET _tasks?actions=*search*&detailed
```

### 集群升级

```
1. 滚动升级 (一个一个节点)
2. 关闭 shard 重平衡
3. 升级
4. 启动并加入
5. 等 yellow → green
6. 下一个
```

---

**文档结束** | Version 1.0