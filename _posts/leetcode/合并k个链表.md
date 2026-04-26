---
layout:     post
title:      合并 K 个升序链表（优先队列）
subtitle:   LeetCode 23 题解笔记
date:       2026-04-26
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - leetcode
    - 链表
    - 优先队列
    - 堆
---

>原始笔记只贴了一份代码。这里把题意与"K 路归并 + 小顶堆"的原理简单写一下，代码保持原样。

## 题目背景

LeetCode 23「合并 K 个升序链表」。给定 `k` 个**已经升序**的链表，将它们合并成一个升序链表。

## 概念解释

- **K 路归并**：归并排序中"两路归并"的推广。每次从所有候选链表的当前头节点中挑出**最小**的，输出后让该链表前进一格。
- **小顶堆 / 优先队列**：能在 `O(log k)` 时间内取出 `k` 个候选中的最小值，是 K 路归并的标配数据结构。
- **lambda 比较器**：`std::priority_queue` 默认是大顶堆，所以需要传入一个返回 `p2 < p1` 的比较器把它变成小顶堆。

## 实现原理

1. 初始把每个非空链表的头节点放进优先队列（这里存 `pair<index, val>`，并辅以哈希表 `mp` 记录每个 index 当前指向的节点指针）。
2. 每次弹出堆顶（值最小的那一项）：
   - 把对应节点接到结果链表尾部，更新 `m_list`；
   - 让 `mp[index]` 指针前进一格，若仍非空，则把新的 `(index, val)` 入堆。
3. 堆空即归并完毕，返回 `m_list_head`。

设总节点数为 `N`，则有 `N` 次堆操作，每次 `O(log k)`，总体时间复杂度 `O(N log k)`，空间复杂度 `O(k)`（堆 + 哈希表大小都受限于链表数量）。

> 备注：标准写法可以直接把 `ListNode*` 入堆，避免额外的 `mp`；这里保留原始的 `index → ListNode*` 映射写法，体现作者最初的实现思路。

## 参考实现

```
/**
 * Definition for singly-linked list.
 * struct ListNode {
 *     int val;
 *     ListNode *next;
 *     ListNode() : val(0), next(nullptr) {}
 *     ListNode(int x) : val(x), next(nullptr) {}
 *     ListNode(int x, ListNode *next) : val(x), next(next) {}
 * };
 */
class Solution {
public:
    ListNode* mergeKLists(vector<ListNode*>& lists) {
        ListNode* m_list = nullptr;
        ListNode* m_list_head = nullptr;
        if(lists.size() == 0)
        {
            return nullptr;
        }

        auto cmp = [](std::pair<int,int> p1, std::pair<int,int> p2){return p2.second < p1.second;};
        std::priority_queue<std::pair<int,int> ,std::vector<std::pair<int,int> >, decltype(cmp) > pq(cmp);

        std::unordered_map<int, ListNode*> mp;

        for(int i = 0; i < lists.size(); ++i)
        {
            if(lists[i] != nullptr)
            {
                pq.push(std::make_pair(i, lists[i]->val));
                mp[i] = lists[i];
            }
        }

        while(!pq.empty())
        {
            std::pair<int,int> t = pq.top();
            if(m_list_head == nullptr)
            {
                m_list = mp[t.first];
                m_list_head = mp[t.first];
            }else
            {
                m_list->next = mp[t.first];
                m_list = m_list->next;
            }
            pq.pop();
            if(mp[t.first]->next != nullptr)
            {
                mp[t.first] = mp[t.first]->next;
                pq.push(std::make_pair(t.first, mp[t.first]->val));
            }
        }

        return m_list_head;
    }
};
```
