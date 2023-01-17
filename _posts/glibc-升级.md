安装最新的TensorFlow（>=1.10）后，载入TensorFlow时提示Glibc版本过低，需要升级到指定版本。

ImportError: /lib64/libc.so.6: version `GLIBC_2.17' not found (required by /usr/local/python3.6/lib/python3.6/site-packages/tensorflow/python/_pywrap_tensorflow.so)
1、下载、解压：

cd /usr/local
wget https://ftp.gnu.org/gnu/glibc/glibc-2.17.tar.gz

tar -zxvf glibc-2.17.tar.gz
在 https://ftp.gnu.org/gnu/glibc/ 或者 http://ftp.twaren.net/Unix/GNU/gnu/libc/ 里选择下载 对应版本.

2、编译、安装：

cd glibc-2.17
./configure --prefix=/usr --disable-profile --enable-add-ons --with-headers=/usr/include --with-binutils=/usr/bin
此时报如下错误信息：

 

意思为必须在一个新目录下编译。解决方法：新建一个目录，然后进入该目录，用绝对路径编译。

cd /usr/local/glibc-2.17

mkdir build
cd build

../configure --prefix=/usr --disable-profile --enable-add-ons --with-headers=/usr/include --with-binutils=/usr/bin
然后

# make
# make install
3、到这一步如果出现ls目录不能使用，则/lib64/libc.so.6未更新。需要重建软连接，但是先解决命令不能使用问题。

命令恢复：

# LD_PRELOAD=/lib64/libc-2.17.so
设置软连接，先删除旧的：

# rm /lib64/libc.so.6
# ln -s /lib64/libc-2.17.so /lib64/libc.so.6
查看glib详情，执行：

# strings /lib64/libc.so.6 |grep GLIBC_

GLIBC_2.2.5
GLIBC_2.2.6
GLIBC_2.3
GLIBC_2.3.2
GLIBC_2.3.3
GLIBC_2.3.4
GLIBC_2.4
GLIBC_2.5
GLIBC_2.6
GLIBC_2.7
GLIBC_2.8
GLIBC_2.9
GLIBC_2.10
GLIBC_2.11
GLIBC_2.12
GLIBC_2.13
GLIBC_2.14
GLIBC_2.15
GLIBC_2.16
GLIBC_2.17
GLIBC_PRIVATE
可以看到支持的最高版本。
4、检查：

# ldd --version
ldd (GNU libc) 2.17
Copyright (C) 2012 Free Software Foundation, Inc.
This is free software; see the source for copying conditions. There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
Written by Roland McGrath and Ulrich Drepper.
