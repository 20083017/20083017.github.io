

clang   
clangd   
lldb   
clang-tidy   
sudo apt-get install clang-tools   


```
run-clang-tidy.py from llvm-project 从llvm-project中copy出来
```

.clang-tidy   
```
---
# 配置clang-tidy配置检测项，带'-'前缀的为disable对应的检测，否则为开启。这里主要是关闭一些用处不大，或者存在bug、假阳性的检查项
Checks: '*,
    -llvm-*,
    -llvmlibc-*,
    -altera-*,
    -android-*,
    -boost-*,
    -darwin-*,
    -fuchsia-*,
    -linuxkernel-*,
    -objc-*,
    -portability-*,
    -zircon-*,
    -clang-analyzer-osx*,
    -clang-analyzer-optin.cplusplus.UninitializedObject,
    -clang-analyzer-optin.cplusplus.VirtualCall,
    -clang-analyzer-core.NullDereference,
    -clang-analyzer-cplusplus.NewDelete,
    -clang-analyzer-cplusplus.PlacementNew,
    -clang-analyzer-cplusplus.NewDeleteLeaks,
    -clang-analyzer-cplusplus.Move,
    -clang-diagnostic-unused-parameter,
    -cppcoreguidelines-*,
    cppcoreguidelines-explicit-virtual-functions,
    cppcoreguidelines-special-member-functions,
    -cert-err58-cpp,
    -cert-env33-c,
    -cert-dcl37-c,
    -cert-dcl51-cpp,
    -google-runtime-int,
    -google-readability-casting,
    -google-readability-function-size,
    -google-readability-todo,
    -google-readability-braces-around-statements,
    -google-build-using-namespace,
    -readability-magic-numbers,
    -readability-implicit-bool-conversion,
    -readability-function-cognitive-complexity,
    -readability-isolate-declaration,
    -readability-convert-member-functions-to-static,
    -readability-container-size-empty,
    -readability-function-size,
    -readability-qualified-auto,
    -readability-make-member-function-const,
    -readability-named-parameter,
    -modernize-use-trailing-return-type,
    -modernize-avoid-c-arrays,
    -modernize-use-nullptr,
    -modernize-replace-disallow-copy-and-assign-macro,
    -modernize-use-bool-literals,
    -modernize-use-equals-default,
    -modernize-use-default-member-init,
    -modernize-use-auto,
    -modernize-loop-convert,
    -modernize-deprecated-headers,
    -modernize-raw-string-literal,
    -misc-no-recursion,
    -misc-unused-parameters,
    -misc-redundant-expression,
    -misc-non-private-member-variables-in-classes,
    -hicpp-*,
    hicpp-exception-baseclass,
    -performance-no-int-to-ptr,
    -bugprone-easily-swappable-parameters,
    -bugprone-implicit-widening-of-multiplication-result,
    -bugprone-integer-division,
    -bugprone-exception-escape,
    -bugprone-reserved-identifier,
    -bugprone-branch-clone,
    -bugprone-narrowing-conversions,
'
# 将警告转为错误
WarningsAsErrors: '*,-misc-non-private-member-variables-in-classes'
FormatStyle: file
# 过滤检查哪些头文件，clang-tidy会把源码依赖的头文件列出来都检查一遍，所以要屏蔽大量第三方库中的头文件
# 参考 https://stackoverflow.com/questions/71797349/is-it-possible-to-ignore-a-header-with-clang-tidy
# 该正则表达式引擎为llvm::Regex，支持的表达式较少，(?!xx)负向查找等都不支持
HeaderFilterRegex: '(xxx/include)*\.h$'
# 具体一些检查项的配置参数，可以参考的：
# https://github.com/envoyproxy/envoy/blob/main/.clang-tidy
# https://github.com/ClickHouse/ClickHouse/blob/d1d2f2c1a4979d17b7d58f591f56346bc79278f8/.clang-tidy
CheckOptions:
  - key: readability-identifier-naming.ClassCase
    value: CamelCase
  - key: readability-identifier-naming.EnumCase
    value: CamelCase
  - key: readability-identifier-naming.LocalVariableCase
    value: lower_case
  - key: readability-identifier-naming.StaticConstantCase
    value: aNy_CasE
  - key: readability-identifier-naming.PrivateMemberCase
    value: lower_case
  - key: readability-identifier-naming.PrivateMemberSuffix
    value: _
  - key: readability-identifier-naming.ProtectedMethodCase
    value: lower_case
  - key: readability-identifier-naming.ProtectedMethodSuffix
    value: _
  - key: readability-braces-around-statements.ShortStatementLines
    value: 2
  - key: readability-uppercase-literal-suffix.NewSuffixes
    value: 'f;u;ul'
  # Ignore GoogleTest function macros.
  - key: readability-identifier-naming.FunctionIgnoredRegexp
    value: '(TEST|TEST_F|TEST_P|INSTANTIATE_TEST_SUITE_P|MOCK_METHOD|TYPED_TEST)'
  - key: performance-move-const-arg.CheckTriviallyCopyableMove
    value: 0
  - key: cppcoreguidelines-special-member-functions.AllowSoleDefaultDtor
    value: 1
  - key: cppcoreguidelines-special-member-functions.AllowMissingMoveFunctions
    value: 1
  - key: cppcoreguidelines-special-member-functions.AllowMissingMoveFunctionsWhenCopyIsDeleted
    value: 1
```


test_clang.sh
```
#!/bin/bash

function say() {
  echo ">> $(date '+%Y-%m-%d %H:%M:%S') $*"
}

function cmd() {
  say "@$*"
  # shellcheck disable=SC2068
  $@ 2>&1
}

function join_by() {
  local IFS="$1"
  shift
  echo "$*"
}

function auto_fix_simple_code() {
  # 可以被自动修复的检查项，下面是一些能够稳定修复的常见错误
  AUTO_FIX_CHECKS_CFG=(
    "-*"
    "modernize-use-nullptr"
    "modernize-use-override"
    # "modernize-use-using"
    "modernize-make-shared"
    "boost-use-to-string"
    "readability-container-size-empty"
    "readability-redundant-access-specifiers"
    "readability-redundant-string-cstr"
    "readability-redundant-string-init"
    "readability-redundant-smartptr-get"
    "readability-redundant-control-flow"
    "google-readability-namespace-comments"
    "performance-unnecessary-copy-initialization"
    "performance-for-range-copy"
    "performance-noexcept-move-constructor"
    "clang-analyzer-deadcode.DeadStores"
  )
  echo "test 1"
  AUTO_FIX_CHECKS=$(join_by "," "${AUTO_FIX_CHECKS_CFG[@]}")
  #
  echo "test 2"
  ./run-clang-tidy.py -p "$BUILD_DIRECTORY" \
    -checks="$AUTO_FIX_CHECKS" \
    -fix $FILE \
    > /tmp/clang-tidy-fix.log 2>&1

  echo "test 3"
#   if [[ -n "${GITLAB_CI}" && "$(git status --short | wc -l)" != "0" ]]; then
#     set -e +o pipefail
#     # 存在被自动修复的变更，提交修复变更代码
#     cmd git add -u
#     cmd git commit -m "自动修复常规问题"
#     cmd git push "http://${CI_USER}:${CI_PRIVATE_TOKEN}@${CI_REPOSITORY_URL#*@}" "HEAD:${CI_MERGE_REQUEST_SOURCE_BRANCH_NAME}"
#     exit 0
#   fi
}

function clang_tidy_check_all() {
  # 检查仍然存在的问题
  say ./run-clang-tidy.py -p="$BUILD_DIRECTORY" \
    -config-file="../.vscode/.clang-tidy" $FILE
  ./run-clang-tidy.py -p="$BUILD_DIRECTORY" \
    -config-file="../.vscode/.clang-tidy" $FILE \
    > /tmp/clang-tidy-issue.log 2>&1

  if [[ -n "${GITLAB_CI}" ]]; then
    {
      echo "clang-tidy 检测结果："
      echo '```'
      grep -A 2 -E "error:.*\[.*\]" /tmp/clang-tidy-issue.log
      echo '```'
    #   echo "详情请点击pipeline⭕️图标进行查看"
    } > /tmp/clang-tidy-summary.log
    if [[ $(wc -l < "/tmp/clang-tidy-summary.log") -gt 4 ]]; then
      cmd add_comment "@/tmp/clang-tidy-summary.log" # add_comment 是CI中提供的一个命令，给对应MR中添加评论
      exit 255                                       # 使CI任务失败
    fi
  else
    {
      echo "clang-tidy 检测结果："
      echo '```'
      grep -E "error:.*\[.*\]" /tmp/clang-tidy-issue.log | grep -Eo "\[.*\]" | sort | uniq -c | sort -n
      echo '```'
    #   echo "详情请点击pipeline⭕️图标进行查看"
    } > /tmp/clang-tidy-summary.log
    cat /tmp/clang-tidy-issue.log
  fi
}

BUILD_DIRECTORY="../../native/cmake-build-script/linux-debug/x64-gnu-lite/"                  # cmake执行目录
# SOURCE_DIRECTORY=${CI_PROJECT_DIR:-$(pwd)} # 源码目录
# say "build cmake in $BUILD_DIRECTORY ..."
# mkdir -p $BUILD_DIRECTORY
# # 执行cmake build，-DCMAKE_EXPORT_COMPILE_COMMANDS=ON 使cmake生成单文件编译依赖配置文件，后续clang-tidy执行需要依赖该配置
# # 会在cmake build目录下生成一个 compile_commands.jso n文件
# cmd cd "$BUILD_DIRECTORY" \
#   && cmd cmake "$SOURCE_DIRECTORY" -DCMAKE_BUILD_TYPE:STRING=RelWithDebInfo -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
# cmd cd "$SOURCE_DIRECTORY"

if [[ -n "${GITLAB_CI}" ]]; then # gitlab CI中会定义GITLAB_CI变量
  # 运行在CI中
  M_SHA1=$(git rev-parse origin/master)
  # 过滤出本次MR中涉及修改的文件
  FILE=$(git diff --name-status "$M_SHA1" | grep -E "^(M|A)\s+(include|src)/.*\.(cc|cpp|h|hpp)$" | awk '!/tests/ { print $2 }')
  [[ "$FILE" == "" ]] && exit 0
else
  # 手动执行
  # FILE='.*\.(?:h|cc)*'
  # FILE='(?<!third\/).*\.(?:h|cpp)*'
  FILE='(?<!third\/!tool\/).*\.(?:h|cpp)*'
fi

echo "Files are ${FILE}"


case "$1" in
fix)
  auto_fix_simple_code
  ;;
check)
  clang_tidy_check_all
  ;;
esac
```
