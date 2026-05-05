---
layout:     post
title:      纯 C++ 写一个最小可用的 TimerThread
subtitle:   只用 thread / mutex / condition_variable 的简化版本与设计取舍
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - Thread
    - Timer
---

>原始笔记是繁体中文的一段连续叙述加完整代码，这里整理成「需求 / 接口 / 实现 / 设计取舍」四块，原始代码基本保留。

## 1. 设计目标

有时候不想直接用平台提供的 Timer API，更希望用纯 C++ 写一个最小可用的版本，至少满足以下三点：

1. **不过度设计**：只提供「定时执行某个函数」的最基本能力。
2. **可随时停止**：关闭程序时不必等到定时时间到才能退出。
3. **task 内部能感知是否被中止**：定时任务自己执行较久时，可以在中间检查点判断 Timer 是否已经被外部停掉，及时跳出。

下面接口与实现都围绕这三点展开。

## 2. 接口设计

`TimerThread.h`：

```cpp
#pragma once

#include <atomic>
#include <condition_variable>
#include <functional>
#include <mutex>
#include <thread>

class TimerThread final {
public:
    TimerThread();
    TimerThread(const TimerThread&) = delete;
    TimerThread(TimerThread&&) = delete;
    TimerThread& operator=(const TimerThread&) = delete;
    TimerThread& operator=(TimerThread&&) = delete;
    ~TimerThread();

    void setTimerTask(const std::function<void()>& task);
    void startTimer(long long ms);
    void stopTimer();
    bool isRunning() const;

private:
    std::function<void()> task_;
    std::atomic<bool>     running_;
    std::mutex            mutex_;
    std::condition_variable cv_timer_;
    std::thread           thread_;
};
```

### 为什么 task 不放在构造函数里

直觉上把 task 作为构造参数看起来更安全：

```cpp
explicit TimerThread(const std::function<void()>& task);
```

但这会让灵活性下降很多。例如：

- 想把 `TimerThread` 当成成员变量时，往往无法在构造时就拿到 task
- 真正的 task 通常需要在某个成员函数里 `std::bind` 一些局部变量
- 如果坚持构造时传入，最后通常只能改成「指针 + 延迟构造」的写法，绕回原点

所以这里把 task 拆出来，用 `setTimerTask()` 单独设定。

### `bool isRunning() const` 看起来多余但很重要

它提供了一种「在 task 内部检查 Timer 是否已经被停止」的能力。
如果 task 比较长，使用者可以在中间反复调用 `isRunning()`，一旦发现已经被外部 `stopTimer()`，就尽快退出。

例如关闭程序时，没人愿意等一个还要跑很久的 task 把窗口卡在那。

## 3. 实现

`TimerThread.cpp`：

```cpp
#include "TimerThread.h"

#include <cassert>
#include <chrono>

TimerThread::TimerThread()
    : task_(),
      running_(false),
      mutex_(),
      cv_timer_(),
      thread_() {}

TimerThread::~TimerThread() {
    stopTimer();
}

void TimerThread::setTimerTask(const std::function<void()>& task) {
    assert(thread_.get_id() != std::this_thread::get_id());
    assert(!running_);
    task_ = task;
}

void TimerThread::startTimer(long long ms) {
    assert(thread_.get_id() != std::this_thread::get_id());
    assert(task_);
    assert(!running_);

    running_ = true;
    thread_ = std::thread([this, ms]() {
        while (running_) {
            {
                std::unique_lock<std::mutex> lock(mutex_);
                cv_timer_.wait_for(lock, std::chrono::milliseconds(ms), [this] {
                    return !running_;
                });
            }

            if (!running_) {
                return;
            }

            task_();
        }
    });
}

void TimerThread::stopTimer() {
    assert(thread_.get_id() != std::this_thread::get_id());
    running_ = false;
    cv_timer_.notify_one();
    if (thread_.joinable()) {
        thread_.join();
    }
}

bool TimerThread::isRunning() const {
    return running_;
}
```

## 4. 几个关键点的解释

### 析构里调用 `stopTimer()`

```cpp
TimerThread::~TimerThread() {
    stopTimer();
}
```

避免使用者忘记停止，也避免发生异常时线程无法回收。

### `setTimerTask()` 的两个 assert

```cpp
void TimerThread::setTimerTask(const std::function<void()>& task) {
    assert(thread_.get_id() != std::this_thread::get_id());
    assert(!running_);
    task_ = task;
}
```

- 第一个：防止使用者在 task 内部又调用 `setTimerTask()`，造成「自己等自己」的死锁。
- 第二个：要求设置新 task 前先停止 Timer，防止线程正在执行旧 task 时被改成新的 task。这里**故意不加锁**，因为 `TimerThread` 本身就不打算做成 thread-safe。

### `startTimer()` 用 `condition_variable` 等待

```cpp
cv_timer_.wait_for(lock, std::chrono::milliseconds(ms), [this] {
    return !running_;
});
```

如果 Timer 设了 60 分钟，关闭程序时不可能等 60 分钟才能退出。
通过 `cv_timer_.notify_one()` + `running_ = false`，可以在等待过程中立即被唤醒并退出。

### `stopTimer()` 中先改标志再 notify

```cpp
void TimerThread::stopTimer() {
    running_ = false;
    cv_timer_.notify_one();
    if (thread_.joinable()) {
        thread_.join();
    }
}
```

先把 `running_` 置为 false，再 notify，避免「被唤醒后发现条件还没变」的伪唤醒浪费一轮检查。

## 5. 还有两个使用上要注意的点

1. **task 跨线程访问数据要自己保护**：task 是在 Timer 线程里执行的，如果它访问的变量同时被其他线程修改，仍然需要使用者自己加锁。
2. **task 执行时间过长会拖累下一次触发**：如果设定 1 秒触发一次，但 task 自己跑了 1 秒，下次触发实际上变成了 2 秒后。
   常见解法是 task 内部把真正的工作转给另一个线程或线程池，Timer 线程只负责「按时间发起调度」。

## 6. 后续可补的方向

- 同时支持「单次触发」和「周期触发」
- 多个 task 共享同一个调度线程的 TimerService
- 在内部使用最小堆 / `std::set<deadline>` 调度多个 timer
- 与 `executor` / `event loop` 框架（如 boost.asio、libuv）的对接方式
