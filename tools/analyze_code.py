
```
参数说明（完整）

 sources（必选）：源路径，支持单文件、目录、通配符（例如 build/*.cpp 或 "src/**/*.cpp"）


 -I, --include（可多次）：头文件搜索根目录（会在该根目录下递归查找所有名为 include 的目录并加入）


 -o, --output：导出的 dot 文件名（默认 deps.dot）


 --direct-only：只统计 直接 include（不递归）


 --exclude：屏蔽某些目录（可多次），脚本会忽略这些目录下的头文件


 --highlight N：把被依赖次数 ≥ N 的头文件在 dot 中高亮（红色）


 --prune-in N：裁剪，只保留被依赖次数 ≥ N 的节点及其一跳邻居（incoming + outgoing）


 --prune-out N：裁剪，只保留出度（依赖数） ≥ N 的节点及其一跳邻居


 --top N：组合模式，按入度（图中被多少文件指向）排序，保留前 N 个节点（同样保留这些节点的一跳邻居）


 --debug：打印详细调试信息（解析到哪些 include、哪些 include 未解析、哪些被 exclude 等）


注意（关于 --top）：

 当前实现中，--top 使用的是 graph 的入度（即任何文件对该节点的引用数），而不是 header_to_sources（即“有多少个源文件引用该头文件”）。如果你想按“被多少源文件依赖”排序，我在 README 的后面给出快速修改提示。
```


```
#!/usr/bin/env python3
import os
import re
import glob
import argparse
from collections import defaultdict, Counter

# 正则：匹配 #include "xxx.h" 或 #include <xxx.h>
include_pattern = re.compile(r'^\s*#\s*include\s*["<](.*)[">]')


def is_excluded(path, exclude_dirs):
    """判断某个绝对路径是否位于屏蔽目录下"""
    abs_path = os.path.abspath(path)
    for d in exclude_dirs:
        if abs_path.startswith(os.path.abspath(d) + os.sep):
            return True
    return False


def expand_include_dirs(include_dirs, debug=False):
    """
    自动展开 include 搜索路径：
    - 如果参数本身就是一个名为 include 的目录，则直接加入
    - 否则在给定根目录下递归查找所有名为 include 的子目录并加入
    """
    expanded = []
    for inc in include_dirs:
        if os.path.basename(inc) == "include" and os.path.isdir(inc):
            expanded.append(os.path.abspath(inc))
            if debug:
                print(f"[DEBUG] 直接加入 include: {expanded[-1]}")
        else:
            for root, dirs, _ in os.walk(inc):
                for d in dirs:
                    if d == "include":
                        path = os.path.abspath(os.path.join(root, d))
                        expanded.append(path)
                        if debug:
                            print(f"[DEBUG] 发现 include 目录: {path}")
    # 去重并保持稳定顺序
    seen = set()
    out = []
    for p in expanded:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def expand_sources(sources, debug=False):
    """
    展开源文件参数:
    - 支持目录: 递归查找 .c/.cpp 文件
    - 支持通配符: glob.glob(..., recursive=True)
    - 支持单个文件路径
    返回：文件路径列表（可能为空）
    """
    expanded = []
    for src in sources:
        if os.path.isdir(src):
            for root, _, files in os.walk(src):
                for f in files:
                    if f.endswith((".c", ".cpp")):
                        path = os.path.join(root, f)
                        expanded.append(path)
                        if debug:
                            print(f"[DEBUG] 发现源文件: {path}")
        else:
            matches = glob.glob(src, recursive=True)
            if not matches and debug:
                print(f"[DEBUG] 未找到匹配的源文件: {src}")
            expanded.extend(matches)
    # 去重并稳定顺序
    seen = set()
    out = []
    for p in expanded:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def collect_includes(file, include_dirs, visited, recursive=True, exclude_dirs=None, debug=False):
    """
    收集某个源文件或头文件的依赖头文件集合
    - file: 待解析的文件路径
    - include_dirs: 列表，头文件搜索路径（已展开）
    - visited: set，递归时避免重复访问
    - recursive: 是否递归（递归 => 直接+间接）
    - exclude_dirs: 屏蔽目录列表
    - debug: 是否打印调试信息
    返回 set(头文件路径)
    """
    if exclude_dirs is None:
        exclude_dirs = []
    deps = set()
    try:
        with open(file, "r", encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, start=1):
                m = include_pattern.match(line)
                if m:
                    header = m.group(1)
                    if debug:
                        print(f"[DEBUG] {file}:{lineno} 找到 include -> {header}")
                    found = False
                    for inc_dir in include_dirs:
                        candidate = os.path.join(inc_dir, header)
                        if os.path.exists(candidate):
                            found = True
                            if is_excluded(candidate, exclude_dirs):
                                if debug:
                                    print(f"[DEBUG] {file}:{lineno} 跳过被屏蔽头文件 {candidate}")
                                break
                            deps.add(candidate)
                            if debug:
                                print(f"[DEBUG] {file}:{lineno} 解析成功 -> {candidate}")
                            if recursive and candidate not in visited:
                                visited.add(candidate)
                                deps |= collect_includes(candidate, include_dirs, visited,
                                                         recursive, exclude_dirs, debug)
                            break
                    if not found and debug:
                        # 没在 include_dirs 下找到对应文件（可能是系统头或拼写不同）
                        print(f"[DEBUG] {file}:{lineno} 未解析成功 -> {header}")
    except FileNotFoundError:
        if debug:
            print(f"[DEBUG] 文件未找到: {file}")
    return deps


def build_dependency_graph(files, include_dirs, exclude_dirs, debug=False):
    """
    构建依赖图 graph: dict(file -> set(deps))
    - 确保每个传入的源文件都在 graph 中作为 key（即使它没有依赖）
    - exclude_dirs: 屏蔽目录
    """
    graph = defaultdict(set)

    def visit(file, visited):
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, start=1):
                    m = include_pattern.match(line)
                    if m:
                        header = m.group(1)
                        for inc_dir in include_dirs:
                            candidate = os.path.join(inc_dir, header)
                            if os.path.exists(candidate) and not is_excluded(candidate, exclude_dirs):
                                graph[file].add(candidate)
                                if debug:
                                    print(f"[DEBUG] 图构建: {file} -> {candidate}")
                                if candidate not in visited:
                                    visited.add(candidate)
                                    visit(candidate, visited)
                                break
        except FileNotFoundError:
            if debug:
                print(f"[DEBUG] 文件未找到: {file}")

    visited = set()
    for f in files:
        graph[f]  # 确保 key 存在
        visit(f, visited)
    return graph


def detect_cycles(graph, max_cycles=20):
    """
    检测有向图中的环（DFS + 递归栈）
    返回环列表（每个环是节点列表，起止节点重复以便显示循环）
    """
    cycles = []
    temp_mark = set()
    perm_mark = set()
    stack = []

    def visit(node):
        if node in perm_mark:
            return
        if node in temp_mark:
            # 找到环：stack 中从第一次出现 node 的位置切片到末尾，再加上 node 以闭合环
            try:
                idx = stack.index(node)
                cycle = stack[idx:] + [node]
                cycles.append(cycle)
            except ValueError:
                pass
            return
        temp_mark.add(node)
        stack.append(node)
        for nei in graph.get(node, []):
            visit(nei)
        stack.pop()
        temp_mark.remove(node)
        perm_mark.add(node)

    for n in graph:
        if n not in perm_mark:
            visit(n)

    # 输出结果
    print("\n🔎 循环依赖检测结果:")
    if not cycles:
        print("✅ 没有发现循环依赖")
    else:
        for i, c in enumerate(cycles[:max_cycles], 1):
            print(f"🔴 循环 {i}: " + " -> ".join(c))
        if len(cycles) > max_cycles:
            print(f"... 还有 {len(cycles) - max_cycles} 个未显示")
    return cycles


def prune_graph(graph, header_to_sources, prune_in=0, prune_out=0, top_n=0, debug=False):
    """
    裁剪图，保留“重点节点及其邻居”
    - prune_in: 保留被依赖次数 >= prune_in 的节点（入度）
    - prune_out: 保留依赖数量 >= prune_out 的节点（出度）
    - top_n: 保留按入度排序的前 top_n 个节点（若 top_n>0）
    行为：focus_nodes = union(prune_in_nodes, prune_out_nodes, top_n_nodes)
    然后保留 focus_nodes 和它们的直接邻居（incoming + outgoing，一次扩展，不递归）
    """
    if prune_in <= 0 and prune_out <= 0 and top_n <= 0:
        return graph

    # 计算入度（来自 graph 的 edges）和出度
    counts_in = Counter()
    counts_out = Counter({node: len(deps) for node, deps in graph.items()})
    for src, deps in graph.items():
        for dep in deps:
            counts_in[dep] += 1

    focus_nodes = set()

    # 根据 prune_in
    if prune_in > 0:
        for node, cnt in counts_in.items():
            if cnt >= prune_in:
                focus_nodes.add(node)
                if debug:
                    print(f"[DEBUG] 保留节点 by prune_in({prune_in}): {node} (in={cnt})")
    # 根据 prune_out
    if prune_out > 0:
        for node, cnt in counts_out.items():
            if cnt >= prune_out:
                focus_nodes.add(node)
                if debug:
                    print(f"[DEBUG] 保留节点 by prune_out({prune_out}): {node} (out={cnt})")
    # 根据 top_n（按入度排序）
    if top_n > 0:
        most = counts_in.most_common(top_n)
        for node, cnt in most:
            focus_nodes.add(node)
            if debug:
                print(f"[DEBUG] 保留节点 by top({top_n}): {node} (in={cnt})")

    # 构建裁剪后图：保留 focus_nodes 及其直接邻居（incoming + outgoing）
    pruned = defaultdict(set)
    # 保留 focus_nodes 的 outgoing edges
    for node in focus_nodes:
        if node in graph:
            pruned[node] |= set(graph[node])
        else:
            # node 可能只作为 dep 出现，没有 outgoing；仍确保该节点存在为 key（空集）
            pruned[node] = pruned.get(node, set())

    # 保留所有指向 focus_nodes 的 incoming edges（保持源节点 -> focus_node）
    for src, deps in graph.items():
        for dep in deps:
            if dep in focus_nodes:
                pruned[src].add(dep)

    # 去掉空的 key（如果既不是 src 也没有 outgoing）
    # 不强制去掉：保留那些作为 key 但没有边的节点（便于在图中显示孤立热点）
    print(f"\n[INFO] 图裁剪完成: 原始节点数 {len(graph)} -> 裁剪后节点数 {len(pruned)}")
    return pruned


def export_to_dot(graph, highlight_map, output="deps.dot"):
    """把 graph 导出为 Graphviz dot 文件，支持节点高亮（highlight_map）"""
    with open(output, "w", encoding="utf-8") as f:
        f.write("digraph G {\n")
        f.write("  rankdir=LR;\n")
        f.write("  node [shape=box, fontsize=10];\n")
        for src, deps in graph.items():
            src_style = ""
            if highlight_map.get(src, False):
                src_style = ' [style=filled, fillcolor=red, fontcolor=white, penwidth=2]'
            if not deps:
                f.write(f'  "{src}"{src_style};\n')
            for dep in deps:
                dep_style = ""
                if highlight_map.get(dep, False):
                    dep_style = ' [style=filled, fillcolor=red, fontcolor=white, penwidth=2]'
                f.write(f'  "{src}" -> "{dep}";\n')
                # 确保 dep 节点也可以带样式
                f.write(f'  "{dep}"{dep_style};\n')
        f.write("}\n")
    print(f"[OK] 依赖图已导出: {output}")
    print("     可用命令: dot -Tpng {0} -o {1}.png".format(output, os.path.splitext(output)[0]))


def main():
    parser = argparse.ArgumentParser(description="头文件依赖分析工具（支持递归 include 查找、裁剪、循环检测等）")
    parser.add_argument("sources", nargs="+", help="源文件路径/目录/通配符 (.cpp/.c)")
    parser.add_argument("-I", "--include", action="append", default=["."],
                        help="头文件搜索根目录 (自动递归查找 include 子目录)")
    parser.add_argument("-o", "--output", default="deps.dot",
                        help="导出依赖图 dot 文件名")
    parser.add_argument("--direct-only", action="store_true",
                        help="只统计直接依赖（不包含间接依赖）")
    parser.add_argument("--exclude", action="append", default=[],
                        help="屏蔽某些目录 (可多次指定)")
    parser.add_argument("--highlight", type=int, default=0,
                        help="高亮被依赖次数 >=N 的头文件 (染成红色)")
    parser.add_argument("--prune-in", type=int, default=0,
                        help="只保留被依赖次数 >=N 的头文件及其邻居")
    parser.add_argument("--prune-out", type=int, default=0,
                        help="只保留依赖 >=N 个头文件的节点及其邻居")
    parser.add_argument("--top", type=int, default=0,
                        help="保留按被依赖次数排序的前 N 个节点（自动组合模式）")
    parser.add_argument("--debug", action="store_true",
                        help="输出详细调试信息")
    args = parser.parse_args()

    include_dirs = expand_include_dirs(args.include, args.debug)
    print(f"[INFO] 头文件搜索路径 ({len(include_dirs)} 个):")
    for d in include_dirs:
        print("   ", d)

    sources = expand_sources(args.sources, args.debug)
    if not sources:
        print("[WARN] 没有找到任何源文件，请检查路径/通配符是否正确")
        return
    print(f"[INFO] 源文件总数: {len(sources)}")

    header_to_sources = defaultdict(set)
    for src in sources:
        deps = collect_includes(
            src, include_dirs, visited=set(),
            recursive=not args.direct_only,
            exclude_dirs=args.exclude, debug=args.debug
        )
        print(f"\n源文件: {src}")
        print(f"依赖头文件总数: {len(deps)}")
        for d in sorted(deps):
            print("   ", d)
            header_to_sources[d].add(src)

    graph = build_dependency_graph(sources, include_dirs, args.exclude, args.debug)

    print("\n📊 头文件被依赖次数统计 (按源文件粒度):")
    counts = Counter({hdr: len(srcs) for hdr, srcs in header_to_sources.items()})
    for hdr, cnt in counts.most_common():
        print(f"{hdr:50s}  <- {cnt} 个源文件")

    # 生成高亮映射（基于 header 被多少源文件依赖）
    highlight_map = {}
    if args.highlight > 0:
        for hdr, cnt in counts.items():
            if cnt >= args.highlight:
                highlight_map[hdr] = True
                if args.debug:
                    print(f"[DEBUG] 将 {hdr} 标记为高亮 (被 {cnt} 个源文件依赖)")

    # 循环检测（始终运行，打印结果）
    detect_cycles(graph)

    # 裁剪图：支持 prune_in / prune_out / top
    graph = prune_graph(graph, header_to_sources,
                        prune_in=args.prune_in, prune_out=args.prune_out,
                        top_n=args.top, debug=args.debug)

    # 导出 dot
    export_to_dot(graph, highlight_map, args.output)


if __name__ == "__main__":
    main()

```
