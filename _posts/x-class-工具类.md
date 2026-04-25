---
layout:     post
title:      hicc::debug::X 调试工具类
subtitle:   一个用来观察 RVO / 拷贝省略 / 就地构造的埋点小类
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - 调试
    - RVO
---

>原始笔记是一段口头描述加一整段代码，结构很平。这里按"用途 / 实现"两块整理，类的实现保持原样。

## 当前保留内容

### 1. 用途

`hicc::debug::X` 是一个专门用来调试 RVO、In-place construction、Copy Elision 等等特性的工具类，它平平无奇，只不过是在若干位置埋点冰打印 stdout 文字而已，这可以让我们直观观察到哪些行为实际上发生了。

X-class 在构造函数的入参部分有相似的构造（默认构造、移动构造、拷贝构造，以及对应的 `operator=`），用以区分每条路径被走到的时机。

### 2. 实现

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

## 后续可补的方向

- 配套一组最小可复现 demo：分别调用按值返回、`emplace`、`std::move` 等，对照 stdout 看走到了哪个 `_ct` 分支
- 加上 NRVO / pre-C++17 强制 RVO / C++17 复制省略的版本差异说明
