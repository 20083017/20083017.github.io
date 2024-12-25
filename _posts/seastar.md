

### 编译

#### github 配置

修改  /etc/hosts 添加dns 至 github.com

gcc11 好像不好使，   
修改configure.py 默认编译工具为 clang++， clang14   

```
sudo ./configure.py --mode=debug --cook=fmt
sudo ninja -C build/debug -j4
```

### tcp 测试
```
./tcp_sctp_server_demo
 ./tcp_sctp_client_demo --server 127.0.0.1:10000 --conn=32 --test=rxrx
```

