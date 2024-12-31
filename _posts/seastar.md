

### 编译

#### github 配置

修改  /etc/hosts 添加dns 至 github.com

gcc11 好像不好使，   去掉了一些tests的demo 主要是rpc相关的，可以跑起来了。
修改configure.py 默认编译工具为 clang++， clang14,也不好使  

```
sudo ./configure.py --mode=debug --cook=fmt
sudo ninja -C build/debug -j4

sudo ./configure.py --mode=debug --cook=fmt --compile-comman
ds-json --enable-dpdk --dpdk-pmd
```

### tcp 测试
```

默认 posix-stack

./tcp_sctp_server_demo
 ./tcp_sctp_client_demo --server 127.0.0.1:10000 --conn=32 --test=rxrx  连接数太多, 卡住了？
./tcp_sctp_client_demo --server 127.0.0.1:10000 --conn=2 --test=rxrx
```

