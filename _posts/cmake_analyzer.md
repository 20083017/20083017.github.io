
```
#!/usr/bin/env python3
import os
import re
import glob
import argparse
from collections import defaultdict, Counter


# ---------- 工具函数 ----------

def normalize_dirs(dirs):
    """规范化目录路径，保证是绝对路径并以 / 结尾"""
    if not dirs:
        return None
    result = []
    for d in dirs:
        absd = os.path.abspath(d)
        if not absd.endswith(os.sep):
            absd += os.sep
        result.append(absd)
    return result


def expand_cmakelists(paths, include_dirs=None, exclude_dirs=None, debug=False):
    """递归展开所有 CMakeLists.txt"""
    files = []
    for p in paths:
        matches = glob.glob(p, recursive=True)

        # 如果是目录，递归找里面的 CMakeLists.txt
        if not matches and os.path.isdir(p):
            matches = glob.glob(os.path.join(p, "**/CMakeLists.txt"), recursive=True)

        for m in matches:
            absm = os.path.abspath(m)

            # include 过滤
            if include_dirs and not any(absm.startswith(d) for d in include_dirs):
                continue

            # exclude 过滤
            if exclude_dirs and any(absm.startswith(d) for d in exclude_dirs):
                if debug:
                    print(f"[DEBUG] 排除: {absm}")
                continue

            files.append(absm)

    if debug:
        print(f"[DEBUG] 找到 {len(files)} 个 CMakeLists.txt")
    return files


# ---------- CMake 解析 ----------

def parse_cmake(files, debug=False):
    """解析 target_link_libraries 依赖"""
    graph = defaultdict(list)
    pattern = re.compile(r"target_link_libraries\s*\((\w+)\s+([^)]+)\)", re.IGNORECASE)

    for f in files:
        if debug:
            print(f"[DEBUG] 解析 {f}")
        with open(f, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                m = pattern.search(line)
                if m:
                    target = m.group(1)
                    deps = re.split(r"[\s;]+", m.group(2).strip())
                    deps = [d for d in deps if d and d.upper() not in ("PUBLIC", "PRIVATE", "INTERFACE")]
                    graph[target].extend(deps)
                    if debug:
                        print(f"   {target} -> {deps}")
    return graph


# ---------- 图处理 ----------

def detect_cycles(graph, max_cycles=20):
    """DFS 检测循环依赖"""
    visited, stack, cycles = set(), [], []

    def dfs(node):
        if node in stack:
            idx = stack.index(node)
            cycles.append(stack[idx:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        stack.append(node)
        for dep in graph.get(node, []):
            dfs(dep)
        stack.pop()

    for n in graph:
        dfs(n)
        if len(cycles) >= max_cycles:
            break
    return cycles


def prune_graph(graph, counts_in, counts_out, top_n=None, prune_in=None, prune_out=None, debug=False):
    """裁剪子图，只保留最关键部分"""
    keep = set()
    if top_n:
        keep.update([n for n, _ in counts_in.most_common(top_n)])
    if prune_in:
        keep.update([n for n, c in counts_in.items() if c >= prune_in])
    if prune_out:
        keep.update([n for n, c in counts_out.items() if c >= prune_out])

    if not keep:
        return graph

    new_graph = {}
    for n, deps in graph.items():
        if n in keep:
            new_graph[n] = [d for d in deps if d in keep]

    if debug:
        print(f"[DEBUG] 裁剪: 原始 {len(graph)} 节点 -> 剩余 {len(new_graph)} 节点")
    return new_graph


def export_to_dot(graph, counts_in, highlight=None, out_file="cmake_deps.dot"):
    """导出依赖关系为 Graphviz dot 文件"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("digraph cmake_deps {\n")
        f.write("  node [shape=box, style=filled, fillcolor=lightgray];\n")
        for n, deps in graph.items():
            color = "red" if highlight and counts_in[n] >= highlight else "lightgray"
            f.write(f"  \"{n}\" [fillcolor={color}];\n")
            for d in deps:
                f.write(f"  \"{n}\" -> \"{d}\";\n")
        f.write("}\n")
    print(f"[OK] 依赖图已导出: {out_file}")


# ---------- 主逻辑 ----------

def main():
    ap = argparse.ArgumentParser(description="CMake target 依赖循环检测工具")
    ap.add_argument("sources", nargs="+", help="CMakeLists 搜索路径或通配符")
    ap.add_argument("-I", "--include", action="append", help="只分析这些目录下的 CMakeLists")
    ap.add_argument("--exclude", action="append", help="屏蔽某些目录（目录及子目录下所有 CMakeLists）")
    ap.add_argument("-o", "--output", default="cmake_deps.dot", help="输出 dot 文件名")
    ap.add_argument("--highlight", type=int, help="高亮依赖数 >= N 的节点")
    ap.add_argument("--prune-in", type=int, help="保留入度 >= N 的节点")
    ap.add_argument("--prune-out", type=int, help="保留出度 >= N 的节点")
    ap.add_argument("--top", type=int, help="保留前 N 个入度最大的节点")
    ap.add_argument("--debug", action="store_true", help="调试模式")
    args = ap.parse_args()

    include_dirs = normalize_dirs(args.include)
    exclude_dirs = normalize_dirs(args.exclude)

    files = expand_cmakelists(args.sources, include_dirs, exclude_dirs, args.debug)
    graph = parse_cmake(files, args.debug)

    # 统计入度/出度
    counts_in, counts_out = Counter(), Counter()
    for n, deps in graph.items():
        counts_out[n] += len(deps)
        for d in deps:
            counts_in[d] += 1

    # 循环检测
    cycles = detect_cycles(graph)
    if cycles:
        print("🔴 循环依赖检测到:")
        for c in cycles:
            print(" -> ".join(c))
    else:
        print("✅ 没有发现循环依赖")

    # 裁剪子图
    graph = prune_graph(graph, counts_in, counts_out,
                        top_n=args.top, prune_in=args.prune_in, prune_out=args.prune_out,
                        debug=args.debug)

    # 导出 DOT 文件
    export_to_dot(graph, counts_in, args.highlight, args.output)


if __name__ == "__main__":
    main()

```
