---
layout:     post
title:      Graphviz 状态图脚本整理
subtitle:   从 C++ 状态机代码提取状态转移并导出 PNG
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Graphviz
    - Shell
    - C++
---

>原始内容是一段脚本，这里补上用途、依赖和执行方法，并把状态提取逻辑整理成更容易直接复用的版本。

## 这段脚本做什么

目标很简单：

1. 从 C++ 源码里找出 `case xxx:`
2. 再找对应的 `setNextState(...)`
3. 生成 `state_graph.dot`
4. 用 Graphviz 渲染成 `state_graph.png`

这类脚本适合那种“状态很多、代码能看懂，但整体流转关系一眼看不出来”的场景。

## 依赖

```bash
sudo apt install graphviz
```

或者：

```bash
brew install graphviz
```

## 使用方式

```bash
./gen_state_graph.sh file1.cpp file2.cpp
```

输出文件：

- `state_graph.dot`
- `state_graph.png`

## 脚本

```bash
#!/bin/bash

# 输入：C++ 代码文件路径（可多个）
# 输出：生成状态转移图 state_graph.png

parse_transitions() {
    local code_files="$@"

    awk '
    BEGIN { current_state = "" }

    /case[[:space:]]+[A-Za-z0-9_]+:/ {
        current_state = substr($2, 1, length($2)-1)
    }

    /setNextState\([A-Za-z0-9_]+\);/ {
        if (current_state != "") {
            match($0, /setNextState\(([A-Za-z0-9_]+)\);/, arr)
            if (arr[1] != "") {
                print current_state " " arr[1]
            }
            current_state = ""
        }
    }

    /default:/ {
        print "DEFAULT stateerror"
    }
    ' $code_files | sort | uniq
}

generate_graph() {
    local transitions="$1"

    echo "digraph StateTransition {" > state_graph.dot
    echo "  rankdir=LR;" >> state_graph.dot
    echo "  node [shape=box, style=rounded];" >> state_graph.dot

    echo "$transitions" | awk '{print $1 "\n" $2}' | sort -u | while read state; do
        if [ "$state" = "DEFAULT" ]; then
            continue
        fi
        echo "  \"$state\" [label=\"$state\"];" >> state_graph.dot
    done

    echo "$transitions" | while read src dst; do
        if [ "$src" = "DEFAULT" ]; then
            echo "  \"其他状态\" -> \"$dst\" [label=\"非法输入\"];" >> state_graph.dot
        else
            echo "  \"$src\" -> \"$dst\";" >> state_graph.dot
        fi
    done

    echo "}" >> state_graph.dot

    dot -Tpng state_graph.dot -o state_graph.png
    echo "Generated state_graph.png"
}

if [ $# -eq 0 ]; then
    echo "Usage: $0 <C++_file1> <C++_file2> ..."
    exit 1
fi

transitions=$(parse_transitions "$@")
generate_graph "$transitions"
```

## 适用前提

这段脚本默认你的代码大致长这样：

- 状态分支通过 `case state_x:` 表达
- 状态切换通过 `setNextState(next_state);` 表达

如果你的状态机是：

- 多层函数跳转
- 宏展开后才出现状态
- 一个 case 里有多个条件跳转

那这段脚本就更适合作为“粗略提图工具”，而不是严格解析器。
