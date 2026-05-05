---
layout:     post
title:      rest_rpc 协议与接口阅读笔记
subtitle:   req/res header & body 字段，以及 register_handler / call 用法
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - RPC
    - rest_rpc
    - 协议
---

>原始笔记结构其实已经比较清晰，但缺少头图、front matter 和小结。这里只做"补全 front matter + 整理小标题层级 + 补一段开头说明"，协议字段表、注释和示例代码全部保持原样。

<img width="752" alt="07227419a14d2d4ed88aeb5322b851a8" src="https://github.com/20083017/20083017.github.io/assets/8308226/7d1acf52-e272-453c-8dac-3501c5eb073e">

## 当前保留内容

### 1. 协议总览

rest_rpc 是 C++ 下的一个轻量 RPC 库，下面分别是请求 / 响应在 header、body 上的字段定义。所有字段表保持原始记录。

#### 1.1 req_header

```req_header
序号  | 类型     | name         | 字节数
1    | uint8_t  | MAGIC_NUM    | 0
2    | uint8_t  | req_type     | 1
3    | uint32_t | buffer_size  | 2-5
4    | uint64_t | req_id       | 6-13
5    | uint32_t | func_id      | 14-17
```

注释:

* MAGIC_NUM 魔数，固定值 39
* req_type ENUM {req_res,sub_pub}
* buffer_size  body的大小
* req_id client发出的第i个请求，i从0开始
* func_id rpc_name的md5值，md5为一种哈希函数，此处采用hash32;rpc_name为register_handler的第一个参数，全局唯一

#### 1.2 req_body

```req_body
序号  | 类型     | name      | 字节数
1    | uint64_t | req_id    | 0
2    | uint8_t  | req_type  | 1
3    | string   | content   | 
5    | uint32_t | func_id   | 
```

注释:

* req_id client发出的第i个请求，i从0开始
* req_type ENUM {req_res,sub_pub}
* content  client.call 函数除第一个参数以外，其他参数的msgpack序列化的结果
* func_id rpc_name的md5值，md5为一种哈希函数，此处采用hash32

#### 1.3 res_header

```res_header
序号  | 类型     | name         | 字节数
1    | uint8_t  | MAGIC_NUM    | 0
2    | uint8_t  | req_type     | 1
3    | uint32_t | buffer_size  | 2-5
4    | uint64_t | req_id       | 6-13
```

注释:

* MAGIC_NUM 魔数，固定值 39
* req_type ENUM {req_res,sub_pub}
* buffer_size  body的大小
* req_id req_header中的req_id

#### 1.4 res_body

```req_body
序号  | 类型     | name      | 字节数
1    | uint64_t | req_id    | 0
2    | uint8_t  | req_type  | 1
3    | string   | content   | 
```

注释:

* req_id req_header中的req_id
* req_type ENUM {req_res,sub_pub}
* content  失败: result_code::FAIL, "unknown function: " + get_name_by_key(key)   
           成功: result_code::OK, result   

### 2. server.register_handler

```
void register_handler(std::string const &name, const Function &f);
```

`register_handler` 中第一个参数即为函数注册名 `rpc_name`。

### 3. client.call

```
auto result = client.call<int>("add", 1, 2);
```

## 后续可补的方向

- 配上一张完整的 req → res 时序图，把 `req_id` / `func_id` 串起来
- 补一段 `sub_pub` 模式（`req_type` 的另一种取值）的字段含义和典型用法
