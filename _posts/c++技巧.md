# 读文件内容到std::string c++11

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

# cast struct to ostream
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

# placement
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
