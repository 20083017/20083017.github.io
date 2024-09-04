
```
#查看SSL版本
[root@cnki-120-145-80 ~]# openssl version
OpenSSL 1.0.2k-fips  26 Jan 2017

#获取旧的openssl命令的位置
[root@cnki-120-145-80 ~]# which openssl
/usr/bin/openssl
[root@cnki-120-145-80 ~]# whereis openssl
openssl: /usr/bin/openssl /usr/lib64/openssl /usr/include/openssl /usr/share/man/man1/openssl.1ssl.gz


#================ 升级SSL ==============
#1.进入opt 目录
cd /opt

#2.下载Openssl
wget https://www.openssl.org/source/openssl-3.0.4.tar.gz

#3.解压
tar -xvf openssl-3.0.4.tar.gz

#4.进入解压后的目录
cd openssl-3.0.4

#5.编译(这一步可能会报错,请看报错1、报错2、报错3)
#./config --prefix=/usr/local/openssl shared zlib

./config --prefix=/usr/local/openssl shared 
#make depend

#6.这一步可能会报错，请看报错2
#make & make install
make
#make test 
sudo make install


#7.备份之前的ssl
mv /usr/bin/openssl /usr/bin/openssl.bak
mv /usr/include/openssl /usr/include/openssl.bak

#8.将默认的openssl命令指向新的
ln -s /usr/local/openssl/bin/openssl /usr/bin/openssl
ln -s /usr/local/openssl/include/openssl /usr/include/openssl

#9.更新动态链接库数据
echo "/usr/local/openssl/lib64" >> /etc/ld.so.conf

#10.加载配置
ldconfig -v


#11.查看是否升级成功
[root@cnki-120-145-80 openssl-3.0.4]# openssl version
OpenSSL 3.0.4 21 Jun 2022 (Library: OpenSSL 3.0.4 21 Jun 2022)

#12. openssl: error while loading shared libraries: libssl.so.1.1: cannot open shared object file: No such file or directory
  ln -s /usr/local/openssl/lib/libssl.so.1.1 /usr/lib/libssl.so.1.1
  ln -s /usr/local/openssl/lib/libssl.so.1.1 /usr/lib64/libssl.so.1.1
  ln -s /usr/local/openssl/lib/libcrypto.so.1.1 /usr/lib64/libcrypto.so.1.1
```


执行编译时可通过 -j 选项指定并行的任务数量来加快速度，通常我们将其设置为编译机器的 CPU 数量，可以结合 nproc 命令使用：
注意，python编译时，不需要使用root用户，使用user用户即可。。。。
```

./configure --prefix=/home/work/local/python-3.8.6/ --with-openssl=/usr/local/openssl

make -s -j "$(nproc)"

make install

install之后，prefix 路径
生成python二进制文件


```


### 不同的ssl库性能对比

```
wolfssl 32位armv7平台交叉编译

$ ./configure \
    --host=arm-linux-gnueabihf \
    CC=/home/liuquan6/.toolchain/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-9.1.0-gcc  \
    AR=/home/liuquan6/.toolchain/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-9.1.0-ar  \
    STRIP=/home/liuquan6/.toolchain/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-9.1.0-strip  \
    RANLIB=/home/liuquan6/.toolchain/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/gcc-sigmastar-9.1.0-2019.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-9.1.0-ranlib  \
    --prefix=/mnt/e/test/wolfssl/output \
    CFLAGS="-march=armv8-a  \
        -DHAVE_PK_CALLBACKS -DWOLFSSL_USER_IO -DNO_WRITEV -DTIME_T_NOT_64BIT" \
    --disable-filesystem --enable-fastmath --enable-sp-asm\
    --disable-shared
$ make
$ make install


openssl 32位 armv7 交叉编译
某些平台 不禁用 asm 会导致编译错误！！！！
tar -xvf openssl-3.0.12.tar.gz
cd openssl-3.0.12/

/* 安装目录设为当前目录下的tmp，no-asm、shard的功能--阅读INSTALL.md */
./config no-asm shared --prefix=$PWD/tmp	
vi Makefile
	/CROSS_COMPILE			/* 搜索、配置为自己的交叉编译工具链, 例：arm-linux- */
	/-m64					/* 搜索-m64，将“-m64”删除 */
	:wq						/* 保存并退出Makefile */
make
make install
```

### 性能优化策略
```
1、指令优化-aesni、aesce etc
2、硬件加密
3、asm
other、 加密block size 也影响速度，优化block size？！！
```





















