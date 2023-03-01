
```
In [3]: import uuid

In [4]: u = uuid.uuid1()

u = uuid.UUID('2c1af3a6b7f511ed80c21554341098f8')

In [58]: datetime.datetime.fromtimestamp((u.time - 0x01b21dd213814000L)*100/1e9)
Out[58]: datetime.datetime(2010, 9, 25, 17, 43, 6, 298623)
```



https://juejin.cn/post/6923014125652181000#heading-10
