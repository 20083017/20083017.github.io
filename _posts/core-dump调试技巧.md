# 方法1: dmesg + addr2line

       1. gcc -o taogeSeg -g taogeSeg.c ：生成带有调试信息的可运行文件taogeSeg
       2. dmesg | grep taogeSeg ：获得运行taogeSeg后的出错信息， 你能够将结果理解为日志， 当中的080483c9是一个地址， 正是这个地址出错了
       3. addr2line -e taogeSeg 080483c9 ：将出错地址转换成源码相应的行， 结果为6， 也就是说源码第6行有问题。 一看， 果然是，万恶的*p=0;被揪出来了。

# 方法2: strace + addr2line

![image](https://user-images.githubusercontent.com/8308226/226785100-2fb3ca2d-a189-4f45-98a3-da96af8dcb15.png)


# 方法3: 看代码

# 方法4: log，二分法，夹逼定理

# 方法5: gdb 调试

https://www.qdcto.com/archives/1002#_%E6%9F%A5%E7%9C%8B%E8%A2%AB%E4%BC%98%E5%8C%96%E5%90%8E%E7%9A%84%E5%8F%98%E9%87%8F%E5%80%BC


# 方法6：
对core函数反汇编：disas proc_conn_timeout_limited或加/m同时显示源码

# 方法7:
 i register
       
