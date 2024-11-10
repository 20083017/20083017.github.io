

### 编译

#### github 配置

修改  /etc/hosts 添加dns 至 github.com

```
sudo ./configure.py --mode=debug --cook=fmt
sudo ninja -C build/debug -j4
```


