
### xquic 握手流程
```
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

    Note over C,S: 3. Data Transfer (Example: Transport Mode)
    C->>C: Create Stream, Send Data
    C->>S: 1-RTT Packet (Stream Data)
    S->>S: Trigger on_stream_read
    S->>C: 1-RTT Packet (Echo Data)
    C->>C: Trigger on_stream_read, Verify Echo

    Note over C,S: 4. Teardown
    C->>S: CONNECTION_CLOSE
    S->>C: CONNECTION_CLOSE
    C->>C: Trigger on_conn_close, Cleanup
    S->>S: Trigger on_conn_close, Cleanup
```

### 建立连接过程
```
整个流程可以分为 初始化阶段、握手阶段 和 业务交互阶段。以下是详细的步骤解析：

1. 初始化阶段 (Initialization)
在连接真正开始之前，Client 和 Server 各自准备好环境。

Server 端 (XquicServer::start)
创建 UDP Socket: 创建一个非阻塞的 UDP Socket 并绑定到指定端口（默认 8443）。
创建 XQuic Engine: 调用 xqc_engine_create 创建服务器引擎。
注册回调：包括写 Socket (write_socket)、定时器 (set_event_timer)、日志等。
配置 SSL：加载证书 (cert.crt) 和私钥 (key.key)。
注册应用层协议 (ALPN):
如果启用 -T (Transport Only)，注册 "transport" ALPN，绑定 Stream 级别的回调（读/写/关闭）。
否则，初始化 HTTP/3 上下文 (xqc_h3_ctx_init)，绑定 Request 级别的回调。
进入事件循环: event_base_dispatch 开始监听 Socket 可读事件。
Client 端 (XquicClient::start)
创建 UDP Socket: 创建非阻塞 UDP Socket（通常不 bind 特定端口，由系统分配 ephemeral port）。
创建 XQuic Engine: 创建客户端引擎，配置拥塞控制算法（如 BBR）、日志回调等。
准备连接参数:
解析服务器地址 (127.0.0.1:8443)。
读取本地的 Session Ticket 和 Transport Parameters（用于 0-RTT 加速，如果是首次连接则忽略）。
发起连接请求:
调用 xqc_connect (Transport 模式) 或 xqc_h3_connect (HTTP/3 模式)。
关键点：此时并没有发送数据包，只是内部生成了初始的连接状态和 Initial Packet 数据。
2. 握手阶段 (Handshake Phase)
这是连接建立的核心，涉及多次 UDP 包的往返 (RTT)。

Step 1: Client 发送 Initial 包 (C -> S)
触发: xqc_connect 返回后，Client 内部生成了 Initial Packet。
发送:
Client 的 Event Loop 检测到需要发送数据（或者通过 write_socket 回调立即触发）。
xqc_client_write_socket_tramp -> XquicClient::write_socket -> sendto。
数据包包含：QUIC Header (Initial Type), Crypto Frame (TLS ClientHello)。
内容: ClientHello 包含了支持的加密套件、QUIC 版本、以及随机数。
Step 2: Server 接收并处理 (S)
接收: Server 的 on_socket_event 触发 process_socket_read。
处理:
调用 xqc_engine_packet_process。
XQuic 引擎解析 UDP Payload，识别出这是一个新的 Initial Packet。
创建连接对象: Server 内部创建一个新的 xqc_connection_t 对象。
回调触发: xqc_server_conn_create_notify_tramp -> XquicServer::on_conn_create_notify。
响应:
Server 解析 ClientHello，生成 ServerHello、证书、密钥交换参数。
Server 构造 Initial Packet 和 Handshake Packet。
通过 write_socket 回调发送回 Client。
Step 3: Client 接收 Server 响应 (C)
接收: Client 的 process_socket_read 收到 Server 的包。
处理: xqc_engine_packet_process 处理包。
验证证书（如果开启了 verify_cert_）。
计算共享密钥。
升级加密级别（从 Initial Key 升级到 Handshake Key）。
发送 Finish: Client 发送包含 Finished 消息的 Handshake Packet，证明握手完成。
Step 4: Server 确认握手 (S)
接收: Server 收到 Client 的 Finished。
完成:
验证 Finished MAC。
握手成功。
回调触发: xqc_server_conn_handshake_finished_tramp -> XquicServer::on_conn_handshake_finished。
此时，连接正式建立 (Established)，可以开始传输应用数据。
Step 5: Client 确认握手完成 (C)
回调触发: xqc_client_conn_handshake_finished_tramp -> XquicClient::on_conn_handshake_finished。
动作:
打印 DCID/SCID。
发送 Ping 包保持活跃。
关键: 如果之前没有发送业务数据，此时可能会触发初始请求的发送（取决于代码逻辑，通常在 start 的最后部分已经创建了 Stream 并尝试发送）。
3. 业务交互阶段 (Data Transfer)
握手完成后，双方通过 Stream 或 Request 交换数据。

场景 A: Transport Mode (纯 QUIC 流)
Client 创建 Stream:
xqc_stream_create 创建一个双向流。
调用 send_stream_data -> xqc_stream_send。
数据被分片放入发送队列，通过 write_socket 发出。
Server 接收数据:
Server 收到数据包，引擎解析出 Stream Frame。
回调触发: xqc_server_stream_read_notify_tramp -> XquicServer::on_stream_read_notify。
Server 调用 xqc_stream_recv 读取数据。
Server 回复 (Echo):
Server 在 on_stream_read_notify 中直接调用 xqc_stream_send 将收到的数据发回。
Client 接收回复:
Client 收到数据，触发 on_stream_read_notify。
调用 xqc_stream_recv 读取并校验（如果开启了 echo_check_）。
场景 B: HTTP/3 Mode
Client 创建 Request:
xqc_h3_request_create 创建一个 HTTP/3 请求对象。
调用 send_request。
发送 Headers (:method, :path 等) 和 Body。
Server 处理 Request:
Server 收到 Headers，触发 on_request_read_notify (Flag: READ_HEADER)。
Server 收到 Body，触发 on_request_read_notify (Flag: READ_BODY)。
Server 构造响应：xqc_h3_request_send_headers (200 OK) + xqc_h3_request_send_body。
Client 接收 Response:
Client 收到 Headers，触发 on_request_read_notify。
Client 收到 Body，触发 on_request_read_notify。
请求结束，触发 on_request_close_notify。
4. 连接关闭 (Teardown)
主动关闭:
Client 或 Server 调用 xqc_conn_close。
发送 CONNECTION_CLOSE Frame。
被动关闭:
对端收到 CONNECTION_CLOSE，停止发送数据。
回调触发: on_conn_close_notify。
打印统计信息 (Stats: 发送包数、丢包数、RTT 等)。
释放资源 (free(user_conn), xqc_engine_destroy 等)。
Client 端通常会调用 event_base_loopbreak 退出事件循环。
```

### server 端如何管理 多个连接的？

```

```


###  transport 连接

```
./test_server -p 8843 -c ./server.crt -k server.key
```
```
/mnt/e/BucksClub/xquic/build/tests/test_client -a 127.0.0.1 -p 8843 -t 1 -l d
```


###  h3连接
```
./test_client -a 127.0.0.1 -p 8843 -h test.xquic.com -T 0 -l d
```

### 整合openssl 1.1.1
```
# 1. 创建工作目录并下载源码 (建议去官网查看最新的 1.1.1 子版本，如 1.1.1w)
mkdir -p ~/build_env && cd ~/build_env
wget https://www.openssl.org/source/openssl-1.1.1w.tar.gz

# 2. 解压
tar -zxvf openssl-1.1.1w.tar.gz
cd openssl-1.1.1w

# 3. 配置编译选项
# --prefix 指定安装目录，shared 生成动态库
./config --prefix=/usr/local/openssl-1.1.1 --openssldir=/usr/local/openssl-1.1.1 shared zlib

# 4. 编译并安装
# -j$(nproc) 表示使用多核并行编译，加快速度
make -j$(nproc)
sudo make install
```

