

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
