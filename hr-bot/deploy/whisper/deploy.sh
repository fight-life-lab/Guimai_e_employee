#!/bin/bash
# Whisper API 部署脚本

set -e

echo "========================================="
echo "Whisper API Docker 部署脚本"
echo "========================================="

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose 未安装"
    echo "请先安装 Docker Compose"
    exit 1
fi

echo ""
echo "步骤 1: 创建模型目录..."
mkdir -p models

echo ""
echo "步骤 2: 构建Docker镜像..."
docker-compose build

echo ""
echo "步骤 3: 启动Whisper API服务..."
docker-compose up -d

echo ""
echo "步骤 4: 等待服务启动..."
sleep 5

echo ""
echo "步骤 5: 检查服务状态..."
if curl -s http://localhost:8003/health > /dev/null; then
    echo "✅ Whisper API 服务启动成功!"
    echo ""
    echo "服务地址: http://localhost:8003"
    echo "健康检查: http://localhost:8003/health"
    echo "API文档: http://localhost:8003/docs"
    echo ""
    echo "测试命令:"
    echo "  curl -X POST http://localhost:8003/transcribe -F 'audio_file=@your_audio.aac'"
else
    echo "⚠️ 服务可能还在启动中，请稍后再检查"
    echo "查看日志: docker-compose logs -f"
fi

echo ""
echo "========================================="
echo "部署完成!"
echo "========================================="
