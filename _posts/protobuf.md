

### 生成 pb.cc

protoc -I=Proto文件路径 –cpp_out=指定输出.h和.cc的目录 Proto文件，也可以使用protoc -h 查看更多帮助。
格式：protoc -I = proto文件路径 --cpp_out = 输出文件路径 proto文件名

### protobuf-lite

```
我在网上查了一下：

option optimize_for = LITE_RUNTIME;
      optimize_for是文件级别的选项，Protocol Buffer定义三种优化级别SPEED/CODE_SIZE/LITE_RUNTIME。缺省情况下是SPEED。

      SPEED: 表示生成的代码运行效率高，但是由此生成的代码编译后会占用更多的空间。

      CODE_SIZE: 和SPEED恰恰相反，代码运行效率较低，但是由此生成的代码编译后会占用更少的空间，通常用于资源有限的平台，如Mobile。

      LITE_RUNTIME: 生成的代码执行效率高，同时生成代码编译后的所占用的空间也是非常少。这是以牺牲Protocol Buffer提供的反射功能为代价的。因此我们在C++中链接Protocol Buffer库时仅需链接libprotobuf-lite，而非libprotobuf。在Java中仅需包含protobuf-java-2.4.1-lite.jar，而非protobuf-java-2.4.1.jar。

      SPEED和LITE_RUNTIME相比，在于调试级别上，例如 msg.SerializeToString(&str) 在SPEED模式下会利用反射机制打印出详细字段和字段值，但是LITE_RUNTIME则仅仅打印字段值组成的字符串;

     因此：可以在程序调试阶段使用 SPEED模式，而上线以后使用提升性能使用 LITE_RUNTIME 模式优化。
```


### 动态库Or静态库讨论

```
Protobuf是Google的一个开源项目，它的大部分代码是用C++写的。当别的程序想要使用protobuf时，既可以采用动态链接，也可以采用静态链接。Google内部主要是采用静态链接为主。而在Linux的世界里，大部分发行版都把Protobuf编译成了动态库。

最佳实践
如果你的Project本身是一个动态库，那么你应该避免在它的公开接口中用到任何protobuf的符号，并且采用静态链接到protobuf的方式。同时你应该在dllmain中调用google::protobuf::ShutdownProtobufLibrary()来清理protobuf使用过内存。
如果你的Project本身是一个静态库，那么决定权不在你手里，而且最终把你的静态库编译成PE/ELF文件的那个人手里。但是你需要在你的build system中留出接口让他可以告知你这个信息。
如果你的Project本身是一个动态库，并且你公开接口中用到了protobuf的符号，那么你必须动态链接到protobuf。 否则当你跨DLL传送protobuf的对象时，如果这个对象在A.DLL中创建，但是在B.DLL中被销毁，那么就会导致程序崩溃。因为当你采用静态链接到Protobuf时，每个DLL内部都有一个protobuf的副本，并且protobuf内部有自己的内存池。跨DLL传输对象就会导致该对象可能在不属于自己的内存池中被释放。

动态链接的注意事项
首先，不推荐在Windows上这么做。 因为protobuf本身是基于C++的，而Windows上DLL的导出符号应该都是C风格的，不应含有任何STL、std::string这样的东西。 如果你一定要这么做，那么你就会收到C4251警告。这是一个level 1的警告，属于最高严重等级。
如果你决定动态链接到protobuf，并且目标平台是Windows操作系统，那么你应该在编译你的project的源代码的时候"#define PROTOBUF_USE_DLLS"。 这样链接器才知道应该使用dllimport的方式去寻找protobuf的符号。 Linux不需要这么做。但是Linux需要注意把code编译成PIC的。 同时，在Windows上需要注意所有代码必须采用动态链接到CRT，而不能采用静态链接。 这条适用于libprotobuf.dll自身以及它的所有使用者。

无论是Windows还是Linux，动态链接带来的另一个问题是：从.proto生成的那些C/C++代码可能也需要被编译成动态库共享。因为protobuf本身有一个global的registry。每个message type都需要去那里注册一下，而且不能重复注册。所以，假如你在A.DLL中定义了某些message type，那么B.DLL就只能从A.DLL的exported的DLL interface中使用这些message type, 而不能从proto文件中重新生成C/C++代码并包含到B.DLL里去。并且B.DLL也不能私自的去修改、扩展这个message type。据说换成protobuf-lite就能避免这个问题，但是Google官方并没有对此表态。

另外，protobuf动态库自身不能被unload然后reload。 这个限制让我很意外，但是Google自己说他们在设计的时候从来没考虑过这样的使用场景。不过，在Linux上这其实是很常见的事情，GLIB自身都不支持unload。

糟糕的用例：Tensorflow
首先，tensorflow作为一个python的plugin,它必须是动态库，不能是静态库。
Tensorflow选择了静态链接到protobuf。
Tensorflow想要支持动态加载plugin。每个plugin是一个动态库。
plugin本身需要访问Tensorflow的接口，而这些接口常常又含有protobuf的符号。Tensorflow会暴露(provide) libprotobuf 的部分符号。如果这个plugin需要的符号恰好在tensorflow中都能找到，那么很好。 但事情并非总是如此， 因为Tensorflow它只有一个partial的libprotobuf，它只包含它自己所必须的那部分protobuf的code。当这个plugin想要的超出了tensorflow所能提供的范畴，写plugin的人就会尝试把protobuf加到link command中。这样就会变得非常非常危险，程序随时会崩溃。因为它会在两个不同的protobuf副本之间传送protobuf的对象。 所以，不要看到“unresolved external symbol”就不动脑子的把缺的库加上，有时候这个错误代表的是更深层次的问题。

糟糕的用例： cmake
cmake 3.16做了一个火上浇油的事情：当你使用find_package(Protobuf)的时候，你需要提前知道你找到的究竟是动态库还是静态库，如果是静态库那么你需要设置Protobuf_USE_STATIC_LIBS成OFF，否则在Windows上链接会失败。请注意： 不是cmake告诉你它找到的是什么，而是你要主动告诉它，它找到的会是什么。
```
