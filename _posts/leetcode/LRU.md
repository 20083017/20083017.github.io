---
layout:     post
title:      LRU 缓存（哈希表 + 双向链表）
subtitle:   LeetCode 146 题解笔记
date:       2026-04-26
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - leetcode
    - LRU
    - Cache
---

>原始笔记只贴了一份能跑过题目的代码。这里在不改动实现的前提下，补一段题意与数据结构的说明，便于日后回顾。

## 题目背景

LeetCode 146「LRU 缓存」。要求设计一个支持 `get(key)` 与 `put(key, value)` 两种操作、容量受限的缓存：当容量满后写入新键时，淘汰**最久未使用**（Least Recently Used）的那一项。两种操作的平均时间复杂度都要做到 `O(1)`。

## 概念解释

- **LRU**：一种缓存替换策略，假设最近被访问的数据短期内更可能再次被访问，因此淘汰最久未访问的项。
- **双向链表**：从节点出发可以 `O(1)` 拿到前驱与后继，因此可以在 `O(1)` 完成"从中间摘除"与"插到头部"两个动作。
- **伪头/伪尾节点（dummy head / dummy tail）**：在链表两端各放一个不存数据的哨兵节点，省去对空链表与边界节点的特判。

## 实现原理

把哈希表与双向链表组合起来：

1. 哈希表 `unordered_map<int, DLinkedNode*>` 把 key 映射到链表中对应节点的指针，使**查找**为 `O(1)`。
2. 双向链表按访问时间排序：越靠近**头部**越新、越靠近**尾部**越旧。
3. `get`：哈希表命中后通过指针把节点从原位置摘下并 `addToHead`，更新它的"最近被访问"地位。
4. `put`：
   - 已存在则更新 value 并 `moveToHead`；
   - 不存在则新建节点、写入哈希表、插到头部；若超出容量，再调用 `removeTail` 同时从哈希表与链表中删除尾节点，保证淘汰的就是最久未使用的那一项。

由于每个动作都只涉及常数次指针修改与哈希操作，`get` 与 `put` 都达到了 `O(1)` 的均摊时间复杂度，空间复杂度为 `O(capacity)`。

## 参考实现

```
struct DLinkedNode {
    int key, value;
    DLinkedNode* prev;
    DLinkedNode* next;
    DLinkedNode(): key(0), value(0), prev(nullptr), next(nullptr) {}
    DLinkedNode(int _key, int _value): key(_key), value(_value), prev(nullptr), next(nullptr) {}
};

class LRUCache {
private:
    unordered_map<int, DLinkedNode*> cache;
    DLinkedNode* head;
    DLinkedNode* tail;
    int size;
    int capacity;

public:
    LRUCache(int _capacity): capacity(_capacity), size(0) {
        // 使用伪头部和伪尾部节点
        head = new DLinkedNode();
        tail = new DLinkedNode();
        head->next = tail;
        tail->prev = head;
    }
    
    int get(int key) {
        if (!cache.count(key)) {
            return -1;
        }
        // 如果 key 存在，先通过哈希表定位，再移到头部
        DLinkedNode* node = cache[key];
        moveToHead(node);
        return node->value;
    }
    
    void put(int key, int value) {
        if (!cache.count(key)) {
            // 如果 key 不存在，创建一个新的节点
            DLinkedNode* node = new DLinkedNode(key, value);
            // 添加进哈希表
            cache[key] = node;
            // 添加至双向链表的头部
            addToHead(node);
            ++size;
            if (size > capacity) {
                // 如果超出容量，删除双向链表的尾部节点
                DLinkedNode* removed = removeTail();
                // 删除哈希表中对应的项
                cache.erase(removed->key);
                // 防止内存泄漏
                delete removed;
                --size;
            }
        }
        else {
            // 如果 key 存在，先通过哈希表定位，再修改 value，并移到头部
            DLinkedNode* node = cache[key];
            node->value = value;
            moveToHead(node);
        }
    }

    void addToHead(DLinkedNode* node) {
        node->prev = head;
        node->next = head->next;
        head->next->prev = node;
        head->next = node;
    }
    
    void removeNode(DLinkedNode* node) {
        node->prev->next = node->next;
        node->next->prev = node->prev;
    }

    void moveToHead(DLinkedNode* node) {
        removeNode(node);
        addToHead(node);
    }

    DLinkedNode* removeTail() {
        DLinkedNode* node = tail->prev;
        removeNode(node);
        return node;
    }
};
```
