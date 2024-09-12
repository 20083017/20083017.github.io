

### crc32

```
folly 主要针对 aarch64（android、linux），x86_64 进行优化
ceph  针对arm、aarch64、x86_64 优化，（simd.cmake文件）
```

### memcpy memset
```
针对 x86_64  aarch64 优化
memcpy.S hook了 memcpy
aarch64  memcpy_select_aarch64.cpp hook了memcpy
```

