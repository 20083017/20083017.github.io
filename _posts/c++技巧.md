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
