
### 编译期 模版元编程调试   

#### 编译生成 templight

llvm-14 版本  templight14版本

下载 llvm-project     
进入 clang/tools 目录    
下载 templight 工程    

返回 llvm-projects目录     

注意: 指定ninja编译失败后，清理工程，使用make重新编译，可以通过   

cmake -S llvm -B build -DLLVM_ENABLE_PROJECTS=clang -DCMAKE_BUILD_TYPE=Release   

cd build    

make clang    

#### templight 使用



#### 网页的搞法
https://cppinsights.io/   
