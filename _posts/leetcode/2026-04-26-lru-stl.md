---
layout:     post
title:      LRU 缓存（STL list + unordered_map 演示）
subtitle:   用 STL 容器写一遍 LRU
date:       2026-04-26
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - leetcode
    - LRU
    - STL
---

>原始笔记是一份直接贴在文件里的可执行 demo，演示如何用 `std::list` + `std::unordered_map` 写一份 LRU。这里只补充结构说明，代码保留原样。

## 题目背景

与 LeetCode 146 相同：要求 `get`、`put` 都做到 `O(1)`，容量满则淘汰最久未使用项。区别在于这里直接借助 STL 的双向链表 `std::list`，不再手写节点结构。

## 概念解释

- **`std::list<T>`**：标准库的双向链表，迭代器在 `splice/erase/insert` 等操作下都保持有效（除非该元素被删除），非常适合做 LRU 这种需要"原地搬节点"的场景。
- **`std::unordered_map<K, list::iterator>`**：用哈希表保存 key 到链表节点迭代器的映射，使得"找到节点"和"把节点搬到表头"都能在均摊 `O(1)` 完成。

## 实现原理

1. 容器约定：`l` 的**首元素**为最新访问、尾元素为最旧访问；`ump` 把 key 映射到对应迭代器。
2. `put(key, value)`：
   - 不存在且未满 → `emplace_front` 插入新节点，并在哈希表登记迭代器；
   - 不存在且已满 → 先依据 `l.back()` 删除尾部最旧节点（同时清理哈希表），再插入新节点；
   - 已存在 → 通过哈希表定位旧节点，先删除再 `emplace_front` 重新插入到表头，更新映射。
3. `get(key)`：未命中返回 `{-1,-1}`；命中后同样把节点搬到表头，体现"刚被访问"。
4. `print` 仅用于 demo 调试，对算法本身无影响。

> 备注：示例中用 `l.remove(*ump[key])` 通过值删除节点，复杂度为 `O(n)`。如果追求严格 `O(1)`，可改用 `l.erase(ump[key])` 或 `l.splice(l.begin(), l, ump[key])` 直接按迭代器搬动。本笔记保留原写法，便于和最初的实现对齐。

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
#include <algorithm>
#include <unordered_map>
#include <errno.h>
#include <string.h>

#include <cstddef>
#include <iostream>

class lru{
private:
    std::list<std::pair<int,int>> l;
    std::unordered_map<int,std::list<std::pair<int,int>>::iterator> ump;
    int capacity_;
public:
    lru(int capacity):capacity_(capacity){
        
    }

    ~lru(){
        
    }

    void put(int key,int value){
        if(ump.count(key) ==  0)
        {
            if(l.size() < static_cast<size_t>(capacity_))
            {
                l.emplace_front(std::make_pair(key,value));
                ump[key] = l.begin();
            }else{
                ump.erase(l.back().first);
                l.pop_back();

                l.emplace_front(std::make_pair(key,value));
                ump[key] = l.begin();
            }
        }else{
            l.remove(*ump[key]);
            ump.erase(key);

            l.emplace_front(std::make_pair(key,value));
            ump[key] = l.begin();
        }
    }

    std::pair<int,int> get(int key){
        if(ump.count(key) ==  0)
        {
            return std::make_pair(-1,-1);
        }

        l.remove(*ump[key]);
        std::pair<int,int> t = *ump[key];
        l.emplace_front(std::make_pair(key,t.second));
        ump[key] = l.begin();

        return t;
    }

    void print(){
        for(auto iter = l.begin(); iter != l.end(); ++iter){
                std::cout << iter->first << " "  << iter->second << std::endl;
        }
    }
    
};

int main()
{

    lru my_lru(3);

    my_lru.put(1,1);
    my_lru.put(2,2);
    my_lru.put(3,3);

    // my_lru.print();
    
    my_lru.put(4,4);

    // my_lru.print();
    
    my_lru.get(2);

    my_lru.print();   
}
```
