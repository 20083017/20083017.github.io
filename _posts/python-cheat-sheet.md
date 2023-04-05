

远程服务器，执行python脚本，同时将结果写入文件！

nohup python3 run.py |tee -a 1.log &



## 读txt文件
```
f = open("employeeUid.txt")

line = f.readline()

uid_list = []

while line:
    line = line.rstrip()
    line = line.lstrip()
    if line is not None:
        uid_list.append(int(line))
        #print(int(line))
    line = f.readline()
    #print(int(line))
f.close()
```
## dict初始化
```
m = range(2048)
mp1 = dict.fromkeys(m)
```

## 打印dict
```
for v in mp:
    print(str(v) + " " + str(mp[v]))
```
## dict 排序
按值排序   
```
    print(sorted(key_value.items(), key = lambda kv:(kv[1], kv[0]))) 
```
按key排序   
```
    # 字典按键排序
    for i in sorted (key_value) : 
        print ((i, key_value[i]), end =" ")
```
## python 按行执行shell脚本
```
#!/usr/bin/python3

import os
import re


f = open("shell_sql.txt")

line = f.readline()

uid_list = []

while line:
    #line = line.rstrip()
    #line = line.lstrip()
    #if line is not None:
    #    uid_list.append(int(line))
        #print(int(line))
    #line = f.readline()
    #print(int(line))
    os.system(line)
    line = f.readline()
f.close()
```

