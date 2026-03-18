#!/bin/bash

# ============================================
# CTYUNOS 系统 Docker 安装脚本
# ============================================

set -e

echo "========================================"
echo "  CTYUNOS Docker 安装脚本"
echo "========================================"
echo ""

# 检查是否root用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 root 用户运行此脚本"
    exit 1
fi

# 更新系统
echo "[1/5] 更新系统包..."
yum update -y || dnf update -y

# 安装依赖
echo "[2/5] 安装依赖..."
yum install -y device-mapper-persistent-data lvm2 curl || dnf install -y device-mapper-persistent-data lvm2 curl

# 使用二进制方式安装Docker
echo "[3/5] 安装Docker..."
DOCKER_VERSION="24.0.7"
curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_VERSION}.tgz" -o /tmp/docker.tgz

# 解压安装
tar -xzf /tmp/docker.tgz -C /tmp/
cp /tmp/docker/* /usr/bin/

# 创建docker组
groupadd -f docker

# 创建systemd服务文件
cat > /etc/systemd/system/docker.service << 'EOF'
[Unit]
Description=Docker Application Container Engine
Documentation=https://docs.docker.com
After=network-online.target firewalld.service
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/bin/dockerd
ExecReload=/bin/kill -s HUP $MAINPID
LimitNOFILE=infinity
LimitNPROC=infinity
TimeoutStartSec=0
Delegate=yes
KillMode=process
Restart=on-failure
StartLimitBurst=3
StartLimitInterval=60s

[Install]
WantedBy=multi-user.target
EOF

# 创建 containerd 服务文件
cat > /etc/systemd/system/containerd.service << 'EOF'
[Unit]
Description=containerd container runtime
Documentation=https://containerd.io
After=network.target

[Service]
ExecStart=/usr/bin/containerd
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动Docker服务
echo "[4/5] 启动Docker服务..."
systemctl daemon-reload
systemctl start containerd || true
systemctl start docker
systemctl enable docker

# 安装Docker Compose
echo "[5/5] 安装Docker Compose..."
DOCKER_COMPOSE_VERSION="v2.23.0"
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# 验证安装
echo ""
echo "========================================"
echo "  验证安装"
echo "========================================"
docker --version || echo "Docker版本检查失败"
docker-compose --version || echo "Docker Compose版本检查失败"

echo ""
echo "========================================"
echo "  Docker 安装完成!"
echo "========================================"
