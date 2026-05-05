---
layout:     post
title:      C++ 常用小技巧三则
subtitle:   读文件到 string、struct 与 ostream 互转、placement new
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - 技巧
    - 速查
---

>原始笔记是三个并列的代码块（`# 标题 + 代码`），没有上下文。这里按三块用途整理，每段代码本身保持不动。

## 当前保留内容

### 1. 读文件内容到 std::string（C++11）

```
#include <fstream>
#include <streambuf>

std::string readFileIntoString2(const std::string& path) {
    auto ss = std::ostringstream{};
    std::ifstream input_file(path);
    if (!input_file.is_open()) {
        LOGGER_DEBUG(gLogApns,
                   "desc=readFileIntoString2 failed!");
    }
    ss << input_file.rdbuf();
    return ss.str();
}
```

### 2. 把 struct 与 ostream / istream 串起来

通过重载 `operator<<` / `operator>>`，让自定义结构体可以直接走流式输出/输入；`operator>>` 里使用一个临时 `values` 做"先读全再赋值"的事务式写入。

```
struct dHeader
{
    uint8_t    blockID;
    uint32_t   blockLen;
    uint32_t   bodyNum;
};

std::ostream& operator<<(std::ostream& out, const dHeader& h)
{
     return out << h.blockID << " " << h.blockLen << " " << h.bodyNum;
}

std::istream& operator>>(std::istream& in, dHeader& h) // non-const h
{
    dHeader values; // use extra instance, for setting result transactionally
    bool read_ok = (in >> values.blockID >> values.blockLen >> values.bodyNum);

    if(read_ok /* todo: add here any validation of data in values */)
        h = std::move(values);
    /* note: this part is only necessary if you add extra validation above
    else
        in.setstate(std::ios_base::failbit); */
    return in;
}
```

### 3. placement new 的标准 4 步

预分配缓冲 → 在缓冲上 placement new → 使用对象 → 显式调用析构 → 释放缓冲：

```
#include 

  void placement_demo()
  { 
    //1. 预分配缓冲
    char * buff = new char [sizeof (Foo) ];  

    //2. 使用 placement new
    Foo * pfoo = new (buff) Foo;  
    
    //使用对象
    unsigned int length = pfoo->size();  
    pfoo->resize(100, 200);

    //3. 显式调用析构函数
    pfoo->~Foo();  
    
    //4. 释放预定义的缓冲
    delete [] buff;  
  }
```

## 后续可补的方向

- "读文件到 string"补一份 C++17 `std::filesystem` + `std::stringstream` 等价写法
- placement new 补对齐（`std::aligned_storage` / `alignas`）的注意事项
