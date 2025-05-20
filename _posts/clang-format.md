
### clang-format

sudo apt-get install clang-format

vscode 安装clang-format 插件

一个常用的.clang-format 文件
```
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

### clang-format 配置详解
```
---
 # 语言: None, Cpp, Java, JavaScript, ObjC, Proto, TableGen, TextProto
 Language:Cpp
 # BasedOnStyle:LLVM
 # 访问说明符(public、private等)的偏移
 AccessModifierOffset:-4
 # 开括号(开圆括号、开尖括号、开方括号)后的对齐: Align, DontAlign, AlwaysBreak(总是在开括号后换行)
 AlignAfterOpenBracket:Align
 # 连续赋值时，对齐所有等号
 AlignConsecutiveAssignments:true
 # 连续声明时，对齐所有声明的变量名
 AlignConsecutiveDeclarations:true
 # 左对齐逃脱换行(使用反斜杠换行)的反斜杠
 AlignEscapedNewlinesLeft:true
 # 水平对齐二元和三元表达式的操作数
 AlignOperands:true
 # 对齐连续的尾随的注释
 AlignTrailingComments:true
 # 允许函数声明的所有参数在放在下一行
 AllowAllParametersOfDeclarationOnNextLine:true
 # 允许短的块放在同一行
 AllowShortBlocksOnASingleLine:false
 # 允许短的case标签放在同一行
 AllowShortCaseLabelsOnASingleLine:false
 # 允许短的函数放在同一行: None, InlineOnly(定义在类中), Empty(空函数), Inline(定义在类中，空函数), All
 AllowShortFunctionsOnASingleLine:Empty
 # 允许短的if语句保持在同一行
 AllowShortIfStatementsOnASingleLine:false
 # 允许短的循环保持在同一行
 AllowShortLoopsOnASingleLine:false
 # 总是在定义返回类型后换行(deprecated)
 AlwaysBreakAfterDefinitionReturnType:None
 # 总是在返回类型后换行: None, All, TopLevel(顶级函数，不包括在类中的函数), 
 #   AllDefinitions(所有的定义，不包括声明), TopLevelDefinitions(所有的顶级函数的定义)
 AlwaysBreakAfterReturnType:None
 # 总是在多行string字面量前换行
 AlwaysBreakBeforeMultilineStrings:false
 # 总是在template声明后换行
 AlwaysBreakTemplateDeclarations:false
 # false表示函数实参要么都在同一行，要么都各自一行
 BinPackArguments:true
 # false表示所有形参要么都在同一行，要么都各自一行
 BinPackParameters:true
 # 大括号换行，只有当BreakBeforeBraces设置为Custom时才有效
 BraceWrapping:   
   # class定义后面
  AfterClass:false
   # 控制语句后面
  AfterControlStatement:false
   # enum定义后面
  AfterEnum:false
   # 函数定义后面
  AfterFunction:false
   # 命名空间定义后面
  AfterNamespace:false
   # ObjC定义后面
  AfterObjCDeclaration:false
   # struct定义后面
  AfterStruct:false
   # union定义后面
  AfterUnion:false
   # catch之前
  BeforeCatch:true
   # else之前
  BeforeElse:true
   # 缩进大括号
  IndentBraces:false
 # 在二元运算符前换行: None(在操作符后换行), NonAssignment(在非赋值的操作符前换行), All(在操作符前换行)
 BreakBeforeBinaryOperators:NonAssignment
 # 在大括号前换行: Attach(始终将大括号附加到周围的上下文), Linux(除函数、命名空间和类定义，与Attach类似), 
 #   Mozilla(除枚举、函数、记录定义，与Attach类似), Stroustrup(除函数定义、catch、else，与Attach类似), 
 #   Allman(总是在大括号前换行), GNU(总是在大括号前换行，并对于控制语句的大括号增加额外的缩进), WebKit(在函数前换行), Custom
 #   注：这里认为语句块也属于函数
 BreakBeforeBraces:Custom
 # 在三元运算符前换行
 BreakBeforeTernaryOperators:true
 # 在构造函数的初始化列表的逗号前换行
 BreakConstructorInitializersBeforeComma:false
 # 每行字符的限制，0表示没有限制
 ColumnLimit:200
 # 描述具有特殊意义的注释的正则表达式，它不应该被分割为多行或以其它方式改变
 CommentPragmas:'^ IWYU pragma:'
 # 构造函数的初始化列表要么都在同一行，要么都各自一行
 ConstructorInitializerAllOnOneLineOrOnePerLine:false
 # 构造函数的初始化列表的缩进宽度
 ConstructorInitializerIndentWidth:4
 # 延续的行的缩进宽度
 ContinuationIndentWidth:4
 # 去除C++11的列表初始化的大括号{后和}前的空格
 Cpp11BracedListStyle:false
 # 继承最常用的指针和引用的对齐方式
 DerivePointerAlignment:false
 # 关闭格式化
 DisableFormat:false
 # 自动检测函数的调用和定义是否被格式为每行一个参数(Experimental)
 ExperimentalAutoDetectBinPacking:false
 # 需要被解读为foreach循环而不是函数调用的宏
 ForEachMacros:[ foreach, Q_FOREACH, BOOST_FOREACH ]
 # 对#include进行排序，匹配了某正则表达式的#include拥有对应的优先级，匹配不到的则默认优先级为INT_MAX(优先级越小排序越靠前)，
 #   可以定义负数优先级从而保证某些#include永远在最前面
 IncludeCategories: 
   - Regex:'^"(llvm|llvm-c|clang|clang-c)/'
    Priority:2
   - Regex:'^(<|"(gtest|isl|json)/)'
    Priority:3
   - Regex:'.*'
    Priority:1
 # 缩进case标签
 IndentCaseLabels:false
 # 缩进宽度
 IndentWidth:4
 # 函数返回类型换行时，缩进函数声明或函数定义的函数名
 IndentWrappedFunctionNames:false
 # 保留在块开始处的空行
 KeepEmptyLinesAtTheStartOfBlocks:true
 # 开始一个块的宏的正则表达式
 MacroBlockBegin:''
 # 结束一个块的宏的正则表达式
 MacroBlockEnd:''
 # 连续空行的最大数量
 MaxEmptyLinesToKeep:1
 # 命名空间的缩进: None, Inner(缩进嵌套的命名空间中的内容), All
 NamespaceIndentation:Inner
 # 使用ObjC块时缩进宽度
 ObjCBlockIndentWidth:4
 # 在ObjC的@property后添加一个空格
 ObjCSpaceAfterProperty:false
 # 在ObjC的protocol列表前添加一个空格
 ObjCSpaceBeforeProtocolList:true
 # 在call(后对函数调用换行的penalty
 PenaltyBreakBeforeFirstCallParameter:19
 # 在一个注释中引入换行的penalty
 PenaltyBreakComment:300
 # 第一次在<<前换行的penalty
 PenaltyBreakFirstLessLess:120
 # 在一个字符串字面量中引入换行的penalty
 PenaltyBreakString:1000
 # 对于每个在行字符数限制之外的字符的penalty
 PenaltyExcessCharacter:1000000
 # 将函数的返回类型放到它自己的行的penalty
 PenaltyReturnTypeOnItsOwnLine:60
 # 指针和引用的对齐: Left, Right, Middle
 PointerAlignment:Left
 # 允许重新排版注释
 ReflowComments:true
 # 允许排序#include
 SortIncludes:true
 # 在C风格类型转换后添加空格
 SpaceAfterCStyleCast:false
 # 在赋值运算符之前添加空格
 SpaceBeforeAssignmentOperators:true
 # 开圆括号之前添加一个空格: Never, ControlStatements, Always
 SpaceBeforeParens:ControlStatements
 # 在空的圆括号中添加空格
 SpaceInEmptyParentheses:false
 # 在尾随的评论前添加的空格数(只适用于//)
 SpacesBeforeTrailingComments:2
 # 在尖括号的<后和>前添加空格
 SpacesInAngles:true
 # 在容器(ObjC和JavaScript的数组和字典等)字面量中添加空格
 SpacesInContainerLiterals:true
 # 在C风格类型转换的括号中添加空格
 SpacesInCStyleCastParentheses:true
 # 在圆括号的(后和)前添加空格
 SpacesInParentheses:true
 # 在方括号的[后和]前添加空格，lamda表达式和未指明大小的数组的声明不受影响
 SpacesInSquareBrackets:true
 # 标准: Cpp03, Cpp11, Auto
 Standard:Cpp11
 # tab宽度
 TabWidth:4
 # 使用tab字符: Never, ForIndentation, ForContinuationAndIndentation, Always
 UseTab:Never
 ...
```

### 配置生效

.vscode/settings.json

```
"clang-format.fallbackStyle":"file",
 "editor.formatOnSave": true,
```
### 配置检查
```
 clang-format --dump-config
```


```
# jemalloc targets clang-format version 8.  We include every option it supports
# here, but comment out the ones that aren't relevant for us.
---
# AccessModifierOffset: -2
AlignAfterOpenBracket: DontAlign
AlignConsecutiveAssignments: false
AlignConsecutiveDeclarations: false
AlignEscapedNewlines: Right
AlignOperands: false
AlignTrailingComments: false
AllowAllParametersOfDeclarationOnNextLine: true
AllowShortBlocksOnASingleLine: true
AllowShortCaseLabelsOnASingleLine: true
AllowShortFunctionsOnASingleLine: Empty
AllowShortIfStatementsOnASingleLine: true
AllowShortLoopsOnASingleLine: true
AlwaysBreakAfterReturnType: AllDefinitions
AlwaysBreakBeforeMultilineStrings: true
# AlwaysBreakTemplateDeclarations: Yes
BinPackArguments: true
BinPackParameters: true
BraceWrapping:
  AfterClass: true
  AfterControlStatement: true
  AfterEnum: true
  AfterFunction: true
  AfterNamespace: true
  AfterObjCDeclaration: true
  AfterStruct: true
  AfterUnion: true
  BeforeCatch: true
  BeforeElse: true
  IndentBraces: true
# BreakAfterJavaFieldAnnotations: true
BreakBeforeBinaryOperators: NonAssignment
BreakBeforeBraces: Allman  
BreakBeforeTernaryOperators: true
# BreakConstructorInitializers: BeforeColon
# BreakInheritanceList: BeforeColon
BreakStringLiterals: false
ColumnLimit: 120
# CommentPragmas: ''
# CompactNamespaces: true
# ConstructorInitializerAllOnOneLineOrOnePerLine: true
# ConstructorInitializerIndentWidth: 4
ContinuationIndentWidth: 4
Cpp11BracedListStyle: true
DerivePointerAlignment: false
DisableFormat:   false
ExperimentalAutoDetectBinPacking: false
FixNamespaceComments: true
ForEachMacros:   [ ql_foreach, qr_foreach, ]
# IncludeBlocks: Preserve
# IncludeCategories:
#   - Regex:           '^<.*\.h(pp)?>'
#     Priority:        1
# IncludeIsMainRegex: ''

 #   可以定义负数优先级从而保证某些#include永远在最前面
 IncludeCategories: 
   - Regex:'^"(llvm|llvm-c|clang|clang-c)/'
    Priority:2
   - Regex:'^(<|"(gtest|isl|json)/)'
    Priority:3
   - Regex:'.*'
    Priority:1

IndentCaseLabels: false
IndentPPDirectives: AfterHash
IndentWidth: 4
IndentWrappedFunctionNames: false
# JavaImportGroups: []
# JavaScriptQuotes: Leave
# JavaScriptWrapImports: True
KeepEmptyLinesAtTheStartOfBlocks: false
Language: Cpp
MacroBlockBegin: ''
MacroBlockEnd: ''
MaxEmptyLinesToKeep: 1
# NamespaceIndentation: None
# ObjCBinPackProtocolList: Auto
# ObjCBlockIndentWidth: 2
# ObjCSpaceAfterProperty: false
# ObjCSpaceBeforeProtocolList: false

PenaltyBreakAssignment: 2
PenaltyBreakBeforeFirstCallParameter: 1
PenaltyBreakComment: 300
PenaltyBreakFirstLessLess: 120
PenaltyBreakString: 1000
# PenaltyBreakTemplateDeclaration: 10
PenaltyExcessCharacter: 1000000
PenaltyReturnTypeOnItsOwnLine: 60
PointerAlignment: Right
# RawStringFormats:
#   - Language: TextProto
#       Delimiters:
#         - 'pb'
#         - 'proto'
#       EnclosingFunctions:
#         - 'PARSE_TEXT_PROTO'
#       BasedOnStyle: google
#   - Language: Cpp
#       Delimiters:
#         - 'cc'
#         - 'cpp'
#       BasedOnStyle: llvm
#       CanonicalDelimiter: 'cc'
ReflowComments: true
SortIncludes: false
SpaceAfterCStyleCast: false
# SpaceAfterTemplateKeyword: true
SpaceBeforeAssignmentOperators: true
# SpaceBeforeCpp11BracedList: false
# SpaceBeforeCtorInitializerColon: true
# SpaceBeforeInheritanceColon: true
SpaceBeforeParens: ControlStatements
# SpaceBeforeRangeBasedForLoopColon: true
SpaceInEmptyParentheses: false
SpacesBeforeTrailingComments: 2
SpacesInAngles:  false
SpacesInCStyleCastParentheses: false
# SpacesInContainerLiterals: false
SpacesInParentheses: false
SpacesInSquareBrackets: false
# Standard: Cpp11
# This is nominally supported in clang-format version 8, but not in the build
# used by some of the core jemalloc developers.
# StatementMacros: []
TabWidth: 4
UseTab: Never
...

```


```
---
BasedOnStyle: Microsoft
AccessModifierOffset: -2
AlignAfterOpenBracket: Align
AllowAllArgumentsOnNextLine: false
AllowAllConstructorInitializersOnNextLine: false
AllowAllParametersOfDeclarationOnNextLine: false
AllowShortBlocksOnASingleLine: Never
AllowShortCaseLabelsOnASingleLine: true
AllowShortFunctionsOnASingleLine: None
AllowShortIfStatementsOnASingleLine: Never
AllowShortLambdasOnASingleLine: All
AllowShortLoopsOnASingleLine: false
AlwaysBreakAfterDefinitionReturnType: None
AlwaysBreakAfterReturnType: None
AlwaysBreakBeforeMultilineStrings: false
AlwaysBreakTemplateDeclarations: Yes
BinPackArguments: true
BinPackParameters: true
BreakBeforeBraces: Allman
BreakBeforeTernaryOperators: false
BreakInheritanceList: BeforeComma
BreakStringLiterals: false
ColumnLimit: 150
CompactNamespaces: false
ConstructorInitializerAllOnOneLineOrOnePerLine: false
Cpp11BracedListStyle: false
ExperimentalAutoDetectBinPacking: false
FixNamespaceComments: true
IncludeBlocks: Regroup
IndentCaseLabels: true
IndentPPDirectives: None
IndentWidth: 4
Language: Cpp
MaxEmptyLinesToKeep: 1
NamespaceIndentation: All
ReflowComments: true
SortIncludes: true
SortUsingDeclarations: true
SpaceAfterCStyleCast: true
SpaceAfterTemplateKeyword: false
SpaceBeforeParens: ControlStatements
SpaceBeforeRangeBasedForLoopColon: true
SpacesInParentheses: false
Standard: c++17
StatementMacros: [ Q_UNUSED LOG DEBUG ]
TabWidth: 4
UseTab: Never

...
```


```
---
Language:        Cpp
# BasedOnStyle:  Google
AccessModifierOffset: -4
AlignAfterOpenBracket: Align
AlignConsecutiveAssignments: false
AlignConsecutiveDeclarations: false
AlignEscapedNewlinesLeft: true
AlignOperands:   true
AlignTrailingComments: true
AllowAllParametersOfDeclarationOnNextLine: true
AllowShortBlocksOnASingleLine: false
AllowShortCaseLabelsOnASingleLine: false
AllowShortFunctionsOnASingleLine: All
AllowShortIfStatementsOnASingleLine: false
AllowShortLoopsOnASingleLine: false
AlwaysBreakAfterDefinitionReturnType: None
AlwaysBreakAfterReturnType: None
AlwaysBreakBeforeMultilineStrings: true
AlwaysBreakTemplateDeclarations: true
BinPackArguments: true
BinPackParameters: true
BraceWrapping:   
  AfterClass:      false
  AfterControlStatement: false
  AfterEnum:       false
  AfterFunction:   false
  AfterNamespace:  false
  AfterObjCDeclaration: false
  AfterStruct:     false
  AfterUnion:      false
  BeforeCatch:     false
  BeforeElse:      false
  IndentBraces:    false
BreakBeforeBinaryOperators: None
BreakBeforeBraces: Attach
BreakBeforeTernaryOperators: true
BreakConstructorInitializersBeforeComma: false
BreakAfterJavaFieldAnnotations: false
BreakStringLiterals: true
ColumnLimit:     80
CommentPragmas:  '^ IWYU pragma:'
ConstructorInitializerAllOnOneLineOrOnePerLine: true
ConstructorInitializerIndentWidth: 4
ContinuationIndentWidth: 4
Cpp11BracedListStyle: true
DerivePointerAlignment: true
DisableFormat:   false
ExperimentalAutoDetectBinPacking: false
ForEachMacros:   [ foreach, Q_FOREACH, BOOST_FOREACH ]
IncludeCategories: 
  - Regex:           '^<.*\.h>'
    Priority:        1
  - Regex:           '^<.*'
    Priority:        2
  - Regex:           '.*'
    Priority:        3
IncludeIsMainRegex: '([-_](test|unittest))?$'
IndentCaseLabels: true
IndentWidth:     4
IndentWrappedFunctionNames: false
JavaScriptQuotes: Leave
JavaScriptWrapImports: true
KeepEmptyLinesAtTheStartOfBlocks: false
MacroBlockBegin: ''
MacroBlockEnd:   ''
MaxEmptyLinesToKeep: 1
NamespaceIndentation: None
ObjCBlockIndentWidth: 4
ObjCSpaceAfterProperty: false
ObjCSpaceBeforeProtocolList: false
PenaltyBreakBeforeFirstCallParameter: 1
PenaltyBreakComment: 300
PenaltyBreakFirstLessLess: 120
PenaltyBreakString: 1000
PenaltyExcessCharacter: 1000000
PenaltyReturnTypeOnItsOwnLine: 200
PointerAlignment: Left
ReflowComments:  true
SortIncludes:    true
SpaceAfterCStyleCast: false
SpaceBeforeAssignmentOperators: true
SpaceBeforeParens: ControlStatements
SpaceInEmptyParentheses: false
SpacesBeforeTrailingComments: 2
SpacesInAngles:  false
SpacesInContainerLiterals: true
SpacesInCStyleCastParentheses: false
SpacesInParentheses: false
SpacesInSquareBrackets: false
Standard:        Auto
TabWidth:        8
UseTab:          Never
...

```
