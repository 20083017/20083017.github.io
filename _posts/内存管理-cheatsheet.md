### freelist 

```

```


leveldb 

ptmalloc
jemalloc
tcmalloc

brpc
task area
iobuf


### 局部性原理padding

1) 规避处理方式
a、 增大数组元素的间隔使得不同线程存取的元素位于不同 cache line，空间换时间
b、 在每个线程中创建全局数组各个元素的本地拷贝，然后结束后再写回全局数组

从代码设计角度，要考虑清楚类结构中哪些变量是不变，哪些是经常变化，哪些变化是完全相互独立，哪些属性一起变化。假如业务场景中，下面的对象满足几个特点   
```
public class Data{
    long modifyTime;
    boolean flag;
    long createTime;
    char key;
    int value;
}
```
l 当 value 变量改变时，modifyTime 肯定会改变   
l createTime 变量和 key 变量在创建后就不会再变化   
l flag 也经常会变化，不过与 modifyTime 和 value 变量毫无关联   
当上面的对象需要由多个线程同时访问时，从 Cache 角度，当我们没有加任何措施时，Data   
对象所有的变量极有可能被加载在 L1 缓存的一行 Cache Line 中。在高并发访问下，会出现这种问题：   
![image](https://github.com/20083017/20083017.github.io/assets/8308226/11a9c5f5-d796-4926-9232-1030634c35cb)
如上图所示，每次 value 变更时，根据 MESI 协议，对象其他 CPU 上相关的 Cache Line 全部被设置为失效。其他的处理器想要访问未变化的数据(key 和 createTime)时，必须从内存中重新拉取数据，增大了数据访问的开销。   

#### 有效的 Padding 方式

正确方式是将该对象属性分组，将一起变化的放在一组，与其他无关的放一组，将不变的放到一组。这样当每次对象变化时，不会带动所有的属性重新加载缓存，提升了读取效率。在 JDK1.8 前，一般在属性间增加长整型变量来分隔每一组属性。被操作的每一组属性占的字节数加上前后填充属性所占的字节数，不小于一个 cache line 的字节数就可达到要求。   
```
public class DataPadding{
       long a1,a2,a3,a4,a5,a6,a7,a8;//防止与前一个对象产生伪共享
       int value;
       long modifyTime;
       long b1,b2,b3,b4,b5,b6,b7,b8;//防止不相关变量伪共享;
       boolean flag;
       long c1,c2,c3,c4,c5,c6,c7,c8;//
       long createTime;
       char key;
       long d1,d2,d3,d4,d5,d6,d7,d8;//防止与下一个对象产生伪共享
}
```
采用上述措施后的图示:

![image](https://github.com/20083017/20083017.github.io/assets/8308226/26b28c9a-21e6-4296-977d-8a5e10ea5006)




