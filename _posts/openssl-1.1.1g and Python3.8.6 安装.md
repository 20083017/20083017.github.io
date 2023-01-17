
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
