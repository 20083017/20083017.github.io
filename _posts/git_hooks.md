

CMake 自动安装 git pre-commit hooks

手动配置 pre-commit
clang-format、pre-commit 可以通过 pip 来安装，安装完成后在你的项目目录下新建一个配置文件 .pre-commit-config.yaml，内容如下：  

```
repos:
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.0.1
    hooks:
    -   id: trailing-whitespace
    -   id: check-added-large-files
    -   id: check-merge-conflict
    -   id: end-of-file-fixer

-   repo: https://github.com/pocc/pre-commit-hooks
    rev: v1.3.4
    hooks:
    -   id: clang-format
        args: [--style=File]
```

通过 CMake 自动配置 pre-commit
在实际的团队协作中，你很难要求所有人都去手动安装这些钩子来提高代码可读性。特别是新人加入团队，如果这些环境都需要手动配置，   
那光配置项目的时间可能就要很久。所以我们希望它能自动化掉。我们的项目是通过 CMake 来管理的，所以可以在 CMake 中加入如下代码，   
让工程在初始化的时候自动去安装 clang-format、pre-commit，   
并自动执行 pre-commit install 将钩子安装到每个开发人员仓库的 .git/hooks 目录下。      

```
# Pre-commit hooks
IF (NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/.git/hooks/pre-commit)
    # FIND_PACKAGE(Python3 COMPONENTS Interpreter Development)
    IF (POLICY CMP0094)  # https://cmake.org/cmake/help/latest/policy/CMP0094.html
        CMAKE_POLICY(SET CMP0094 NEW)  # FindPython should return the first matching Python
    ENDIF ()
    # needed on GitHub Actions CI: actions/setup-python does not touch registry/frameworks on Windows/macOS
    # this mirrors PythonInterp behavior which did not consult registry/frameworks first
    IF (NOT DEFINED Python_FIND_REGISTRY)
        SET(Python_FIND_REGISTRY "LAST")
    ENDIF ()
    IF (NOT DEFINED Python_FIND_FRAMEWORK)
        SET(Python_FIND_FRAMEWORK "LAST")
    ENDIF ()
    FIND_PACKAGE(Python REQUIRED COMPONENTS Interpreter)
    MESSAGE(STATUS "Python executable: ${Python_EXECUTABLE}")
    EXECUTE_PROCESS(COMMAND sudo ${Python_EXECUTABLE} -m pip install clang-format pre-commit)
    EXECUTE_PROCESS(COMMAND pre-commit install WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
ENDIF ()
```
