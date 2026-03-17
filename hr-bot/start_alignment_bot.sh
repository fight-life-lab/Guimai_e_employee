#!/bin/bash
# 人岗适配评估对话机器人启动脚本
# 在远程服务器 121.229.172.161 上运行

set -e

echo "=========================================="
echo "人岗适配评估对话机器人 - 启动脚本"
echo "=========================================="

# 配置
APP_DIR="/root/shijingjing/e-employee/hr-bot"
PORT=3111
CONDA_ENV="media_env"
LOG_FILE="$APP_DIR/logs/alignment_bot.log"
PID_FILE="$APP_DIR/alignment_bot.pid"

# 创建日志目录
mkdir -p "$APP_DIR/logs"

# 检查是否在正确的目录
cd "$APP_DIR" || {
    echo "错误: 无法进入应用目录 $APP_DIR"
    exit 1
}

echo "应用目录: $APP_DIR"
echo "服务端口: $PORT"

# 检查Conda环境
if ! command -v conda &> /dev/null; then
    echo "错误: Conda未安装"
    exit 1
fi

# 激活Conda环境
echo "激活Conda环境: $CONDA_ENV"
source $(conda info --base)/etc/profile.d/conda.sh
conda activate $CONDA_ENV || {
    echo "错误: 无法激活Conda环境 $CONDA_ENV"
    exit 1
}

echo "Python版本: $(python --version)"

# 检查依赖
echo "检查Python依赖..."
pip install -q aiomysql 2>/dev/null || echo "警告: aiomysql安装失败"

# 检查MySQL连接
echo "检查MySQL数据库连接..."
python3 -c "
import asyncio
import aiomysql

async def test_connection():
    try:
        conn = await aiomysql.connect(
            host='121.229.172.161',
            port=3306,
            user='hr_user',
            password='hr_password',
            db='hr_employee_db'
        )
        async with conn.cursor() as cur:
            await cur.execute('SELECT 1')
            result = await cur.fetchone()
            print('MySQL连接成功!')
        conn.close()
    except Exception as e:
        print(f'MySQL连接失败: {e}')

asyncio.run(test_connection())
" || echo "警告: MySQL连接检查失败"

# 检查vLLM服务
echo "检查vLLM服务..."
if curl -s http://121.229.172.161:8002/v1/models > /dev/null; then
    echo "vLLM服务运行正常"
else
    echo "警告: vLLM服务可能未运行，请检查Docker容器"
fi

# 检查ChromaDB服务
echo "检查ChromaDB服务..."
if curl -s http://121.229.172.161:8001/api/v1/heartbeat > /dev/null; then
    echo "ChromaDB服务运行正常"
else
    echo "警告: ChromaDB服务可能未运行"
fi

# 停止已有进程
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "停止已有进程 (PID: $OLD_PID)..."
        kill "$OLD_PID" || true
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

echo ""
echo "启动人岗适配评估服务..."
echo "日志文件: $LOG_FILE"
echo ""

# 启动服务
nohup python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --log-level info \
    >> "$LOG_FILE" 2>&1 &

# 保存PID
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"

echo "服务已启动 (PID: $NEW_PID)"
echo "等待服务初始化..."
sleep 3

# 检查服务是否正常运行
if ps -p "$NEW_PID" > /dev/null 2>&1; then
    echo ""
    echo "=========================================="
    echo "服务启动成功!"
    echo "=========================================="
    echo "API文档: http://121.229.172.161:$PORT/docs"
    echo "健康检查: http://121.229.172.161:$PORT/health"
    echo ""
    echo "人岗适配评估接口:"
    echo "  - 分析员工: POST http://121.229.172.161:$PORT/api/v1/alignment/analyze"
    echo "  - 流式分析: POST http://121.229.172.161:$PORT/api/v1/alignment/analyze/stream"
    echo "  - 对比员工: POST http://121.229.172.161:$PORT/api/v1/alignment/compare"
    echo "  - 评估维度: GET  http://121.229.172.161:$PORT/api/v1/alignment/dimensions"
    echo ""
    echo "查看日志: tail -f $LOG_FILE"
    echo "停止服务: kill $NEW_PID"
    echo "=========================================="
else
    echo "错误: 服务启动失败"
    echo "查看日志: $LOG_FILE"
    exit 1
fi
