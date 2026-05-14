#!/bin/bash

# ============================================================
# 对比本地与服务器版本
# ============================================================

set -e

# 配置
SSH_KEY="${SSH_KEY:-$HOME/Projects/Pem/odoo-2025.pem}"
SERVER_USER="${SERVER_USER:-ubuntu}"
SERVER_HOST="${SERVER_HOST:-54.65.127.141}"
SERVER_PATH="${SERVER_PATH:-/opt/seisei-project/odoo-addons/qr_ordering}"
LOCAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 构建 SSH 命令
if [ -f "$SSH_KEY" ]; then
    SSH_CMD="ssh -i $SSH_KEY"
    RSYNC_SSH_CMD="ssh -i $SSH_KEY"
else
    SSH_CMD="ssh"
    RSYNC_SSH_CMD="ssh"
    echo -e "${YELLOW}⚠️  未找到 SSH 密钥文件: ${SSH_KEY}${NC}"
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  对比本地与服务器版本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}配置信息:${NC}"
echo "  服务器: ${SERVER_USER}@${SERVER_HOST}"
echo "  服务器路径: ${SERVER_PATH}"
echo "  本地路径: ${LOCAL_PATH}"
echo ""

# 检查服务器连接
echo -e "${YELLOW}[检查] 检查服务器连接...${NC}"
if ! $SSH_CMD -o ConnectTimeout=5 "${SERVER_USER}@${SERVER_HOST}" "echo '连接成功'" > /dev/null 2>&1; then
    echo -e "${RED}❌ 无法连接到服务器${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 服务器连接正常${NC}"
echo ""

# 关键文件列表
KEY_FILES=(
    "__manifest__.py"
    "__init__.py"
    "static/src/js/pos_print_consumer.js"
    "static/src/js/qr_ordering_v2.js"
    "static/src/js/qr_ordering.js"
    "static/src/css/qr_ordering_v2.css"
    "controllers/qr_ordering_controller.py"
    "controllers/pos_print_controller.py"
    "models/pos_print_job.py"
    "security/ir.model.access.csv"
)

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  文件差异对比${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 对比每个关键文件
DIFF_COUNT=0
MISSING_COUNT=0
SAME_COUNT=0

for file in "${KEY_FILES[@]}"; do
    local_file="${LOCAL_PATH}/${file}"
    server_file="${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/${file}"
    
    echo -e "${BLUE}检查: ${file}${NC}"
    
    # 检查本地文件是否存在
    if [ ! -f "$local_file" ]; then
        echo -e "  ${RED}❌ 本地文件不存在${NC}"
        MISSING_COUNT=$((MISSING_COUNT + 1))
        echo ""
        continue
    fi
    
    # 检查服务器文件是否存在
    if ! $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" "test -f ${SERVER_PATH}/${file}" 2>/dev/null; then
        echo -e "  ${RED}❌ 服务器文件不存在${NC}"
        MISSING_COUNT=$((MISSING_COUNT + 1))
        echo ""
        continue
    fi
    
    # 使用 rsync 的 dry-run 模式检查差异
    DIFF_OUTPUT=$(rsync -avzn --dry-run -e "$RSYNC_SSH_CMD" \
        "$local_file" \
        "${server_file}" 2>&1 | grep -v "sending incremental" || true)
    
    if echo "$DIFF_OUTPUT" | grep -q ">f"; then
        echo -e "  ${YELLOW}⚠️  文件有差异${NC}"
        DIFF_COUNT=$((DIFF_COUNT + 1))
        
        # 显示简要差异（前10行）
        echo -e "  ${CYAN}差异预览:${NC}"
        $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" "cat ${SERVER_PATH}/${file}" 2>/dev/null | \
            diff -u "$local_file" - | head -20 | sed 's/^/    /' || true
    else
        echo -e "  ${GREEN}✅ 文件相同${NC}"
        SAME_COUNT=$((SAME_COUNT + 1))
    fi
    echo ""
done

# 使用 rsync 检查所有文件差异
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  完整目录差异（rsync dry-run）${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

echo -e "${YELLOW}本地 → 服务器 需要更新的文件:${NC}"
rsync -avzn --dry-run -e "$RSYNC_SSH_CMD" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.git' \
    --exclude='*.log' \
    --exclude='*.md' \
    "${LOCAL_PATH}/" \
    "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/" 2>&1 | \
    grep -E "^[<>]|^deleting|^$" | head -30 || echo "  无差异"

echo ""
echo -e "${YELLOW}服务器 → 本地 需要更新的文件:${NC}"
rsync -avzn --dry-run -e "$RSYNC_SSH_CMD" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.git' \
    --exclude='*.log' \
    --exclude='*.md' \
    "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/" \
    "${LOCAL_PATH}/" 2>&1 | \
    grep -E "^[<>]|^deleting|^$" | head -30 || echo "  无差异"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  对比总结${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  相同文件: ${GREEN}${SAME_COUNT}${NC}"
echo -e "  有差异文件: ${YELLOW}${DIFF_COUNT}${NC}"
echo -e "  缺失文件: ${RED}${MISSING_COUNT}${NC}"
echo ""


