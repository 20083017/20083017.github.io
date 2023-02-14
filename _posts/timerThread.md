
有時候你就是不想用平台提供的 Timer API，想用純 C++ 寫一個，且此 Timer 必須最少滿足一些條件，像是：

1. 不過度設計，簡單提供定時呼叫的機制即可。

2. 可以隨時停止 Timer，不用想關閉程式時，卻還是必須等到時間到了才能結束。

3. Timer task 執行時，可以設一些檢查點判斷 Timer 是否已經被使用者終止，在處理一些需時甚久的 CPU 計算時特別需要。

以下是你需要的介面，讓我們來看看為何需要這幾個函式吧。
```
#pragma once

#include <functional>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <thread>

class TimerThread final
{
public:
    TimerThread();
    TimerThread(const TimerThread&) = delete;
    TimerThread(TimerThread&&) = delete;
    TimerThread& operator=(const TimerThread&) = delete;
    TimerThread& operator=(TimerThread&&) = delete;
    ~TimerThread();

public:
    void setTimerTask(const std::function<void()>& task);
    void startTimer(long long ms);
    void stopTimer();
    bool isRunning() const;

private:
    std::function<void()> task_;
    std::atomic<bool> running_;
    std::mutex mutex_;
    std::condition_variable cv_timer_;
    std::thread thread_;
};
```
1. void setTimerTask(const std::function<void()>& task)

設定要定時執行的 function，這很直觀，唯一需要解釋的是，為什麼不在建構子直接傳入 task，而必須另外開一個函式設定 task 呢？

explicit TimerThread(const std::function<void()>& task)

因為擺在建構子雖然可以避免使用者呼叫 startTimer 時 task 是空的錯誤，但彈性降低很多，例如除非使用指標，不然沒辦法當成成員變數，但又要在成員函式中 std::bind 一些 local 的變數傳入 task，這會造成需要較為複雜的寫法，且不易使用。

2. void startTimer(long long ms) 及 void stopTimer()

這沒甚麼好解釋，使用者會希望能停止或重新設定 Timer。

3. bool isRunning() const

這個函式乍看之下可有可無，但其實非常重要，因為它提供了在 task 中檢查 Timer 是否已經被終止的可能，如果使用者提供的 task 需要執行較久的時間，使用者會希望在他的 task 內設定一些點來呼叫此函式並檢查是否終止。例如在關閉程式時，應該沒人會希望等待 task 執行完畢，視窗凍結住吧。

接下來讓我們看看實作。
```
#include “TimerThread.h”
#include <assert.h>
#include <chrono>

TimerThread::TimerThread() :
    task_(),
    running_(false),
    mutex_(),
    cv_timer_(),
    thread_()
{}

TimerThread::~TimerThread()
{
    stopTimer();
}

void TimerThread::setTimerTask(const std::function<void()>& task)
{
    assert(thread_.get_id() != std::this_thread::get_id());
    assert(!running_);
    task_ = task;
}

void TimerThread::startTimer(long long ms)
{
    assert(thread_.get_id() != std::this_thread::get_id());
    assert(task_);
    assert(!running_);
    running_ = true;
    thread_ = std::thread([this, ms]()
    {
        while (running_)
        {
            {
                std::unique_lock lock(mutex_);
                cv_timer_.wait_for(lock, std::chrono::milliseconds(ms), [this]
                {
                    return !running_;
                });
            }

            if (!running_)
            {
                return;
            }

            task_();
        } // end while
    }); // end thread_
}

void TimerThread::stopTimer()
{
    assert(thread_.get_id() != std::this_thread::get_id());
    running_ = false;
    cv_timer_.notify_one();
    if (thread_.joinable())
    {
        thread_.join();
    }
}

bool TimerThread::isRunning() const
{
    return running_;
}
```
1. 解構子呼叫 stopTimer()，可以避免使用者忘記呼叫及避免 exception 時無法釋放資源的情況發生。
```
TimerThread::~TimerThread()
{
    stopTimer();
}
```
2. 第一個 assert 提醒使用者在開發時，仔細檢查有沒有在 task 內呼叫 setTimerTask，造成 自己等自己 dead lock 的情況發生。

assert(!running_) 提醒使用者，設定新 task 前先停止 Timer，不然可能 TimerThread 在執行 task 時，task 同時被賦值，畢竟此 TimerThread 不是 thread-safe，嘗試 lock task 是多餘的設計，並且效率會有一點減損，別小看這一點減損，在設計看盤系統可能會是致命的。
```
void TimerThread::setTimerTask(const std::function<void()>& task)
{
    assert(thread_.get_id() != std::this_thread::get_id());
    assert(!running_);
    task_ = task;
}
```
3. assert(task) 提醒使用者程式不會檢查 task 是否為空，檢查 task 是否為空會慢一點，況且 task 空的是要怎樣。

值得注意的是，使用 std::condition_variable 可以讓 thread 有機會在等待的時間還沒到就被停止條件滿足時喚醒。例如 Timer 設定 60 分鐘，使用者關閉程式時你不會想等 60 分鐘關閉程式吧。
```
void TimerThread::startTimer(long long ms)
{
    assert(thread_.get_id() != std::this_thread::get_id());
    assert(task_);
    assert(!running_);
    running_ = true;
    thread_ = std::thread([this, ms]()
    {
        while (running_)
        {
            {
                std::unique_lock lock(mutex_);
                cv_timer_.wait_for(lock, std::chrono::milliseconds(ms), [this]
                {
                    return !running_;
                });
            }

            if (!running_)
            {
                return;
            }

            task_();
        } // end while
    }); // end thread_
}
```
4. 呼叫 notify_one 前，先設定 running_ = false，不然被偽喚醒效率就慢了點了。
```
void TimerThread::stopTimer()
{
    assert(thread_.get_id() != std::this_thread::get_id());
    running_ = false;
    cv_timer_.notify_one();
    if (thread_.joinable())
    {
        thread_.join();
    }
}
```
事實上這個 Timer 還有兩個要注意的地方，第一個就是 task 是在不同的 thread 執行，因此如果要同時更新變數，是需要保護的。

第二個就是如果 task 執行的過久，那麼下次 timer 間隔就會超時了，例如設定 timer 1 秒，結果 task 執行了 1 秒，那下次 timer 到達其實是 2 秒後了，不過這完全可以由使用者自行解決，只要 task 內簡單將任務轉給自己的 thread，不佔用 Timer thread 的執行時間即可，這也可以防止 task 當機影響到 Timer thread。

以上就介紹到這裡，程式請隨便取用，有不懂的或錯誤的請留言告訴我，謝謝。
