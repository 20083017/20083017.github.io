### freelist 

```

```

### 分配大量虚存或者实存
```
        //  大量分配虚拟内存，每次调用分配20Gvoid virtualMemoryTest(){    int sizeVm = 1 * 1024 * 1024 * 1024;    //  1GB    for(int i = 0; i < 20; i++){    //  1GB * 20        void* block = mmap(NULL, sizeVm, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, 0, 0);        memset(block, 1, 1);        list[index++] = block;    }}
//  大量分配物理内存，每次调用申请160Mvoid physicalMemoryTest(){    int size = 8 * 1024 * 1024;     //  8M    for (int i = 0; i < 20; i++) {  //  8M * 20        void *block = malloc(size);        memset(block, 1, size);        list[index++] = block;    }}
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


#### C语言padding

在设计数据结构的时候，尽量将只读数据与读写数据分开，并具尽量将同一时间访问的数据组合在一起。这样 CPU 能一次将需要的数据读入。譬如，下面的数据结构就很不好。

```
struct __a

{

   int id; // 不易变

   int factor;// 易变

   char name[64];// 不易变

   int value;// 易变

};
```

在 X86 下，可以试着修改和调整它

```
#define CACHE_LINE_SIZE 64  //缓存行长度

struct __a

{

   int id; // 不易变

   char name[64];// 不易变

  char __align[CACHE_LINE_SIZE – sizeof(int)+sizeof(name) * sizeof(name[0]) %
CACHE_LINE_SIZE]

   int factor;// 易变

   int value;// 易变   char __align2[CACHE_LINE_SIZE –2* sizeof(int)%CACHE_LINE_SIZE ]
};
```
CACHE_LINE_SIZE–sizeof(int)+sizeof(name)*sizeof(name[0])%CACHE_LINE_SIZE 看起来不和谐，CACHE_LINE_SIZE 表示高速缓存行(64B 大小)。   
__align 用于显式对齐，这种方式使得结构体字节对齐的大小为缓存行的大小。   



内存占用分析

1、编译后程序各区域的大小   

size -A bin   

2、虚拟内存占用分析   

![image](https://github.com/20083017/20083017.github.io/assets/8308226/615d48b4-a6c2-4d3a-8942-907d0c78c9e0)

/proc/$pid/smaps   


```
成员名	含义
Name	进程的名称
Pid	PID。
VmPeak	进程使用的最大虚拟内存，通常情况下它等于进程的内存描述符mm 中的 total_vm.
VmSize	进程使用的虚拟内存，它等于mm->total_vm。
VmLck	进程锁住的内存，它等于mm->locked_vm，这里指使用mlock()锁住的内存。
VmPin	进程固定住的内存，它等于mm->pinned_vm，这里指使用 get_user_page()固定住的内存。
VmHWM	进程使用的最大物理内存，它通常等于进程使用的匿名页面、文件映射页面以及共享内存页面的大小总和。
VmRSS	进程使用的最大物理内存，它常常等于VmHWM，计算公式为 VmRSS= RssAnon+RssFile+RssShmem.
RssAnon	进程使用的匿名页面，通过get_mm_counter(mm，MM_ANONPAGES)获取。
RssFile	进程使用的文件映射页面，通过get_mm_counter(mm, MM_FILEPAGES)获取。
RssShmem	进程使用的共享内存页面，通过get_mm_counter(mm, MM_SHMEMPAGES)获取。
RssFile	进程使用的文件映射页面，通过get_mm_counter(mm, MM_FILEPAGES)获取 RssShmem:进程使用的共享内存页面，通过getmm_counter(mm,MM SHMEMPAGES获取。
VmData	进程私有数据段的大小，它等于 mm->data_vm。
VmStk	进程用户栈的大小，它等于mm->stack_vm。
VmExe	进程代码段的大小，通过内存描述符mm中的start_code和end_code两个成员获取。
VmLib	进程共享库的大小，通过内存描述符mm中的exec_vm和VmExe计算。
VmPTE	进程页表大小，通过内存描述符 mm 中的pgtables_bytes 成员获取。
VmSwap	进程使用的交换分区的大小，通过get_mm_counter(mm，MM_SWAPENTS)获取。
HugetlbPages	进程使用巨页的大小，通过内存描述符 mm 中的 hugetlb_usage成员获取。
https://blog.csdn.net/weixin_39247141/article/details/126273389
```


3、物理内存占用分析   

![image](https://github.com/20083017/20083017.github.io/assets/8308226/6646e78e-e5e5-4fae-843b-a28343068b17)


4、 heap 占用分析   heap_profiler   









