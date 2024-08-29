
```

/**
 * @brief 单件模式基类, 参考 boost::serialization::Singleton,去除了Debug锁操作 <br />
 *        实例的初始化会在模块载入（如果是动态链接库则是载入动态链接库）时启动 <br />
 *        在模块卸载时会自动析构 <br />
 *
 * Note that this Singleton class is thread-safe.
 * 
 * 增加基于C++11标准 N2660 的实现 优化销毁判定内存区的放置 优化初始化顺序
 *              单例接口返回const的智能指针，不允许替换单例对象
 * @example
 *      // Singleton_class.h
 *      class Singleton_class : public util::design_pattern::Singleton<Singleton_class> {};
 */

#ifndef UTILS_DESIGNPATTERN_SINGLETON_H
#define UTILS_DESIGNPATTERN_SINGLETON_H

#pragma once

#include <atomic>
#include <cstddef>
#include <Memory>
#include <utility>


namespace design_pattern {
namespace details {
template <class T, class Deletor>
inline std::shared_ptr<T> Create_Shared_Ptr(T *ptr, Deletor &&deletor) {
    return std::shared_ptr<T>(ptr, std::forward<Deletor>(deletor));
}
} // namespace details
} // namespace design_pattern

#define UTIL_DESIGN_PATTERN_SINGLETON_NOMAVLBLE(CLAZZ) \
    CLAZZ(CLAZZ &&) = delete;                          \
    CLAZZ &operator=(CLAZZ &&) = delete;

#if defined(__cpp_threadsafe_static_init)
#if __cpp_threadsafe_static_init >= 200806L
#define UTIL_DESIGN_PATTERN_SINGLETON_DATA_IMPL_N2660 1
#endif
#elif defined(__cplusplus)
// @see https://gcc.gnu.org/projects/cxx-status.html
// @see http://clang.llvm.org/cxx_status.html
#if __cplusplus >= 201103L
#define UTIL_DESIGN_PATTERN_SINGLETON_DATA_IMPL_N2660 1
#endif
#elif defined(_MSC_VER) && defined(_MSVC_LANG)
// @see https://docs.microsoft.com/en-us/cpp/build/reference/zc-threadsafeinit-thread-safe-local-static-initialization
#if _MSC_VER >= 1900 && _MSVC_LANG >= 201103L
#define UTIL_DESIGN_PATTERN_SINGLETON_DATA_IMPL_N2660 1
#endif
#endif

#if defined(UTIL_DESIGN_PATTERN_SINGLETON_DATA_IMPL_N2660) && UTIL_DESIGN_PATTERN_SINGLETON_DATA_IMPL_N2660

// @see https://wg21.link/n2660
#define UTIL_DESIGN_PATTERN_SINGLETON_DATA_IMPL(CLAZZ, BASE_CLAZZ)                                 \
private:                                                                                                  \
    template <class TCLASS>                                                                               \
    class Singleton_Wrapper_Permission_T : public TCLASS {  \
                        public:Singleton_Wrapper_Permission_T() { Start();}                                    \
                        ~Singleton_Wrapper_Permission_T() { Stop();}                                                   \
    };                                              \
    class Singleton_Wrapper_T {                                                                     \
    public:                                                                                               \
        using ptr_permission_t = std::shared_ptr<Singleton_Wrapper_Permission_T<CLAZZ> >;                 \
        using ptr_t = std::shared_ptr<CLAZZ>;                                                             \
        static bool is_destroyed__;                                                                       \
        struct Deleter {                                                                                  \
            void operator()(Singleton_Wrapper_Permission_T<CLAZZ> *p) const {                             \
                is_destroyed__ = true;                                                                    \
                ::std::atomic_thread_fence(std::memory_order_release); \
                delete p;                                                                                 \
            }                                                                                             \
        };                                                                                                \
        friend struct Deleter;                                                                            \
        static const ptr_t &Me() {                                                                        \
            static ptr_t data = std::static_pointer_cast<CLAZZ>(                                          \
                ::design_pattern::details::Create_Shared_Ptr(              \
                    new Singleton_Wrapper_Permission_T<CLAZZ>(), Deleter()));                             \
            return data;                                                                                  \
        }                                                                                                 \
    };                                                                                                    \
                                                                                                          \
private:                                                                                                  \
    friend class Singleton_Wrapper_T;
#endif

#define UTIL_DESIGN_PATTERN_SINGLETON_DEF_FUNCS(CLAZZ, BASE_CLAZZ)                     \
    UTIL_DESIGN_PATTERN_SINGLETON_DATA_IMPL(CLAZZ, BASE_CLAZZ)                         \
    BASE_CLAZZ(const BASE_CLAZZ &) = delete;                                                  \
    BASE_CLAZZ &operator=(const BASE_CLAZZ &) = delete;                                       \
    UTIL_DESIGN_PATTERN_SINGLETON_NOMAVLBLE(BASE_CLAZZ)                                      \
public:                                                                                       \
    static CLAZZ &Get_Instance() { return *Singleton_Wrapper_T::Me(); }                 \
    static const CLAZZ &Get_Const_Instance() { return Get_Instance(); }                 \
    static CLAZZ *Instance() { return Singleton_Wrapper_T::Me().get(); }                \
    static const std::shared_ptr<CLAZZ> &Me() { return Singleton_Wrapper_T::Me(); }     \
    static bool Is_Instance_Destroyed() { return Singleton_Wrapper_T::is_destroyed__; } \
                                                                                              \
private:

namespace design_pattern {
template <class T>
class Singleton {
public:
    /**
     * @brief 自身类型声明
     */
    using self_type = T;
    using ptr_t = std::shared_ptr<self_type>;

     Singleton() {}
     ~Singleton() {}

     virtual void Start() {  };
     virtual void Stop() {  };


    UTIL_DESIGN_PATTERN_SINGLETON_DEF_FUNCS(self_type, Singleton)
};
template <class T>
 bool Singleton<T>::Singleton_Wrapper_T::is_destroyed__ = false;

} // namespace design_pattern
#endif

```
