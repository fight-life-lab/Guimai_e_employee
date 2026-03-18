#!/bin/bash

# ============================================
# NVIDIA Docker 安装脚本
# ============================================

set -e

echo "========================================"
echo "  NVIDIA Docker 安装脚本"
echo "========================================"
echo ""

# 检查是否root用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 root 用户运行此脚本"
    exit 1
fi

# 安装 nvidia-container-toolkit
echo "[1/3] 安装 nvidia-container-toolkit..."

# 添加 NVIDIA 容器工具包仓库
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
    tee /etc/yum.repos.d/nvidia-container-toolkit.repo

# 安装工具包
yum install -y nvidia-container-toolkit || dnf install -y nvidia-container-toolkit

# 配置 Docker 使用 nvidia 运行时
echo "[2/3] 配置 Docker..."
nvidia-ctk runtime configure --runtime=docker

# 重启 Docker
echo "[3/3] 重启 Docker..."
systemctl restart docker

echo ""
echo "========================================"
echo "  NVIDIA Docker 安装完成!"
echo "========================================"
echo ""
echo "测试命令: docker run --rm --runtime=nvidia --gpus all nvidia/cuda:12.0-base nvidia-smi"
