#!/bin/bash

# 人力数字员工智能体系统 - 部署脚本
# 用于在远程服务器上部署和启动服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
REMOTE_HOST="root@121.229.172.161"
REMOTE_DIR="/root/shijingjing/e-employee"
LOCAL_DIR="."
CONDA_ENV="media_env"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  人力数字员工智能体系统 - 部署脚本  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 函数：在远程服务器执行命令
remote_exec() {
    ssh $REMOTE_HOST "$1"
}

# 步骤1：创建远程目录
echo -e "${YELLOW}[1/8] 创建远程目录...${NC}"
remote_exec "mkdir -p $REMOTE_DIR"

# 步骤2：上传代码
echo -e "${YELLOW}[2/8] 上传代码到远程服务器...${NC}"
# 排除不需要上传的文件
rsync -avz --exclude='.git' \
          --exclude='__pycache__' \
          --exclude='*.pyc' \
          --exclude='data/' \
          --exclude='models/' \
          --exclude='logs/' \
          --exclude='.env' \
          $LOCAL_DIR/ $REMOTE_HOST:$REMOTE_DIR/

# 步骤3：检查环境
echo -e "${YELLOW}[3/8] 检查远程环境...${NC}"
remote_exec "source /root/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && python --version"

# 步骤4：安装依赖
echo -e "${YELLOW}[4/8] 安装依赖...${NC}"
remote_exec "cd $REMOTE_DIR && source /root/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"

# 步骤5：创建必要目录
echo -e "${YELLOW}[5/8] 创建必要目录...${NC}"
remote_exec "cd $REMOTE_DIR && mkdir -p data documents logs models"

# 步骤6：初始化数据库
echo -e "${YELLOW}[6/8] 初始化数据库...${NC}"
remote_exec "cd $REMOTE_DIR && source /root/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && python scripts/init_database.py"

# 步骤7：构建知识库
echo -e "${YELLOW}[7/8] 构建知识库...${NC}"
remote_exec "cd $REMOTE_DIR && source /root/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && python scripts/build_knowledge_base.py"

# 步骤8：启动服务
echo -e "${YELLOW}[8/8] 启动服务...${NC}"
# 停止旧服务
remote_exec "pkill -f 'uvicorn app.main:app' || true"
sleep 2

# 启动新服务
remote_exec "cd $REMOTE_DIR && source /root/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 > logs/server.log 2>&1 &"

sleep 3

# 检查服务状态
if remote_exec "curl -s http://localhost:8000/health | grep -q 'healthy'"; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  部署成功！服务已启动  ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "服务地址: http://121.229.172.161:8000"
    echo "API文档: http://121.229.172.161:8000/docs"
    echo "健康检查: http://121.229.172.161:8000/health"
    echo ""
    echo "查看日志: ssh $REMOTE_HOST 'tail -f $REMOTE_DIR/logs/server.log'"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  部署可能失败，请检查日志  ${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "查看日志: ssh $REMOTE_HOST 'tail -n 50 $REMOTE_DIR/logs/server.log'"
    exit 1
fi
