
```
#!/bin/bash

# =====================================================
# 🛠️ OP-TEE 构建脚本（中国大陆优化版）
# 💡 特性：
#   - repo 工具及自身 manifest 从 清华镜像 下载（避免 gerrit.googlesource.com）
#   - OP-TEE 源码从 GitHub 官方同步（保证权威性）
#   - 支持断点续传、增量构建、WSL 兼容
#   - 自动修复 multiarch 头文件
#   - 详细日志与错误提示
#
# 🌐 使用场景：中国大陆网络环境
# 🔧 OP-TEE 版本：v3.20.0
#
# 🚀 使用方法：
#   chmod +x build_optee_china.sh
#   ./build_optee_china.sh
# =====================================================

set -euo pipefail  # 严格模式

# =====================================================
# 🔧 配置区
# =====================================================
WORK_DIR="$HOME/optee"                    # 工作目录
BUILD_DIR="$WORK_DIR/build"
TOOLCHAINS_DIR="$WORK_DIR/toolchains"
AARCH64_GCC="$TOOLCHAINS_DIR/aarch64/bin/aarch64-linux-gnu-gcc"
AARCH32_GCC="$TOOLCHAINS_DIR/arm/bin/arm-linux-gnueabihf-gcc"

OPTEE_RELEASE="3.20.0"                   # 可改为 latest 或具体标签
MANIFEST_URL="https://github.com/OP-TEE/manifest.git"
MANIFEST_FILE="default.xml"
JOBS=$(nproc)

# 清华镜像相关
REPO_BIN_DIR="$HOME/bin"
REPO_BIN_PATH="$REPO_BIN_DIR/repo"
REPO_URL_TUNA="https://mirrors.tuna.tsinghua.edu.cn/git/git-repo/"

# 依赖包
DEPS=("libgmp-dev" "libmpfr-dev" "libmpc-dev" "ninja-build" "rsync"
      "python3-pip" "bison" "flex" "libssl-dev" "libglib2.0-dev"
      "libfdt-dev" "libpixman-1-dev" "zlib1g-dev")

# =====================================================
# 📝 日志与工具函数
# =====================================================
log()   { echo -e "\n👉 $*"; }
info()  { echo -e "\n💡 INFO: $*"; }
warn()  { echo -e "\n⚠️  WARN: $*"; }
success() { echo -e "\n✅ SUCCESS: $*"; }
error() { echo -e "\n❌ ERROR: $*" >&2; exit 1; }
debug() { [[ "${DEBUG:-0}" == "1" ]] && echo -e "\n🔍 DEBUG: $*"; }

# =====================================================
# 🔍 环境检测
# =====================================================
check_environment() {
    log "🔍 检查系统环境"
    debug "OS: $(uname -srm)"
    if grep -qi microsoft /proc/version 2>/dev/null || [ -n "${WSL_DISTRO_NAME:-}" ]; then
        info "检测到 WSL 环境"
        export ON_WSL=1
    fi
}

# =====================================================
# 🌐 配置 repo 使用清华镜像（关键！）
# ✅ 彻底避免访问 gerrit.googlesource.com
# =====================================================
setup_repo_with_tuna() {
    log "🌐 配置 repo 使用清华镜像"

    # 1. 创建 bin 目录
    mkdir -p "$REPO_BIN_DIR"
    export PATH="$REPO_BIN_DIR:$PATH"

    # 2. 永久写入 .bashrc（避免重复添加）
    for line in "export PATH=\"$REPO_BIN_DIR:\$PATH\"" \
                "export REPO_URL=$REPO_URL_TUNA"; do
        if ! grep -qF "$line" ~/.bashrc; then
            echo "$line" >> ~/.bashrc
        fi
    done

    # 3. 设置 REPO_URL（核心：让 repo 自身从清华下载）
    export REPO_URL="$REPO_URL_TUNA"
    debug "REPO_URL=$REPO_URL"

    # 4. 下载 repo 脚本（如果不存在）
    if [ ! -f "$REPO_BIN_PATH" ]; then
        info "正在从清华镜像下载 repo 工具..."
        if curl -L --retry 3 -f -o "$REPO_BIN_PATH" "$REPO_URL_TUNA"; then
            chmod a+rx "$REPO_BIN_PATH"
            success "repo 已下载至: $REPO_BIN_PATH"
        else
            error "无法从清华镜像下载 repo，请检查网络或手动安装"
        fi
    else
        info "repo 已存在，跳过下载"
    fi

    # 5. 验证
    if ! repo --version >/dev/null 2>&1; then
        error "repo 安装失败，请检查权限或 PATH"
    fi
    success "repo 已配置为使用清华镜像"
}

# =====================================================
# 🌍 初始化并同步 OP-TEE 源码（从 GitHub）
# =====================================================
init_and_sync_optee() {
    log "📦 初始化 OP-TEE 源码 (版本: $OPTEE_RELEASE) → 从 GitHub 同步"

    cd "$WORK_DIR" || error "无法进入工作目录: $WORK_DIR"

    if [ -d ".repo" ]; then
        if [ ! -f ".repo/manifest.xml" ]; then
            warn ".repo 目录损坏，清理中..."
            rm -rf .repo
        else
            success "✅ 源码已存在，跳过 repo init/sync"
            return 0
        fi
    fi

    # 执行 repo init（使用 GitHub 官方仓库）
    info "初始化 repo 仓库..."
    debug "repo init -u $MANIFEST_URL -m $MANIFEST_FILE -b $OPTEE_RELEASE"
    if ! repo init -u "$MANIFEST_URL" -m "$MANIFEST_FILE" -b "$OPTEE_RELEASE"; then
        error "repo init 失败。请确认：
  - 网络是否通畅
  - 版本 '$OPTEE_RELEASE' 是否存在
  - REPO_URL 是否正确设置为清华镜像"
    fi

    # 同步源码（从 GitHub）
    info "开始同步 OP-TEE 源码（从 GitHub，可能较慢）..."
    debug "repo sync -c --no-tags --no-clone-bundle -j$JOBS"
    if ! repo sync -c --no-tags --no-clone-bundle -j"$JOBS"; then
        warn "多线程同步失败，尝试单线程..."
        if ! repo sync -c --no-tags --no-clone-bundle -j1; then
            error "repo sync 失败，请检查网络、磁盘空间或代理设置"
        fi
    fi

    success "🎉 源码同步完成！代码来自 GitHub 官方"
}

# =====================================================
# 📦 安装系统依赖
# =====================================================
install_dependencies() {
    log "🔧 安装系统依赖"

    sudo apt update || error "apt update 失败"

    sudo apt install -y \
        git make gcc gcc-aarch64-linux-gnu gcc-arm-linux-gnueabihf \
        g++-aarch64-linux-gnu g++-arm-linux-gnueabihf \
        libc6-dev libc6-dev-arm64-cross libc6-dev-armhf-cross \
        unzip wget curl python3 python3-pip || error "基础依赖安装失败"

    local missing=()
    for dep in "${DEPS[@]}"; do
        if ! dpkg -l | grep -q "^ii  $dep"; then
            missing+=("$dep")
        fi
    done

    if [ ${#missing[@]} -eq 0 ]; then
        success "所有依赖已安装"
        return
    fi

    warn "发现缺失依赖: ${missing[*]}"
    read -p "是否安装? [Y/n] " -n1 -r; echo
    [[ $REPLY =~ ^[Nn]$ ]] && error "请手动安装: sudo apt install ${missing[*]}"

    sudo apt install -y "${missing[@]}" || error "依赖安装失败"
    success "依赖安装完成"
}

# =====================================================
# 🧩 修复 multiarch 头文件问题
# =====================================================
fix_multiarch_headers() {
    log "🔧 修复 multiarch 头文件链接"

    local arch_dir="/usr/include/x86_64-linux-gnu"
    local headers=("gmp.h" "mpfr.h" "mpc.h")

    for header in "${headers[@]}"; do
        local src="$arch_dir/$header"
        local dst="/usr/include/$header"
        if [ -f "$src" ] && [ ! -f "$dst" ]; then
            sudo ln -sf "$src" "$dst"
            info "创建符号链接: $dst -> $src"
        elif [ ! -f "$src" ]; then
            error "未找到 $src，请确保 libgmp-dev / mpfr-dev / mpc-dev 已安装"
        fi
    done

    success "头文件修复完成"
}

# =====================================================
# 🛠️ 处理 toolchains（清理或重建）
# =====================================================
handle_toolchains() {
    log "🛠️  检查 toolchains 状态"

    if [ -f "$AARCH64_GCC" ] && [ -f "$AARCH32_GCC" ]; then
        success "toolchains 已存在，跳过重建"
        return
    fi

    warn "toolchains 缺失或不完整，执行清理并重建"

    cd "$BUILD_DIR" || error "进入构建目录失败"
    make distclean || true
    rm -rf "$TOOLCHAINS_DIR" out build 2>/dev/null || true

    info "重新构建工具链..."
    make -j"$JOBS" toolchains || error "工具链构建失败"
    success "工具链构建完成"
}

# =====================================================
# 🧼 设置干净环境（尤其 WSL）
# =====================================================
setup_clean_env() {
    log "🧼 设置构建环境"

    if [ "${ON_WSL:-0}" = "1" ]; then
        info "净化 WSL PATH（避免 Windows 干扰）"
        export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    fi
    debug "PATH: $PATH"
}

# =====================================================
# 🏗️ 构建主系统
# =====================================================
build_system() {
    log "🏗️  开始构建 OP-TEE"

    cd "$BUILD_DIR" || error "无法进入构建目录"
    make -j"$JOBS" all || error "构建失败"
    success "🎉 构建成功！"
}

# =====================================================
# ✅ 验证 xtest
# =====================================================
check_xtest() {
    local xtest_bin="$WORK_DIR/optee_test/out/xtest/xtest"
    [ -f "$xtest_bin" ] && success "xtest 测试套件就绪" || \
        error "xtest 未生成，请检查 build 配置"
}

# =====================================================
# 🖥️ 启动 QEMU
# =====================================================
launch_qemu() {
    log "🖥️  启动 QEMU"
    cd "$BUILD_DIR" || error "进入构建目录失败"
    make run > qemu.log 2>&1 &
    sleep 8
    if pgrep qemu >/dev/null; then
        success "QEMU 启动成功！登录: root (无密码)"
        echo "
📌 退出: Ctrl+A, 然后按 X
📌 日志: tail -f qemu.log
📌 测试: xtest 或 /optee_test/run_xtest.sh
"
    else
        error "QEMU 启动失败，请查看 qemu.log"
    fi
}

# =====================================================
# 🤔 询问是否启动
# =====================================================
ask_launch() {
    echo
    read -p "是否启动 QEMU? [y/N] " -n1 -r; echo
    [[ $REPLY =~ ^[Yy]$ ]] && launch_qemu || success "构建完成，未启动 QEMU"
}

# =====================================================
# 🚀 主流程
# =====================================================
main() {
    info "开始构建 OP-TEE v$OPTEE_RELEASE（中国大陆优化版）"
    debug "DEBUG 模式开启"

    check_environment
    setup_repo_with_tuna
    init_and_sync_optee
    install_dependencies
    fix_multiarch_headers
    handle_toolchains
    setup_clean_env
    build_system
    check_xtest
    ask_launch

    success "✅ 所有步骤完成！"
}

# =====================================================
# 🏁 入口
# =====================================================
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```


```
roborock@DESKTOP-B2S7H04:~/project$ cat run_tee_ultimate.sh
#!/bin/bash

# =====================================================
# OP-TEE 智能构建脚本（完整版）
# 功能：
#   - 自动安装缺失依赖
#   - 自动处理 multiarch 头文件路径（gmp.h, mpfr.h, mpc.h）
#   - 智能判断是否需要清理 toolchains
#   - 支持增量构建
# 用法：
#   chmod +x smart_build_optee.sh
#   ./smart_build_optee.sh
# =====================================================

set -e  # 遇错停止

# ---------- 配置 ----------
WORK_DIR="$HOME/optee"
BUILD_DIR="$WORK_DIR/build"
TOOLCHAINS_DIR="$WORK_DIR/toolchains"
AARCH64_GCC="$TOOLCHAINS_DIR/aarch64/bin/aarch64-linux-gnu-gcc"
AARCH32_GCC="$TOOLCHAINS_DIR/arm/bin/arm-linux-gnueabihf-gcc"

# 关键依赖列表
DEPS=("libgmp-dev" "libmpfr-dev" "libmpc-dev" "ninja-build" "rsync" "python3-pip" "bison" "flex" "libssl-dev")

# ---------- 工具函数 ----------
log() {
    echo -e "\n👉 $1"
}

error() {
    echo -e "\n❌ 错误: $1"
    exit 1
}

success() {
    echo -e "\n✅ $1"
}

# ---------- 1. 检查工作目录 ----------
log "检查工作目录"
if [ ! -d "$WORK_DIR" ]; then
    error "工作目录 $WORK_DIR 不存在，请先初始化仓库"
fi

cd "$WORK_DIR"

# ---------- 2. 检查并安装依赖 ----------
log "检查系统依赖"

echo "👉 步骤 2: 安装系统依赖"
sudo apt update
sudo apt install -y git make gcc gcc-aarch64-linux-gnu gcc-arm-linux-gnueabihf \
    libc6-dev libc6-dev-arm64-cross libc6-dev-armhf-cross \
    bison flex libssl-dev libglib2.0-dev \
    libfdt-dev libpixman-1-dev zlib1g-dev \
    python3 python3-pip unzip wget curl \
    g++-aarch64-linux-gnu g++-arm-linux-gnueabihf

MISSING_DEPS=()
for dep in "${DEPS[@]}"; do
    if ! dpkg -l | grep -q "^ii  $dep"; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    log "发现缺失依赖: ${MISSING_DEPS[*]}"
    read -p "是否安装? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sudo apt update
        sudo apt install -y "${MISSING_DEPS[@]}" || error "依赖安装失败"
        success "依赖安装完成"
    else
        error "请手动安装缺失依赖后重试"
    fi
fi

# ---------- 3. 自动处理 multiarch 头文件 ----------
fix_multiarch_headers() {
    local arch_dir="/usr/include/x86_64-linux-gnu"
    local headers=("gmp.h" "mpfr.h" "mpc.h")

    log "处理 multiarch 头文件路径（Debian/Ubuntu 标准）"

    for header in "${headers[@]}"; do
        if [ -f "$arch_dir/$header" ] && [ ! -f "/usr/include/$header" ]; then
            sudo ln -sf "$arch_dir/$header" "/usr/include/$header"
            echo "✅ 创建符号链接: /usr/include/$header -> $arch_dir/$header"
        elif [ -f "/usr/include/$header" ]; then
            echo "✅ /usr/include/$header 已存在，跳过"
        else
            error "未找到 $header，请检查 libgmp-dev / libmpfr-dev / libmpc-dev 是否安装"
        fi
    done
}

# 执行头文件修复
fix_multiarch_headers

# ---------- 4. 检查 toolchains 完整性 ----------
log "检查 toolchains 状态"
TOOLCHAINS_OK=true

if [ ! -d "$TOOLCHAINS_DIR" ]; then
    TOOLCHAINS_OK=false
else
    if [ ! -f "$AARCH64_GCC" ] || [ ! -f "$AARCH32_GCC" ]; then
        TOOLCHAINS_OK=false
    fi
fi

# ---------- 5. 决策是否需要清理 ----------
cd "$BUILD_DIR" || error "无法进入构建目录: $BUILD_DIR"

NEEDS_CLEAN=false

if [ "$TOOLCHAINS_OK" = false ]; then
    log "检测到 toolchains 不完整或不存在，需要清理重建"
    NEEDS_CLEAN=true
else
    success "toolchains 完整，跳过重建"
fi

if [ "$NEEDS_CLEAN" = true ]; then
    log "执行深度清理"
    make distclean || true
    rm -rf "$TOOLCHAINS_DIR" "$WORK_DIR/out" "$BUILD_DIR/build" 2>/dev/null || true
    success "清理完成"

    log "重新构建工具链"
    make -j$(nproc) toolchains || error "工具链构建失败"
else
    success "toolchains 完整，跳过重建"
fi

# ---------- 检测 WSL 并清理 PATH ----------
setup_clean_environment() {
    log "设置构建环境"

    # 检测 WSL
    if grep -qi microsoft /proc/version 2>/dev/null || [ -n "${WSL_DISTRO_NAME:-}" ]; then
        log "✅ 检测到 WSL: $WSL_DISTRO_NAME"
        log "🛡️  正在设置干净 PATH（移除 Windows 路径）"

        # 仅保留 Linux 安全路径
        export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        export PATH="$PATH:/usr/games:/usr/local/games"

        success "干净 PATH 已设置: $PATH"
    else
        log "🐧 非 WSL 环境，使用当前 PATH"
    fi

    # 再次验证 PATH
    if echo "$PATH" | tr ':' '\n' | grep -q '[[:space:][:cntrl:]]'; then
        error "PATH 仍包含空格或控制字符，请手动清理"
    fi
}

setup_clean_environment

# ---------- 6. 构建主系统 ----------
log "开始分步构建 OP-TEE 系统"
make -j$(nproc) all || error "主系统构建失败"
#make -j$(nproc) qemu          || error "QEMU 构建失败"
#make -j$(nproc) linux         || error "Linux 内核构建失败"
#make -j$(nproc) optee-os      || error "OP-TEE OS 构建失败"
#make -j$(nproc) optee-client-ext  || error "OP-TEE Client 构建失败"

# 关键：使用 optee-test-ext
#make -j$(nproc) optee-test-ext || error "OP-TEE Test (ext) 构建失败"
#make -j$(nproc) rootfs        || error "RootFS 构建失败"
#make                          || error "最终整合失败"

success "🎉 构建成功！"

# ---------- 7. 检查 xtest 是否生成 ----------
check_xtest() {
    local XTEST_BIN="$WORK_DIR/optee_test/out/xtest/xtest"
    if [ ! -f "$XTEST_BIN" ]; then
        error "xtest 未生成: $XTEST_BIN

请检查构建日志。常见原因：
  - build/conf/buildroot_config 中 BR2_PACKAGE_OPTEE_TEST_EXT=y
  - br-ext/package/optee_test_ext/ 存在
  - 已运行 make optee-test-ext"
    fi
    success "xtest 已就绪: $XTEST_BIN"
}

#check_xtest

# ---------- 8. 启动 QEMU ----------
launch_qemu() {
    log "启动 QEMU 模拟器"
    make run > qemu.log 2>&1 &
    QEMU_PID=$!
    sleep 8

    if ! kill -0 $QEMU_PID 2>/dev/null; then
        error "QEMU 启动失败，请查看 qemu.log"
    fi
    success "QEMU 运行中 (PID: $QEMU_PID)"
    echo "
📌 登录：root（无密码）
📌 退出 QEMU：Ctrl+A, X
📌 查看日志：tail -f qemu.log
"
}

# ---------- 9. 提示运行测试 ----------
run_xtest_hint() {
    echo "
📌 请在 QEMU 终端中运行测试：

    /optee_test/run_xtest.sh

📌 或直接运行：
    xtest

📌 常见测试：
    xtest 1000    # TEE Core
    xtest 2001    # Crypto
    xtest 3010    # Secure Storage
"
}

# ---------- 10. 询问是否启动 ----------
ask_to_launch() {
    echo
    read -p "是否启动 QEMU 并运行测试? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        launch_qemu
        run_xtest_hint
    else
        success "构建完成，未启动 QEMU"
        echo "
📌 手动启动：
  cd $BUILD_DIR && make run

📌 运行测试：
  登录后执行：/optee_test/run_xtest.sh
"
    fi
}

# ---------- 执行 ----------
ask_to_launch
```



```
#!/bin/bash

# =====================================================
# OP-TEE 智能构建脚本（修复完整版）
# 功能：
#   - 自动安装缺失依赖
#   - 自动处理 multiarch 头文件路径（gmp.h, mpfr.h, mpc.h）
#   - 智能判断是否需要清理 toolchains
#   - 支持增量构建
#   - 修复 repo 下载问题
# 用法：
#   chmod +x smart_build_optee.sh
#   ./smart_build_optee.sh
# =====================================================

set -e  # 遇错停止

# ---------- 配置 ----------
WORK_DIR="$HOME/optee"
BUILD_DIR="$WORK_DIR/build"
TOOLCHAINS_DIR="$WORK_DIR/toolchains"
AARCH64_GCC="$TOOLCHAINS_DIR/aarch64/bin/aarch64-linux-gnu-gcc"
AARCH32_GCC="$TOOLCHAINS_DIR/arm/bin/arm-linux-gnueabihf-gcc"

# 🔧 修复：定义 repo 和 manifest 相关变量
OPTEE_RELEASE="3.20.0"                         # 可改为 latest 或具体版本
MANIFEST_URL="https://github.com/OP-TEE/manifest.git"
MANIFEST_FILE="default.xml"
JOBS=$(nproc)                                  # 并行任务数

# 🔧 repo 官方下载地址（HTTPS）
REPO_URL="https://github.com/GerritCodeReview/git-repo/raw/main/repo"

# 关键依赖列表
DEPS=("libgmp-dev" "libmpfr-dev" "libmpc-dev" "ninja-build" "rsync" "python3-pip" "bison" "flex" "libssl-dev")

# ---------- 工具函数 ----------
log() {
    echo -e "\n👉 $1"
}

error() {
    echo -e "\n❌ 错误: $1"
    exit 1
}

success() {
    echo -e "\n✅ $1"
}

# 🔧 修复：定义 info 和 warn 函数
info() {
    echo -e "\n💡 $1"
}

warn() {
    echo -e "\n⚠️  $1"
}

# ---------- 修复 repo 工具 ----------
log "安装或更新 repo 工具"

# ---------- 安装 repo ----------
REPO_DIR="$HOME/.bin"
REPO_PATH="$REPO_DIR/repo"
mkdir -p "$REPO_DIR"
export PATH="$REPO_DIR:$PATH"
if ! grep -q 'export PATH="$HOME/.bin:$PATH"' ~/.bashrc; then
  echo 'export PATH="$HOME/.bin:$PATH"' >> ~/.bashrc
fi

if ! command -v repo >/dev/null 2>&1; then
  info "Installing repo tool from GitHub..."
  curl -L --retry 3 -o "$REPO_PATH" "$REPO_URL"
  chmod a+rx "$REPO_PATH"
else
  info "Repo tool already installed."
fi

# ---------- 初始化 ----------
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

info "Initializing OP-TEE manifest (release $OPTEE_RELEASE)..."

# 自动修复旧的损坏 repo 状态
if [ -d ".repo/repo" ] && [ ! -f ".repo/repo/main.py" ]; then
  warn ".repo/repo seems corrupted, removing..."
  rm -rf .repo/repo
fi
if [ -d ".repo" ] && [ ! -f ".repo/manifest.xml" ]; then
  warn ".repo directory incomplete, cleaning up..."
  rm -rf .repo
fi

if ! repo init -u "$MANIFEST_URL" -m "$MANIFEST_FILE" -b "$OPTEE_RELEASE"; then
  warn "Repo init failed, retrying..."
  rm -rf .repo
  repo init -u "$MANIFEST_URL" -m "$MANIFEST_FILE" -b "$OPTEE_RELEASE"
fi

info "Syncing sources..."
repo sync -c --no-tags --no-clone-bundle -j"$JOBS" || {
  warn "Sync failed — retrying single-thread..."
  repo sync -c --no-tags --no-clone-bundle -j1
}



mkdir -p ~/bin
export PATH=~/bin:$PATH

info "Installing or repairing Repo tool..."
if ! command -v repo >/dev/null 2>&1; then
  mkdir -p ~/.local/bin
  cd ~/.local/bin
  git clone https://github.com/GerritCodeReview/git-repo.git repo-tmp
  cp repo-tmp/repo repo
  chmod +x repo
  rm -rf repo-tmp
  export PATH="$HOME/.local/bin:$PATH"
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
else
    info "repo 已安装: $(repo --version)"
fi

# ---------- 初始化工作目录 ----------
log "初始化工作目录"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# ---------- 检查并安装依赖 ----------
log "检查系统依赖"

sudo apt update
sudo apt install -y git make gcc gcc-aarch64-linux-gnu gcc-arm-linux-gnueabihf \
    libc6-dev libc6-dev-arm64-cross libc6-dev-armhf-cross \
    bison flex libssl-dev libglib2.0-dev \
    libfdt-dev libpixman-1-dev zlib1g-dev \
    python3 python3-pip unzip wget curl \
    g++-aarch64-linux-gnu g++-arm-linux-gnueabihf

MISSING_DEPS=()
for dep in "${DEPS[@]}"; do
    if ! dpkg -l | grep -q "^ii  $dep"; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    log "发现缺失依赖: ${MISSING_DEPS[*]}"
    read -p "是否安装? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sudo apt update
        sudo apt install -y "${MISSING_DEPS[@]}" || error "依赖安装失败"
        success "依赖安装完成"
    else
        error "请手动安装缺失依赖后重试"
    fi
fi


# ---------- 6. 初始化仓库 ----------
log "初始化 OP-TEE 仓库 (release $OPTEE_RELEASE)"

cd "$WORK_DIR" || error "无法进入工作目录: $WORK_DIR"

if [ ! -d ".repo" ]; then
    info "首次初始化 repo 仓库..."
    repo init -u "$MANIFEST_URL" -m "$MANIFEST_FILE" -b "$OPTEE_RELEASE" || error "repo init 失败"
    
    info "同步源码（可能需要几分钟）..."
    repo sync -c --no-tags --no-clone-bundle -j"$JOBS" || {
        warn "同步失败，尝试单线程重试..."
        repo sync -c --no-tags --no-clone-bundle -j1 || error "repo sync 失败"
    }
    success "源码同步完成"
else
    success "仓库已存在，跳过 repo init/sync"
fi

# ---------- 3. 自动处理 multiarch 头文件 ----------
fix_multiarch_headers() {
    local arch_dir="/usr/include/x86_64-linux-gnu"
    local headers=("gmp.h" "mpfr.h" "mpc.h")

    log "处理 multiarch 头文件路径（Debian/Ubuntu 标准）"

    for header in "${headers[@]}"; do
        if [ -f "$arch_dir/$header" ] && [ ! -f "/usr/include/$header" ]; then
            sudo ln -sf "$arch_dir/$header" "/usr/include/$header"
            echo "✅ 创建符号链接: /usr/include/$header -> $arch_dir/$header"
        elif [ -f "/usr/include/$header" ]; then
            echo "✅ /usr/include/$header 已存在，跳过"
        else
            error "未找到 $header，请检查 libgmp-dev / libmpfr-dev / libmpc-dev 是否安装"
        fi
    done
}

# 执行头文件修复
fix_multiarch_headers

# ---------- 4. 检查 toolchains 完整性 ----------
log "检查 toolchains 状态"
TOOLCHAINS_OK=true

if [ ! -d "$TOOLCHAINS_DIR" ]; then
    TOOLCHAINS_OK=false
else
    if [ ! -f "$AARCH64_GCC" ] || [ ! -f "$AARCH32_GCC" ]; then
        TOOLCHAINS_OK=false
    fi
fi

# ---------- 5. 决策是否需要清理 ----------
cd "$BUILD_DIR" || error "无法进入构建目录: $BUILD_DIR"

NEEDS_CLEAN=false

if [ "$TOOLCHAINS_OK" = false ]; then
    log "检测到 toolchains 不完整或不存在，需要清理重建"
    NEEDS_CLEAN=true
else
    success "toolchains 完整，跳过重建"
fi

if [ "$NEEDS_CLEAN" = true ]; then
    log "执行深度清理"
    make distclean || true
    rm -rf "$TOOLCHAINS_DIR" "$WORK_DIR/out" "$BUILD_DIR/build" 2>/dev/null || true
    success "清理完成"

    log "重新构建工具链"
    make -j$(nproc) toolchains || error "工具链构建失败"
else
    success "toolchains 完整，跳过重建"
fi

# ---------- 检测 WSL 并清理 PATH ----------
setup_clean_environment() {
    log "设置构建环境"

    # 检测 WSL
    if grep -qi microsoft /proc/version 2>/dev/null || [ -n "${WSL_DISTRO_NAME:-}" ]; then
        log "✅ 检测到 WSL: $WSL_DISTRO_NAME"
        log "🛡️  正在设置干净 PATH（移除 Windows 路径）"

        # 仅保留 Linux 安全路径
        export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        export PATH="$PATH:/usr/games:/usr/local/games"

        success "干净 PATH 已设置: $PATH"
    else
        log "🐧 非 WSL 环境，使用当前 PATH"
    fi

    # 再次验证 PATH
    if echo "$PATH" | tr ':' '\n' | grep -q '[[:space:][:cntrl:]]'; then
        error "PATH 仍包含空格或控制字符，请手动清理"
    fi
}

setup_clean_environment


# ---------- 7. 构建主系统 ----------
log "开始构建 OP-TEE 系统"
cd "$BUILD_DIR" || error "无法进入构建目录"

make -j$(nproc) all || error "主系统构建失败"
success "🎉 构建成功！"

# ---------- 8. 检查 xtest 是否生成 ----------
check_xtest() {
    local XTEST_BIN="$WORK_DIR/optee_test/out/xtest/xtest"
    if [ ! -f "$XTEST_BIN" ]; then
        error "xtest 未生成: $XTEST_BIN

请检查构建日志。常见原因：
  - build/conf/buildroot_config 中 BR2_PACKAGE_OPTEE_TEST_EXT=y
  - br-ext/package/optee_test_ext/ 存在
  - 已运行 make optee-test-ext"
    fi
    success "xtest 已就绪: $XTEST_BIN"
}

check_xtest

# ---------- 9. 启动 QEMU ----------
launch_qemu() {
    log "启动 QEMU 模拟器"
    make run > qemu.log 2>&1 &
    QEMU_PID=$!
    sleep 8

    if ! kill -0 $QEMU_PID 2>/dev/null; then
        error "QEMU 启动失败，请查看 qemu.log"
    fi
    success "QEMU 运行中 (PID: $QEMU_PID)"
    echo "
📌 登录：root（无密码）
📌 退出 QEMU：Ctrl+A, X
📌 查看日志：tail -f qemu.log
"
}

# ---------- 10. 提示运行测试 ----------
run_xtest_hint() {
    echo "
📌 请在 QEMU 终端中运行测试：

    /optee_test/run_xtest.sh

📌 或直接运行：
    xtest

📌 常见测试：
    xtest 1000    # TEE Core
    xtest 2001    # Crypto
    xtest 3010    # Secure Storage
"
}

# ---------- 询问是否启动 ----------
ask_to_launch() {
    echo
    read -p "是否启动 QEMU 并运行测试? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        launch_qemu
        run_xtest_hint
    else
        success "构建完成，未启动 QEMU"
        echo "
📌 手动启动：
  cd $BUILD_DIR && make run

📌 运行测试：
  登录后执行：/optee_test/run_xtest.sh
"
    fi
}

# ---------- 执行 ----------
ask_to_launch
```


















