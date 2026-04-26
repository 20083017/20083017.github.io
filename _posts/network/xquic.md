---
layout:     post
title:      XQUIC 笔记整理
subtitle:   握手流程、传输模式与简单压测结论
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - QUIC
    - XQUIC
    - Network
---

>把原始记录中的握手流程、测试命令和压测结论收敛成一份便于回看的最小笔记。

## 整体流程

XQUIC 的连接过程可以先按四段理解：

1. 初始化：Client / Server 分别创建 UDP socket 和 XQUIC engine
2. 握手：TLS 1.3 跑在 QUIC 上，完成密钥协商
3. 业务传输：走 transport stream 或 HTTP/3 request
4. 关闭：发送 `CONNECTION_CLOSE`，释放连接对象

## 握手时序图

```text
sequenceDiagram
    participant C as Xquic Client
    participant S as Xquic Server

    Note over C,S: 1. Initialization
    C->>C: Create UDP Socket & Engine
    S->>S: Bind UDP Socket & Create Engine

    Note over C,S: 2. Handshake (TLS 1.3 over QUIC)
    C->>S: Initial Packet (ClientHello)
    S->>S: Create Conn Object, Trigger on_conn_create
    S->>C: Initial + Handshake Packets (ServerHello, Cert)
    C->>C: Verify Cert, Derive Keys
    C->>S: Handshake Packet (Finished)
    S->>S: Verify Finished, Trigger on_handshake_finished
    S->>C: Handshake Packet (Finished) + 1-RTT Keys
    C->>C: Trigger on_handshake_finished

    Note over C,S: 3. Data Transfer
    C->>C: Create Stream / Request
    C->>S: 1-RTT Packet
    S->>S: Trigger read callback
    S->>C: Response

    Note over C,S: 4. Teardown
    C->>S: CONNECTION_CLOSE
    S->>C: CONNECTION_CLOSE
```

## 建立连接过程：最值得记住的点

### 1. Client 发起连接

- `xqc_connect()` / `xqc_h3_connect()` 先建立内部连接状态
- 随后发送 QUIC Initial 包，里面带 `ClientHello`

### 2. Server 收包并创建连接对象

- `xqc_engine_packet_process()` 识别到新连接
- 创建 `xqc_connection_t`
- 回调 `on_conn_create`
- 返回 `ServerHello`、证书和握手包

### 3. 双方完成握手

- Client 校验证书、导出密钥、发送 `Finished`
- Server 校验通过后进入 established 状态
- 两边都会触发握手完成回调

### 4. 开始传输业务数据

- transport 模式：创建 stream，走 `xqc_stream_send`
- HTTP/3 模式：创建 request，发送 headers/body

## Server 如何管理多个连接

原始笔记这部分没展开，但从流程上看，关键点是：

- 每个新连接都会在 engine 内对应一个连接对象
- 连接生命周期由收包、定时器和回调共同驱动
- 关闭时通过 `on_conn_close` 把对象从 engine 中移除并释放资源

## transport 模式测试

启动服务端：

```bash
./test_server -p 8843 -c ./server.crt -k server.key
```

启动客户端：

```bash
/mnt/e/BucksClub/xquic/build/tests/test_client -a 127.0.0.1 -p 8843 -t 1 -l d
```

## HTTP/3 模式测试

```bash
./test_client -a 127.0.0.1 -p 8843 -h test.xquic.com -T 0 -l d
```

## 集成 OpenSSL 1.1.1 的一套命令

```bash
mkdir -p ~/build_env && cd ~/build_env
wget https://www.openssl.org/source/openssl-1.1.1w.tar.gz

tar -zxvf openssl-1.1.1w.tar.gz
cd openssl-1.1.1w

./config --prefix=/usr/local/openssl-1.1.1 \
  --openssldir=/usr/local/openssl-1.1.1 \
  shared zlib

make -j$(nproc)
sudo make install
```

## transport / h3 路径差异示意

### HTTP/3

- client：`xqc_h3_connect()`
- server：收到 Initial 后创建连接
- 请求通过 `xqc_h3_request_create()` 创建
- 服务端在 request 回调里读 header/body 并回包

### transport

- client：`xqc_connect(alpn="transport")`
- 握手完成后 `xqc_stream_create()`
- 服务端在 stream 回调里接收数据并返回响应帧

## 压测时关注哪些指标

原始记录里已经提到了几项核心指标：

- 吞吐量（Mbps）
- 平均延迟 / p50 / p95 / p99 / max
- 完成率
- 失败数

还没有直接采集但值得后补的有：

- 每秒成功握手数
- RPS
- 服务端 CPU / 内存占用
- 丢包 / 重传率

## 大文件 vs 小文件压测结论

原始测试给出的核心观察可以收敛成：

1. 数据传输不是主要瓶颈，瓶颈更偏向 TLS 握手排队
2. 文件变大后，吞吐量几乎按比例增长，但延迟变化不明显
3. 100 并发以内表现还不错，500 并发时明显退化
4. 高并发退化的主要问题不是发送大文件，而是连接建立阶段太慢

整理后的结论就是：**单核 Seastar 服务端的并发瓶颈更接近握手能力，而不是纯数据发送能力。**
