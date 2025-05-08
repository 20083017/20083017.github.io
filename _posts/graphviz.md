

```
#!/bin/bash

# 输入：C++ 代码文件路径（可多个）
# 输出：生成状态转移图 state_graph.png
# 依赖：graphviz（安装命令：sudo apt install graphviz 或 brew install graphviz）

# --------------------------------------------
# 解析代码中的状态转移关系（关键逻辑）
# --------------------------------------------
parse_transitions() {
    local code_files="$@"
    
    # 使用 awk 提取 case 标签和 setNextState 的目标状态
    awk '
    BEGIN { current_state = "" }
    # 匹配 case 行（如 "case state1:"）
    /case [A-Za-z0-9_]+:/ {
        current_state = substr($2, 1, length($2)-1)  # 提取状态名（去掉末尾冒号）
    }
    # 匹配 setNextState 调用（如 "setNextState(state2);"）
    /setNextState$[A-Za-z0-9_]+$/ {
        if (current_state != "") {
            # 提取参数（例如 state2）
            match($0, /setNextState$([A-Za-z0-9_]+)$/, arr)
            print current_state " " arr[1]
            current_state = ""  # 清空，避免重复匹配
        }
    }
    # 处理 default 分支（如果有）
    /default:/ {
        print "DEFAULT stateerror"  # 假设 default 分支跳转到 stateerror
    }
    ' $code_files | sort | uniq
}

# --------------------------------------------
# 生成 DOT 文件并渲染为 PNG
# --------------------------------------------
generate_graph() {
    local transitions="$1"
    
    # 生成 DOT 文件
    echo "digraph StateTransition {" > state_graph.dot
    echo "  rankdir=LR;" >> state_graph.dot
    echo "  node [shape=box, style=rounded];" >> state_graph.dot
    
    # 添加所有状态节点
    echo "$transitions" | awk '{print $1 "\n" $2}' | sort -u | while read state; do
        if [ "$state" == "DEFAULT" ]; then continue; fi  # 忽略 DEFAULT 标签
        echo "  \"$state\" [label=\"$state\"];" >> state_graph.dot
    done
    
    # 添加状态转移边
    echo "$transitions" | while read src dst; do
        if [ "$src" == "DEFAULT" ]; then
            echo "  \"其他状态\" -> \"$dst\" [label=\"非法输入\"];" >> state_graph.dot
        else
            echo "  \"$src\" -> \"$dst\";" >> state_graph.dot
        fi
    done
    
    echo "}" >> state_graph.dot
    
    # 生成 PNG 图片
    dot -Tpng state_graph.dot -o state_graph.png
    echo "Generated state_graph.png"
}

# --------------------------------------------
# 主流程
# --------------------------------------------
if [ $# -eq 0 ]; then
    echo "Usage: $0 <C++_file1> <C++_file2> ..."
    exit 1
fi

# 解析代码并生成图
transitions=$(parse_transitions "$@")
generate_graph "$transitions"

```
