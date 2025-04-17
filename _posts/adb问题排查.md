

```
另附解决adb端口占用问题解决：
1、adb nodaemon server  查看abd服务是否正常
2、netstat -ano | findstr "5037"  查看adb端口占用情况
3、tasklist|findstr "XXX" 查看占用进程名
4、kill掉占用端口的进程
```


![image](https://github.com/user-attachments/assets/897c2100-7f47-4dcc-94e3-e63b1919c913)
