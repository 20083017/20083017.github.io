---
layout:     post
title:      .clang-format 中文注释版配置示例
subtitle:   一份带中文说明的整 .clang-format 模板，方便回看每一项含义
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - C++
    - clang-format
---

>原始文件只是一份没有任何上下文的 `.clang-format` 配置。这里把它整理成「这份配置是用来干嘛的 + 整段配置 + 维护提醒」三块。
>
>更系统的 clang-format 使用方法（增量格式化、VS Code 接入、多份 demo 对比）放在另一篇 `clang-format.md` 里，本文只保留「带中文注释的完整配置 demo」这一个用途。

## 这份配置适合什么场景

- 想快速拿一份**比较激进、注释又齐全的 `.clang-format`** 套到自己工程里
- 看 `clang-format.md` 主篇时想对照具体某一项的中文注释含义
- 对官方文档的英文项不熟，先靠中文备注快速过一遍每一项干什么用

参考文档（出处在原始笔记里就有）：

- <https://clang.llvm.org/docs/ClangFormatStyleOptions.html>
- <https://www.bbsmax.com/A/VGzlMjexJb/>

## 完整配置（带中文注释）

下面这份直接整段拷到工程根目录的 `.clang-format` 即可。建议拷过去之后，至少先用代码评审里**短期最在意的几条**作为基准（例如 `ColumnLimit`、`IndentWidth`、`PointerAlignment`）。

```yaml
# 语言: None, Cpp, Java, JavaScript, ObjC, Proto, TableGen, TextProto
Language: Cpp

BasedOnStyle: LLVM

# 访问说明符(public、private 等)的偏移
AccessModifierOffset: -4

# 左括号(左圆括号、左尖括号、左方括号)后的对齐:
#   Align, DontAlign, AlwaysBreak(总是在左括号后换行)
AlignAfterOpenBracket: Align

# 连续赋值时，对齐所有等号
AlignConsecutiveAssignments: true

# 连续声明时，对齐所有声明的变量名
AlignConsecutiveDeclarations: true

# 对齐连续位域字段的风格
# AlignConsecutiveBitFields: AcrossEmptyLinesAndComments

# 对齐连续宏定义的风格
# AlignConsecutiveMacros: Consecutive   # clang-format 12

# 用于在使用反斜杠换行中对齐反斜杠的选项
AlignEscapedNewlines: Left

# 水平对齐二元和三元表达式的操作数
AlignOperands: Align

# 对齐连续的尾随的注释
AlignTrailingComments: true

# 如果函数调用或带括号的初始化列表不适合全部在一行时
# 允许将所有参数放到下一行，即使 BinPackArguments 为 false
AllowAllArgumentsOnNextLine: true

# 允许构造函数的初始化参数放在下一行
AllowAllConstructorInitializersOnNextLine: true

# 允许函数声明的所有参数在放在下一行
AllowAllParametersOfDeclarationOnNextLine: true

# 允许短的块放在同一行(Always 总是将短块合并成一行，Empty 只合并空块)
AllowShortBlocksOnASingleLine: Empty

# 允许短的 case 标签放在同一行
AllowShortCaseLabelsOnASingleLine: true

# 允许短的函数放在同一行: None, InlineOnly(定义在类中), Empty(空函数),
#   Inline(定义在类中，空函数), All
AllowShortFunctionsOnASingleLine: Inline

# 允许短的 if 语句保持在同一行
AllowShortIfStatementsOnASingleLine: true

# 允许短的循环保持在同一行
AllowShortLoopsOnASingleLine: true

# 总是在定义返回类型后换行 (deprecated)
AlwaysBreakAfterDefinitionReturnType: None

# 总是在返回类型后换行: None, All, TopLevel(顶级函数，不包括在类中的函数),
#   AllDefinitions(所有的定义，不包括声明), TopLevelDefinitions(所有顶级函数的定义)
AlwaysBreakAfterReturnType: None

# 总是在多行 string 字面量前换行
AlwaysBreakBeforeMultilineStrings: false

# 总是在 template 声明后换行
AlwaysBreakTemplateDeclarations: false

# false 表示函数实参要么都在同一行，要么都各自一行
BinPackArguments: false

# false 表示所有形参要么都在同一行，要么都各自一行
BinPackParameters: true

# 大括号换行，只有当 BreakBeforeBraces 设置为 Custom 时才有效
BraceWrapping:
  AfterCaseLabel:        true     # case 语句后面
  AfterClass:            true     # class 定义后面
  AfterControlStatement: Never    # 控制语句后面
  AfterEnum:             true     # enum 定义后面
  AfterFunction:         true     # 函数定义后面
  AfterNamespace:        false    # 命名空间定义后面
  AfterObjCDeclaration:  false    # ObjC 定义后面
  AfterStruct:           true     # struct 定义后面
  AfterUnion:            true     # union 定义后面
  AfterExternBlock:      false    # extern 导出块后面
  BeforeCatch:           true     # catch 之前
  BeforeElse:            true     # else 之前
  IndentBraces:          false    # 缩进大括号(整个大括号框起来的部分都缩进)
  SplitEmptyFunction:    false    # 空函数的大括号是否可以在一行
  SplitEmptyRecord:      false    # 空记录体(struct/class/union)的大括号是否可以在一行
  SplitEmptyNamespace:   false    # 空名字空间的大括号是否可以在一行

# 在二元运算符前换行:
#   None(在操作符后换行), NonAssignment(在非赋值的操作符前换行), All(在操作符前换行)
BreakBeforeBinaryOperators: None

# 大括号的换行规则
#   Attach / Linux / Mozilla / Stroustrup / Allman / GNU / WebKit / Custom
BreakBeforeBraces: Custom

# 三元运算操作符换行位置（? 和 : 在新行还是尾部）
BreakBeforeTernaryOperators: true

# 在构造函数的初始化列表的逗号前换行
BreakConstructorInitializersBeforeComma: false

# 要使用的构造函数初始化式样式
BreakConstructorInitializers: BeforeComma

# 每行字符的限制，0 表示没有限制
ColumnLimit: 100

# 描述具有特殊意义的注释的正则表达式，它不应该被分割为多行或以其它方式改变
# CommentPragmas: ''

# 如果为 true，则连续的名称空间声明将在同一行上
CompactNamespaces: false

# 构造函数的初始化列表要么都在同一行，要么都各自一行
ConstructorInitializerAllOnOneLineOrOnePerLine: false

# 构造函数的初始化列表的缩进宽度
ConstructorInitializerIndentWidth: 4

# 延续的行的缩进宽度
ContinuationIndentWidth: 4

# 去除 C++11 的列表初始化的大括号 { 后和 } 前的空格
Cpp11BracedListStyle: true

# 继承最常用的指针和引用的对齐方式
DerivePointerAlignment: false

# 关闭格式化
DisableFormat: false

# 自动检测函数的调用和定义是否被格式为每行一个参数 (Experimental)
ExperimentalAutoDetectBinPacking: false

# 如果为 true，会自动给短名称空间补上结束注释，并修正错误的现有结束注释
FixNamespaceComments: true

# 需要被解读为 foreach 循环而不是函数调用的宏
ForEachMacros: [foreach, Q_FOREACH, BOOST_FOREACH]

# 对 #include 进行排序，匹配了某正则表达式的 #include 拥有对应优先级
# 优先级数字越小排序越靠前；可以定义负数优先级，让某些 #include 永远排在最前
IncludeCategories:
  - Regex:    '^"(llvm|llvm-c|clang|clang-c)/'
    Priority: 2
  - Regex:    '^(<|"(gtest|isl|json)/)'
    Priority: 3
  - Regex:    '.*'
    Priority: 1

# 缩进 case 标签
IndentCaseLabels: false

# 要使用的预处理器指令缩进样式
IndentPPDirectives: AfterHash

# 缩进宽度
IndentWidth: 4

# 函数返回类型换行时，缩进函数声明或函数定义的函数名
IndentWrappedFunctionNames: false

# 保留在块开始处的空行
KeepEmptyLinesAtTheStartOfBlocks: true

# 开始一个块的宏的正则表达式
MacroBlockBegin: ''
# 结束一个块的宏的正则表达式
MacroBlockEnd: ''

# 连续空行的最大数量
MaxEmptyLinesToKeep: 10

# 命名空间的缩进: None, Inner(缩进嵌套的命名空间中的内容), All
# NamespaceIndentation: Inner

# 使用 ObjC 块时缩进宽度
ObjCBlockIndentWidth: 4
# 在 ObjC 的 @property 后添加一个空格
ObjCSpaceAfterProperty: false
# 在 ObjC 的 protocol 列表前添加一个空格
ObjCSpaceBeforeProtocolList: true

# 在 call( 后对函数调用换行的 penalty
PenaltyBreakBeforeFirstCallParameter: 2
# 在一个注释中引入换行的 penalty
PenaltyBreakComment: 300
# 第一次在 << 前换行的 penalty
PenaltyBreakFirstLessLess: 120
# 在一个字符串字面量中引入换行的 penalty
PenaltyBreakString: 1000
# 对于每个在行字符数限制之外的字符的 penalty
PenaltyExcessCharacter: 1000000
# 对每一个空格缩进字符的 penalty (相对于前导的非空格列计算)
# PenaltyIndentedWhitespace: 0
# 将函数的返回类型放到它自己的行的 penalty
PenaltyReturnTypeOnItsOwnLine: 120

# 指针和引用的对齐: Left, Right, Middle
PointerAlignment: Left

# 允许重新排版注释
ReflowComments: true

# 允许排序 #include
SortIncludes: true
# 允许排序 using 声明顺序
SortUsingDeclarations: false

# 在 C 风格类型转换后添加空格
SpaceAfterCStyleCast: false
# 在逻辑非操作符 (!) 之后插入一个空格
SpaceAfterLogicalNot: false
# 在 template 关键字后插入一个空格
SpaceAfterTemplateKeyword: false

# 定义在什么情况下在指针限定符之前或之后放置空格
# SpaceAroundPointerQualifiers: Before

# 在赋值运算符之前添加空格
SpaceBeforeAssignmentOperators: true

# 左圆括号之前添加一个空格: Never, ControlStatements, Always
SpaceBeforeParens: ControlStatements

# 空格将在基于范围的 for 循环冒号之前被删除
SpaceBeforeRangeBasedForLoopColon: true

# [ 前是否添加空格（数组名和 [ 之间，Lambdas 不会受到影响）
# 连续多个 [ 只考虑第一个（嵌套数组、多维数组）
SpaceBeforeSquareBrackets: false

# 在空的圆括号中添加空格
SpaceInEmptyParentheses: false

# 在尾随的评论前添加的空格数 (只适用于 //)
SpacesBeforeTrailingComments: 3

# 在尖括号的 < 后和 > 前添加空格
SpacesInAngles: false

# 在容器(ObjC 和 JavaScript 的数组和字典等)字面量中添加空格
SpacesInContainerLiterals: false

# 在 C 风格类型转换的括号中添加空格
SpacesInCStyleCastParentheses: false

# 如果为 true，会在 if/for/switch/while 条件括号前后插入空格
SpacesInConditionalStatement: false

# 在圆括号的 ( 后和 ) 前添加空格
SpacesInParentheses: false

# 在方括号的 [ 后和 ] 前添加空格，lambda 表达式和未指明大小的数组的声明不受影响
SpacesInSquareBrackets: false

# 标准: Cpp03, Cpp11, Auto
Standard: Cpp11

# tab 宽度
TabWidth: 4

# 使用 tab 字符: Never, ForIndentation, ForContinuationAndIndentation, Always
UseTab: Never
```

## 维护这份配置时建议怎么用

- **不要直接拷整份就立刻全量格式化老仓库**，否则历史 diff 会被洗一遍。优先在新模块或新增文件上启用，老代码用「增量格式化」过渡。
- 如果团队已有一份 `.clang-format`，把这份只当**对照表**用，逐条核对每项的取值差异。
- 中文注释只是给自己看的备忘，真正的权威定义还是 LLVM 官方文档。

## 后续可补的方向

- 与 `clang-format.md` 主篇里的「自用 / Microsoft / Google / jemalloc」几份 demo 做差异对比
- 在 CI 里启用 `clang-format --dry-run --Werror` 的最小配置
- 与 pre-commit hook 的整合，做到只对改动行格式化
