---
layout:     post
title:      合并 K 个升序链表（STL 演示版）
subtitle:   priority_queue + list iterator 的 K 路归并
date:       2026-04-26
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - leetcode
    - 链表
    - 优先队列
    - STL
---

>原始笔记是一份可以直接编译运行的小 demo，借助 `std::list` 与 `std::priority_queue` 演示 K 路归并。这里只补上结构说明，代码保留原样。

## 题目背景

题意与 LeetCode 23「合并 K 个升序链表」一致，但本笔记不是 LeetCode 的提交版本，而是脱离 `ListNode*` 直接用 STL 容器写的对照实现，便于在本地跑起来观察行为。

## 概念解释

- **`std::list<int>`**：标准库双向链表，迭代器在容器修改后仍然稳定（除非元素被删），可以放心存到外部数据结构里。
- **`listIterator = std::pair<int, std::list<int>::iterator>`**：用 `pair` 把链表编号和该链表当前节点的迭代器绑在一起，方便从堆里取出后判断"该往哪条链表前进"。
- **`std::priority_queue` + lambda**：默认大顶堆；通过自定义比较器 `*(p2.second) < *(p1.second)` 翻转成小顶堆。

## 实现原理

1. 把每条链表的 `begin()` 迭代器连同它所属的链表下标一起入堆，得到 `k` 个候选。
2. 反复弹出堆顶（当前值最小的那个迭代器），把对应值追加到结果 `ret` 中。
3. 弹出后把该链表的迭代器前进一格 `++t.second`；若没到 `end()`，再把更新后的 `(index, iter)` 入堆。
4. 堆空时归并完成，遍历 `ret` 输出。

时间复杂度 `O(N log k)`，空间复杂度 `O(k)`，与提交版本一致。

## 参考实现

```
#include <iostream>  
#include <atomic>
#include <thread>      
#include <vector>  
#include <iterator>
// can be checked without being set
#include <type_traits>
#include <memory>
#include <list>
#include <queue>

int main() {

    std::list<int> l1;
    l1.emplace_back(1);
    l1.emplace_back(20);
    l1.emplace_back(25);
    std::list<int> l2;
    l2.emplace_back(2);
    l2.emplace_back(10);
    l2.emplace_back(33);

    std::vector<std::list<int>> lists = {l1,l2};

    typedef std::pair<int,std::list<int>::iterator> listIterator;

    auto cmp = [](listIterator p1, listIterator p2){ return *(p2.second) < *(p1.second); };
    
    std::priority_queue< listIterator, std::vector<listIterator>, decltype(cmp) > pq(cmp);

    for(size_t i = 0; i < lists.size(); ++i)
        {
            pq.emplace(std::make_pair(i,lists[i].begin()));
        }

    std::list<int> ret;
    
    while(!pq.empty())
        {
            listIterator t = pq.top();
            pq.pop();
            ret.emplace_back(*(t.second));
            
            if(++t.second != lists[t.first].end())
            {
                pq.emplace(std::make_pair(t.first, t.second));
            }
        }

    auto iter = ret.begin();
    while(iter != ret.end())
        {
            std::cout << (*iter) << std::endl;
            ++iter;
        }
    

    return 0;
}
```
