#!/bin/bash

# 本地启动服务脚本
# 用于在本地开发环境启动服务

set -e

echo "========================================"
echo "  人力数字员工智能体系统 - 启动脚本  "
echo "========================================"
echo ""

# 激活conda环境
echo "[1/5] 激活 Conda 环境 media_env..."
source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || source /opt/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate media_env

# 检查Python版本
echo "[2/5] 检查 Python 版本..."
python --version

# 创建必要目录
echo "[3/5] 创建必要目录..."
mkdir -p data documents logs models

# 检查依赖
echo "[4/5] 检查依赖..."
pip install -q -r requirements.txt

# 初始化数据（如果数据库不存在）
if [ ! -f "data/hr_database.db" ]; then
    echo "[5/5] 初始化数据库..."
    python scripts/init_database.py
else
    echo "[5/5] 数据库已存在，跳过初始化"
fi

# 启动服务
echo ""
echo "========================================"
echo "  启动 FastAPI 服务..."
echo "========================================"
echo ""
echo "服务将在 http://localhost:8000 启动"
echo "API文档: http://localhost:8000/docs"
echo "按 Ctrl+C 停止服务"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
