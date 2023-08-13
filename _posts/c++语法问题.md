 ### lamda表达式捕获问题

 lamda表達式
 = 捕獲所有的變量
 a = a_ 只捕獲單個變量

 部分成員變量的修改，需要使用&捕獲，而非=捕獲


windows测试的情况下，针对内存进行快照，对 thread lamda表达式之前，lamda表达式内，return 0 分别进行快照拍照，查看内存使用情况。   
lamda表达式内使用的内存，只捕获单个变量，比捕获全部变量，内存使用多。

#### [=] 捕获   
![BwOgBBIbrm](https://github.com/20083017/20083017.github.io/assets/8308226/d039e8e6-9ac3-4886-a040-5b2dbdff91c6)

#### [mmp=mp]捕获
![5mSmqms8X9](https://github.com/20083017/20083017.github.io/assets/8308226/f61ef4e0-f156-479d-9902-d5f2bdf178d7)

#### 测试程序
```
#include<thread>
#include <map>
#include <vector>
#include <iostream>

int main(int argc, const char *argv[]) {

     std::map<int,std::string> mp;
     for(int i = 0; i < 10000; ++i)
     {
     mp.emplace(i,std::to_string(i));
     }

     std::vector<std::string> arr;
     for(int i = 0; i < 10000; ++i)
     {
       arr.emplace_back(std::to_string(i));
     }
      // test1
     std::thread t = std::thread([=](){

     });
     // // test2
     //std::thread t = std::thread([mmp=mp](){

     //});

     if (t.joinable())
     {
       t.join();
     }


     for (int i = 0; i < 100; ++i)
     {
       std::cout << std::endl;
     }
return 0;
}
```
