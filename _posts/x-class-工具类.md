

hicc::debug::X 是一个专门用来调试 RVO，In-place construction，Copy Elision 等等特性的工具类，它平平无奇，只不过是在若干位置埋点冰打印 stdout 文字而已，这可以让我们直观观察到哪些行为实际上发生了。

X-class 在构造函数的入参部分有相似的构造：

```
namespace hicc::debug {

    class X {
        std::string _str;

        void _ct(const char *leading) {
            printf("  - %s: X[ptr=%p].str: %p, '%s'\n", leading, (void *) this, (void *) _str.c_str(), _str.c_str());
        }

    public:
        X() {
            _ct("ctor()");
        }
        ~X() {
            _ct("dtor");
        }
        X(std::string &&s)
            : _str(std::move(s)) {
            _ct("ctor(s)");
        }
        X(std::string const &s)
            : _str(s) {
            _ct("ctor(s(const&))");
        }
        X &operator=(std::string &&s) {
            _str = std::move(s);
            _ct("operator=(&&s)");
            return (*this);
        }
        X &operator=(std::string const &s) {
            _str = s;
            _ct("operator=(const&s)");
            return (*this);
        }

        const char *c_str() const { return _str.c_str(); }
        operator const char *() const { return _str.c_str(); }
    };

} // namespace hicc::debug
```
