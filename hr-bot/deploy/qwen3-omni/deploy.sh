#!/bin/bash
# Qwen3-Omni vLLM 部署脚本

set -e

echo "========================================="
echo "Qwen3-Omni vLLM 部署脚本"
echo "========================================="

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose 未安装"
    exit 1
fi

# 检查NVIDIA Docker运行时
echo ""
echo "检查 NVIDIA Docker 运行时..."
if ! docker info | grep -q "nvidia"; then
    echo "警告: 未检测到 NVIDIA Docker 运行时"
    echo "请确保已安装 nvidia-docker2"
fi

echo ""
echo "步骤 1: 创建模型目录..."
mkdir -p models

echo ""
echo "步骤 2: 拉取 vLLM 镜像..."
docker pull vllm/vllm-openai:latest

echo ""
echo "步骤 3: 启动 Qwen3-Omni 服务..."
echo "注意: 首次启动会下载模型，可能需要较长时间..."
docker-compose up -d

echo ""
echo "步骤 4: 等待服务启动..."
echo "模型下载和加载可能需要 10-30 分钟，请耐心等待..."
sleep 10

# 检查服务状态
echo ""
echo "步骤 5: 检查服务状态..."
for i in {1..30}; do
    if curl -s http://localhost:8004/health > /dev/null 2>&1; then
        echo "✅ Qwen3-Omni 服务启动成功!"
        echo ""
        echo "服务地址: http://localhost:8004"
        echo "健康检查: http://localhost:8004/health"
        echo "API文档: http://localhost:8004/docs"
        echo ""
        echo "模型: Qwen/Qwen3-Omni-7B"
        echo "支持: 文本、图片、音频、视频"
        echo ""
        echo "查看日志: docker-compose logs -f"
        exit 0
    fi
    echo "等待服务启动... ($i/30)"
    sleep 10
done

echo ""
echo "⚠️ 服务启动超时，请检查日志:"
echo "  docker-compose logs -f"
echo ""
echo "可能的原因:"
echo "  1. 模型下载中，请继续等待"
echo "  2. GPU 内存不足"
echo "  3. 网络问题导致模型下载失败"
