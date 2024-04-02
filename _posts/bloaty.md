

bloaty  分析

符号
```
bloaty -d symbols -n 0 libmicontinuity.so  > 2.txt
```

文件

```
bloaty -d compileunits -n 0 libsimple_decoder.so > compileunits.txt

```

链接

```
https://blog.csdn.net/weiwei9363/article/details/121475302
```

分析各个段的占比
```
~/.toolchain/sdk_package_MC01/toolchain/bin/aarch64-openwrt-linux-size -A ./libmicontinuity_sdk.so.1.0.4032716
```

smaps 分析 不同库的占比

cat /proc/$pid/smaps
cat /proc/$pid/status
