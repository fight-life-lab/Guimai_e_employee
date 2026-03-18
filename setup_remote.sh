#!/bin/bash

# 远程服务器初始化脚本
# 在远程服务器上执行此脚本进行环境初始化

set -e

echo "========================================"
echo "  远程服务器环境初始化脚本  "
echo "========================================"
echo ""

REMOTE_DIR="/root/shijingjing/e-employee"
CONDA_ENV="media_env"

# 创建目录
echo "[1/6] 创建项目目录..."
mkdir -p $REMOTE_DIR
cd $REMOTE_DIR

# 检查conda环境
echo "[2/6] 检查 Conda 环境..."
source /root/anaconda3/etc/profile.d/conda.sh

if conda env list | grep -q "$CONDA_ENV"; then
    echo "环境 $CONDA_ENV 已存在"
else
    echo "创建环境 $CONDA_ENV..."
    conda create -n $CONDA_ENV python=3.9.25 -y
fi

# 激活环境
conda activate $CONDA_ENV

# 检查GPU
echo "[3/6] 检查 GPU 状态..."
nvidia-smi || echo "警告: 未检测到GPU"

# 创建目录结构
echo "[4/6] 创建目录结构..."
mkdir -p data documents logs models

# 等待代码上传
echo "[5/6] 等待代码上传..."
echo "请在本机运行: ./deploy.sh"
echo ""
echo "或者手动上传代码:"
echo "  scp -r hr-bot/ root@121.229.172.161:$REMOTE_DIR/"
echo ""

# 提示完成
echo "========================================"
echo "  远程服务器初始化完成！  "
echo "========================================"
echo ""
echo "下一步:"
echo "1. 在本地运行 ./deploy.sh 上传代码并启动服务"
echo "2. 或者手动上传代码后执行:"
echo "   cd $REMOTE_DIR"
echo "   pip install -r requirements.txt"
echo "   python scripts/init_database.py"
echo "   python scripts/build_knowledge_base.py"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
