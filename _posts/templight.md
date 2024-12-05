
### 编译期 模版元编程调试   

#### 编译生成 templight

llvm-14 版本  templight14版本

下载 llvm-project     
进入 clang/tools 目录    
下载 templight 工程    

返回 llvm-projects目录     

注意: 指定ninja编译失败后，清理工程，使用make重新编译，可以通过   

gcc 编译可能会遇到问题 
```
主要是一些不识别的编译选项！！！！
clang: error: unknown argument: '-fno-lifetime-dse'
make[2]: *** [tools/clang/tools/templight/lib/CMakeFiles/obj.clangTemplight.dir/build.make:76: tools/clang/tools/templight/lib/CMakeFiles/obj.clangTemplight.dir/TemplightAction.cpp.o] Error 1
make[1]: *** [CMakeFiles/Makefile2:52059: tools/clang/tools/templight/lib/CMakeFiles/obj.clangTemplight.dir/all] Error 2
make: *** [Makefile:156: all] Error 2
```
cmake -S llvm -B build -DLLVM_ENABLE_PROJECTS=clang -DCMAKE_BUILD_TYPE=Release   

cmake -S llvm -B build -DLLVM_ENABLE_PROJECTS=clang -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=/usr/bin/clang -DCMAKE_CXX_COMPILER=/usr/bin/clang++   

cd build    

make clang    

#### templight 使用



#### 网页的搞法
https://cppinsights.io/   
