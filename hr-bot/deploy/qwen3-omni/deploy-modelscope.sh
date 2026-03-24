#!/bin/bash
# Qwen3-Omni vLLM ModelScope 部署脚本

set -e

echo "========================================="
echo "Qwen3-Omni vLLM ModelScope 部署脚本"
echo "========================================="

# 检查GPU显存
echo ""
echo "检查 GPU 显存状态..."
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits

# 检查Docker
echo ""
echo "检查 Docker..."
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

# 检查当前运行的容器
echo ""
echo "当前运行的容器:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "警告: 当前 GPU 显存可能不足！"
echo "建议操作:"
echo "  1. 停止 whisper-api 服务释放显存"
echo "  2. 或者调整现有 vLLM 服务的显存占用"
echo ""
read -p "是否继续部署? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消部署"
    exit 0
fi

# 可选：停止 whisper-api 释放显存
echo ""
read -p "是否停止 whisper-api 服务以释放显存? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "停止 whisper-api..."
    docker stop whisper-api 2>/dev/null || true
fi

echo ""
echo "步骤 1: 创建模型目录..."
mkdir -p models

echo ""
echo "步骤 2: 拉取