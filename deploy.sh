#!/bin/bash
# 人力数字员工系统部署脚本
# 目标服务器: 121.229.172.161
# 工作目录: /root/shijingjing/e-employee

set -e

echo "=== 人力数字员工系统部署 ==="
echo "目标服务器: 121.229.172.161"
echo ""

# 1. 传输修改的文件
echo "[1/4] 正在传输文件到远程服务器..."

# 主要修改文件：价值贡献路由
scp /Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/app/api/value_contribution_routes.py root@121.229.172.161:/root/shijingjing/e-employee/hr-bot/app/api/

# 价值数据文件
scp /Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/价值数据.xlsx root@121.229.172.161:/root/shijingjing/e-employee/hr-bot/data/

echo "[1/4] 文件传输完成"
echo ""

# 2. 远程执行部署命令
echo "[2/4] 正在远程服务器上执行部署..."

ssh root@121.229.172.161 << 'REMOTE_SCRIPT'
    echo "  -> 进入工作目录"
    cd /root/shijingjing/e-employee/hr-bot
    
    echo "  -> 查找并停止现有服务进程"
    # 查找并杀掉现有的 uvicorn 进程
    PID=$(ps aux | grep "uvicorn app.main:app" | grep -v grep | awk '{print $2}')
    if [ -n "$PID" ]; then
        echo "     发现现有进程 PID: $PID，正在停止..."
        kill -9 $PID
        sleep 2
        echo "     进程已停止"
    else
        echo "     未发现运行中的服务进程"
    fi
    
    echo "  -> 确保日志目录存在"
    mkdir -p /root/shijingjing/e-employee/hr-bot/logs
    
    echo "  -> 激活 Conda 环境"
    source /opt/miniconda3/bin/activate media_env
    
    echo "  -> 启动服务 (nohup 方式)"
    nohup uvicorn app.main:app --host 0.0.0.0 --port 3111 > /root/shijingjing/e-employee/hr-bot/logs/hr-bot.log 2>&1 &
    
    sleep 3
    
    # 检查服务是否启动成功
    NEW_PID=$(ps aux | grep "uvicorn app.main:app" | grep -v grep | awk '{print $2}')
    if [ -n "$NEW_PID" ]; then
        echo "  -> 服务启动成功，PID: $NEW_PID"
        echo "  -> 日志文件: /root/shijingjing/e-employee/hr-bot/logs/hr-bot.log"
    else
        echo "  -> [错误] 服务启动失败，请检查日志"
        exit 1
    fi
REMOTE_SCRIPT

echo "[2/4] 远程部署完成"
echo ""

# 3. 验证服务状态
echo "[3/4] 验证服务状态..."
sleep 2
ssh root@121.229.172.161 "ps aux | grep uvicorn | grep -v grep"
echo ""

# 4. 显示部署信息
echo "[4/4] 部署完成！"
echo ""
echo "=== 服务信息 ==="
echo "访问地址: http://121.229.172.161:3111"
echo "日志文件: /root/shijingjing/e-employee/hr-bot/logs/hr-bot.log"
echo ""
echo "=== 查看日志命令 ==="
echo "ssh root@121.229.172.161 'tail -f /root/shijingjing/e-employee/hr-bot/logs/hr-bot.log'"
echo ""
echo "=== 数据导入 ==="
echo "现在可以通过前端页面导入价值数据.xlsx文件了"
