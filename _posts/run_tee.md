

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
log "开始构建 OP-TEE 系统"
make -j$(nproc) all || error "主系统构建失败"

# ---------- 7. 完成 ----------
# ---------- 6. 构建主系统 ----------
log "开始构建 OP-TEE 系统"
make -j$(nproc) all || error "主系统构建失败"
success "🎉 构建成功！"

# ---------- 7. 启动 QEMU ----------
launch_qemu() {
    log "启动 QEMU 模拟器"

    # 进入 build 目录
    cd "$BUILD_DIR" || error "无法进入 $BUILD_DIR"

    # 后台启动 QEMU（避免阻塞）
    make run > qemu.log 2>&1 &
    QEMU_PID=$!

    log "QEMU 已启动 (PID: $QEMU_PID)，日志保存在 qemu.log"
    sleep 8  # 等待系统启动

    # 检查是否启动成功
    if ! kill -0 $QEMU_PID 2>/dev/null; then
        error "QEMU 启动失败，请查看 qemu.log"
    fi

    success "QEMU 运行中..."
    echo "
📌 提示：
  - 登录：root（无密码）
  - 退出 QEMU：按 Ctrl+A，然后按 X
  - 查看日志：tail -f qemu.log
"
}

# ---------- 8. 运行 xtest 测试 ----------
run_xtest() {
    log "准备运行 xtest 测试套件"

    # 检查 xtest 是否已构建
    if [ ! -f "$WORK_DIR/optee_test/out/xtest/xtest" ]; then
        error "xtest 未找到，请确认 optee-test 构建成功"
    fi

    # 提示用户手动运行 xtest（因为需要交互）
    echo "
📌 请在 QEMU 终端中执行以下命令运行测试：

    /optee_test/run_xtest.sh

📌 或手动运行：

    xtest

📌 常见测试：
    xtest 1000    # 基础功能测试
    xtest 2000    # 加密测试
    xtest 3000    # 存储测试
"
}

# ---------- 9. 询问是否启动 QEMU ----------
ask_to_launch() {
    echo
    read -p "是否启动 QEMU 并运行测试? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        launch_qemu
        run_xtest
    else
        success "构建完成，未启动 QEMU"
        echo "
📌 启动手动命令：
  cd $BUILD_DIR && make run

📌 运行测试：
  登录后执行：/optee_test/run_xtest.sh
"
    fi
}

# ---------- 执行 ----------
ask_to_launch
```
