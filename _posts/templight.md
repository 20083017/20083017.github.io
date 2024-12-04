
### 编译期 模版元编程调试   

#### 编译生成 templight
下载 llvm-project     
进入 clang/tools 目录    
下载 templight 工程    

返回 llvm-projects目录     


cmake -S llvm -B build -DLLVM_ENABLE_PROJECTS=clang -DCMAKE_BUILD_TYPE=Release   

cd build    

make clang    

#### templight 使用

