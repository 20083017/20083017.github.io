---
layout:     post
title:      clang-format 使用整理
subtitle:   增量格式化、VS Code 接入与常用配置
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - clang-format
---

>把原始笔记中的脚本、编辑器配置和样例配置整理成一份可直接复用的 clang-format 速查。

## 适用场景

clang-format 更适合做两类事：

1. 统一团队的 C/C++ 代码风格
2. 在提交前只格式化本次改动过的行，减少无关 diff

## pre-commit：只格式化改动过的代码

下面这段 hook 的思路是：

- 先从暂存区找出本次提交里改动过的 C/C++ 文件
- 再用 `clang-format-diff` 只处理已暂存修改的行
- 如果文件被改写，就重新 `git add`

```bash
#!/usr/bin/env bash
set -e
set -o pipefail

CLANG_FORMAT_BIN="clang-format"
EXT_PATTERN="\.(c|cc|cpp|cxx|h|hpp|hh|hxx)$"

if ! command -v "$CLANG_FORMAT_BIN" >/dev/null 2>&1; then
  echo "[ERROR] clang-format not found"
  echo "Install it first, for example: sudo apt install clang-format"
  exit 1
fi

FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E "$EXT_PATTERN" || true)

if [ -z "$FILES" ]; then
  echo "[pre-commit] No C/C++ files to format."
  exit 0
fi

echo "[pre-commit] Running clang-format on modified lines..."

for FILE in $FILES; do
  [ -f "$FILE" ] || continue

  git diff -U0 --cached "$FILE" | ${CLANG_FORMAT_BIN}-diff -p1 -i

  if ! git diff --quiet "$FILE"; then
    git add "$FILE"
    echo "  formatted: $FILE"
  fi
done

echo "[pre-commit] Done ✅"
```

## 本地安装

```bash
sudo apt-get install clang-format
```

如果还要用上面的 hook，通常还需要确认本机存在 `clang-format-diff`。

## VS Code 接入

1. 安装 clang-format 插件
2. 让工作区或项目根目录放置 `.clang-format`
3. 决定是否开启保存时自动格式化

这类配置会直接改文件，所以更适合配合 Git 使用。

## 一个常用的 `.clang-format` 示例

```yaml
---
BasedOnStyle: Google
AccessModifierOffset: -4
AlignConsecutiveAssignments: true
AlignConsecutiveBitFields: true
AlignConsecutiveDeclarations: true
AlignConsecutiveMacros: true
AllowAllConstructorInitializersOnNextLine: false
AllowShortBlocksOnASingleLine: Empty
AllowShortFunctionsOnASingleLine: Empty
AllowShortIfStatementsOnASingleLine: Never
AlwaysBreakBeforeMultilineStrings: false
BinPackArguments: true
BraceWrapping:
  AfterCaseLabel: false
  AfterClass: false
  AfterControlStatement: Never
  AfterEnum: false
  AfterFunction: false
  AfterNamespace: false
  AfterObjCDeclaration: false
  AfterStruct: false
  AfterUnion: false
  AfterExternBlock: false
  BeforeCatch: false
  BeforeElse: false
  BeforeLambdaBody: false
  BeforeWhile: false
  IndentBraces: false
  SplitEmptyFunction: true
  SplitEmptyRecord: true
  SplitEmptyNamespace: true
BreakBeforeBinaryOperators: All
BreakBeforeBraces: Custom
BreakConstructorInitializers: AfterColon
BreakInheritanceList: AfterColon
ColumnLimit: 120
CompactNamespaces: true
ConstructorInitializerIndentWidth: 8
IndentWidth: 4
IndentWrappedFunctionNames: true
NamespaceIndentation: All
ReflowComments: false
SpaceAfterTemplateKeyword: false
SpacesBeforeTrailingComments: 4
Standard: Latest
TabWidth: 4
```

## 配置时最常关注的几项

- `BasedOnStyle`：先继承一个基础风格，再做局部覆盖
- `ColumnLimit`：决定是否鼓励长行换行
- `IndentWidth` / `TabWidth`：缩进宽度
- `BreakBeforeBraces`：大括号风格
- `AllowShortIfStatementsOnASingleLine`：短 `if` 是否允许单行
- `AlignConsecutive*`：是否对齐连续声明、赋值、宏
- `ReflowComments`：是否自动重排注释

## 使用建议

- 团队首次接入时，先做一次全量格式化，再开始增量格式化
- 如果仓库历史包袱较重，优先启用“只格式化改动行”的 hook
- `.clang-format` 最好跟仓库一起版本化，避免每个人本地风格不一致
