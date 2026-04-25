---
layout:     post
title:      用最小堆实现 Top-K（KthLargest）
subtitle:   priority_queue + greater 的固定写法记录
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - STL
    - 算法
---

>原始笔记只有一段代码，没有任何上下文。这里把题意、思路、复杂度补上，代码本身保持原样。

## 当前保留内容

### 1. 题意 & 思路

求数据流中第 K 大的元素：维护一个大小为 `k` 的**最小堆**，堆顶就是当前流中第 K 大。

- 元素不足 K 个时直接入堆。
- 满 K 个之后，新值若比堆顶大，则弹出堆顶并入堆；否则忽略。

`std::priority_queue` 默认是最大堆，要做最小堆需要把比较器换成 `std::greater<int>`。

### 2. 实现

```
//最小堆
class KthLargest {
private:
    std::priority_queue<int, std::vector<int>, std::greater<int>> p;
    int k;
public:
    KthLargest(int k, vector<int>& nums) {
        this->k = k;
        for(auto item: nums)
        {
            add(item);
        }
    }
    
    int add(int val) {
        if(p.size() < k)
        {
            p.emplace(val);
            return p.top();
        }
        int t = p.top();
        // std::cout << t << std::endl;
        if(val > t)
        {
            p.pop();
            p.emplace(val);
        }
        return p.top();
    }
};
```

### 3. 复杂度

- 单次 `add`：`O(log k)`
- 空间：`O(k)`

## 后续可补的方向

- 对照"维护最大堆"的反例，说明为什么这里必须是最小堆
- 用 `multiset` / `nth_element` 的等价实现对比
- 数据流非常大、k 也很大时的近似算法（如 Count-Min、Reservoir Sampling）
