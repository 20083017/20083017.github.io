
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
硬件engine -enable-devcryptoeng
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

### cryptodev engine 
对应硬件加密  需要安装cryptodev.ko
![image](https://github.com/user-attachments/assets/f714e814-2148-4daf-a71f-e06cc82646f4)


![image](https://github.com/user-attachments/assets/56ab6e91-789f-475f-8be9-5be04a229c03)

### crytodev example
openvpn ^_^
```
#include <openssl/conf.h>
#include <openssl/des.h>
#include <openssl/err.h>
#include <openssl/evp.h>
#include <openssl/objects.h>
#include <openssl/rand.h>
#include <openssl/ssl.h>

#include <openssl/engine.h>

#if !defined(LIBRESSL_VERSION_NUMBER)
#include <openssl/kdf.h>
#endif
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/provider.h>
#include <openssl/core_names.h>
#endif

int main(int ac, char **av, char **ae)
{

   ENGINE *e = NULL;
    if ((e = ENGINE_by_id("devcrypto")) == NULL) {
        printf("cryptodev engine not found!\n\n");
        return 0;
    }

  const EVP_CIPHER *cipher;
  //unsigned char key[32];
  int len;
  unsigned char tag[16];

  unsigned char key[] = {0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x30, 0x31};//av[1];
  unsigned char iv[] = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b};
  unsigned char data[] = {0x0,0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19,0x1a,0x1b,0x1c,0x1d,0x1e,0x1f,0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x29,0x2a,0x2b,0x2c,0x2d,0x2e,0x2f,0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0x3a,0x3b};

  ERR_load_crypto_strings();

  //encrypt
  EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
  cipher = EVP_aes_256_gcm();

 

  EVP_EncryptInit_ex(ctx, cipher, NULL, NULL, NULL);
  EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, sizeof(iv), NULL);
  EVP_EncryptInit_ex(ctx, NULL, NULL, key, iv);

  len = sizeof(data);
  int h=0;

  EVP_EncryptUpdate(ctx, data, &len, data, len);
  EVP_EncryptFinal(ctx, tag, &h);

  printf("DATA:");
  for (int i = 0; i < sizeof(data); ++i)
    printf("%02X,", data[i]);
  printf("\n");

  EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, sizeof tag, tag);
  printf("TAG:");
  for (int i = 0; i < sizeof(tag); ++i)
    printf("%02X,", tag[i]);
  printf("\n");

  //decrypt
  ctx = EVP_CIPHER_CTX_new();      
  EVP_DecryptInit (ctx, cipher, key, iv);
  EVP_CIPHER_CTX_ctrl (ctx, EVP_CTRL_GCM_SET_TAG, 16, tag);
  EVP_DecryptInit (ctx, NULL, key, iv);
  EVP_DecryptUpdate (ctx, data, &h, data, len);
  printf("DATA:");
  for (int i = 0; i < sizeof(data); ++i)
    printf("%02X,", data[i]);
  printf("\n");
  int dec_success = EVP_DecryptFinal (ctx, data, &h);
  printf("TAG: %d\n", dec_success);

  fflush(stdout);
//   freeCrypto();
  return 0;
}
```















