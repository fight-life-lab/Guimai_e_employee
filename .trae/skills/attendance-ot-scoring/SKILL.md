---
name: "attendance-ot-scoring"
description: "批量修改考勤数据结构（增加20:30后加班统计）、实现工时态度评分计算。Invoke when user needs to add overtime scoring for work attitude, modify attendance Excel structure, or implement detailed bonus calculation with reasons."
---

# 考勤加班统计与工时态度评分 Skill

## 概述

本 Skill 用于处理考勤数据的结构修改和工时态度评分计算，包括：
1. 修改考勤汇总表结构（增加20:30后加班次数和时长字段）
2. 修改后端上传接口以支持新结构
3. 基于规则计算工时态度加分项并生成详细理由

## 环境配置

### 技术栈
- **后端框架**：Python 3.13 + FastAPI
- **前端技术**：HTML+JS
- **包管理**：Conda 环境 `media_env`
- **服务启动命令**：`uvicorn app.main:app --host 0.0.0.0 --port 3111`

### 服务器与目录
- **运行主机**：121.229.172.161
- **工作目录**：/root/shijingjing/e-employee
- **代码结构**：
  - Python 代码：`hr_bot/app/`
  - 静态文件：`hr_bot/static/`
  - 数据目录：`hr_bot/data/`
  - 日志目录：`hr_bot/logs/`
  - 导数目录：`hr_bot/import_data/`

### 数据库配置
- **MySQL**：
  - Host: `localhost`
  - Port: `3306`
  - DB: `hr_employee_db`
  - User: `hr_user`
  - Password: `hr_password`

### 服务配置
- **服务端口**：3111 (Uvicorn)
- **日志**：`./logs/hr-bot.log`，级别 `INFO`

## 执行步骤

### 步骤 1：修改 Excel 表结构

**目标文件**：`hr_bot/data/全汇总.xlsx`

**新增字段**：
- `加班2030后次数`：统计每月打卡时间在20:30及以后的次数
- `加班2030后时长`：统计每月20:30及以后打卡的加班时长

**实现方式**：
```python
import pandas as pd
from datetime import datetime, time

# 读取原始数据
df = pd.read_excel('全汇总.xlsx')

# 新增列
df['加班2030后次数'] = 0
df['加班2030后时长'] = 0.0

# 处理逻辑：根据打卡时间计算20:30后的加班
# 假设原始数据包含打卡时间字段（需要根据实际列名调整）
```

### 步骤 2：清理现有数据

```python
# 清空数据库中的考勤数据
DELETE FROM attendance_records;
# 或者清空汇总表
DELETE FROM attendance_summary;
```

### 步骤 3：修改后端上传接口

**修改文件位置**：`hr_bot/app/api/attendance.py` 或类似文件

**需要修改的内容**：
1. 修改上传接口的数据处理逻辑
2. 新增20:30后加班统计逻辑
3. 更新数据库写入逻辑（如果数据存储到 MySQL）

**核心逻辑示例**：
```python
from datetime import time

def calculate_overtime_2030(clock_out_time):
    """计算20:30后的加班次数和时长"""
    if clock_out_time >= time(20, 30):
        # 计算加班时长（从20:30到打卡时间）
        hours = (clock_out_time.hour - 20) + (clock_out_time.minute - 30) / 60
        return 1, hours
    return 0, 0.0

def process_attendance_data(df):
    """处理考勤数据"""
    overtime_2030_count = 0
    overtime_2030_hours = 0.0
    
    for _, row in df.iterrows():
        clock_out = row['下班打卡时间']  # 根据实际列名调整
        count, hours = calculate_overtime_2030(clock_out)
        overtime_2030_count += count
        overtime_2030_hours += hours
    
    return overtime_2030_count, overtime_2030_hours
```

### 步骤 4：SCP 代码至远程服务器

```bash
# 将本地代码同步到远程服务器
scp -r hr_bot/app/* root@121.229.172.161:/root/shijingjing/e-employee/hr_bot/app/
```

### 步骤 5：启动后端服务（远程）

```bash
# SSH 到远程服务器并启动服务
ssh root@121.229.172.161
cd /root/shijingjing/e-employee
# 激活 conda 环境（如果需要）
conda activate media_env
# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 3111
```

### 步骤 6：手动上传文件

等待用户上传 `全汇总.xlsx` 文件到系统。

### 步骤 7：验证数据库数据

```python
import pymysql

# 连接数据库
connection = pymysql.connect(
    host='localhost',
    port=3306,
    user='hr_user',
    password='hr_password',
    database='hr_employee_db'
)

# 查询验证
with connection.cursor() as cursor:
    sql = "SELECT * FROM attendance_summary LIMIT 10;"
    cursor.execute(sql)
    results = cursor.fetchall()
    for row in results:
        print(row)

connection.close()
```

### 步骤 8：计算工时态度加分项

**评分规则**（基础分70分，上限100分）：

#### 扣分项（自然年）
- **迟到/早退**：迟到豁免3次/月，在豁免基础上每多一次每次扣1分，最多扣10分
- **旷工**：每旷工1次，扣10分。年度旷工超过3次以上，本大项目直接0分

#### 加分项（累计得分）- 二选一
- **工作日加班**：
  - 按照17点30分为下班时间
  - 最晚打卡时间为18点30分及以后的，加1分
  - 20点30分及以后的，加3分
  - 最多加20分
  
- **月度加班时长**：
  - 月度加班时间达到36小时及以上的，加20分

#### 其他加分项
- **政治面貌**：中共党员加5分
- **党工团兼职**：党10分、团7分、工4分，最高10分

**实现代码示例**：
```python
def calculate_work_attitude_score(employee_data):
    """计算工时态度得分"""
    base_score = 70
    max_score = 100
    reasons = []
    
    # 1. 迟到/早退扣分
    late_count = employee_data.get('迟到次数', 0)
    exemption = 3  # 每月豁免3次
    late_penalty = max(0, (late_count - exemption)) * 1
    late_penalty = min(late_penalty, 10)  # 最多扣10分
    
    if late_penalty > 0:
        reasons.append(f"迟到{late_count}次，超出豁免{exemption}次，扣{late_penalty}分")
    
    # 2. 旷工扣分
    absent_count = employee_data.get('旷工次数', 0)
    absent_penalty = absent_count * 10
    if absent_count > 3:
        reasons.append(f"年度旷工{absent_count}次，超过3次，本项直接0分")
        return 0, reasons
    elif absent_penalty > 0:
        reasons.append(f"旷工{absent_count}次，扣{absent_penalty}分")
    
    # 3. 加班加分（二选一）
    overtime_bonus = 0
    
    # 方式1：基于打卡时间的加分
    overtime_1830_count = employee_data.get('加班1830后次数', 0)
    overtime_2030_count = employee_data.get('加班2030后次数', 0)
    
    bonus_1830 = min(overtime_1830_count, 20)  # 18:30后每次1分
    bonus_2030 = min(overtime_2030_count * 3, 20)  # 20:30后每次3分
    overtime_by_time = bonus_1830 + bonus_2030
    
    if overtime_by_time > 0:
        reasons.append(
            f"加班加分：18:30后加班{overtime_1830_count}次（每次1分），"
            f"20:30后加班{overtime_2030_count}次（每次3分），"
            f"共计加班{bonus_1830 + bonus_2030}分"
        )
    
    # 方式2：基于加班时长的加分
    monthly_overtime_hours = employee_data.get('月度加班时长', 0)
    overtime_by_hours = 20 if monthly_overtime_hours >= 36 else 0
    
    if overtime_by_hours > 0:
        reasons.append(f"月度加班时长{monthly_overtime_hours}小时，达到36小时标准，加20分")
    
    # 二选一，取高分
    overtime_bonus = max(overtime_by_time, overtime_by_hours)
    overtime_bonus = min(overtime_bonus, 20)  # 最多加20分
    
    # 4. 政治面貌加分
    is_party_member = employee_data.get('是否中共党员', False)
    party_bonus = 5 if is_party_member else 0
    if party_bonus > 0:
        reasons.append("中共党员，加5分")
    
    # 5. 党工团兼职加分
    party_position = employee_data.get('党工团兼职', '')
    position_bonus = 0
    if '党' in party_position:
        position_bonus = max(position_bonus, 10)
    elif '团' in party_position:
        position_bonus = max(position_bonus, 7)
    elif '工' in party_position:
        position_bonus = max(position_bonus, 4)
    position_bonus = min(position_bonus, 10)  # 最高10分
    
    if position_bonus > 0:
        reasons.append(f"党工团兼职（{party_position}），加{position_bonus}分")
    
    # 计算总分
    total_score = base_score - late_penalty - absent_penalty + overtime_bonus + party_bonus + position_bonus
    total_score = min(total_score, max_score)  # 不超过上限
    total_score = max(total_score, 0)  # 不低于0分
    
    # 生成详细理由
    final_reasons = [
        f"基础分{base_score}分",
        *reasons,
        f"最终得分：{total_score}分"
    ]
    
    return total_score, '\n'.join(final_reasons)

# 使用示例
result_score, result_reason = calculate_work_attitude_score({
    '迟到次数': 5,
    '旷工次数': 0,
    '加班1830后次数': 10,
    '加班2030后次数': 3,
    '月度加班时长': 40,
    '是否中共党员': True,
    '党工团兼职': '党员'
})
print(f"得分：{result_score}")
print(f"理由：{result_reason}")
```

### 步骤 9：SCP 到远程服务器并启动后端服务

```bash
# 同步最终代码
scp -r hr_bot/app/* root@121.229.172.161:/root/shijingjing/e-employee/hr_bot/app/

# 重启服务
ssh root@121.229.172.161 "cd /root/shijingjing/e-employee && \
    conda activate media_env && \
    uvicorn app.main:app --host 0.0.0.0 --port 3111 &"
```

## 注意事项

1. **Excel 列名适配**：根据实际 Excel 文件结构调整列名
2. **时间格式处理**：确保时间字段格式正确（datetime 或 time 类型）
3. **数据库表结构**：如需存储新字段，需先 ALTER TABLE 添加列
4. **评分规则**：严格按照提供的规则计算，特别是"二选一"的逻辑
5. **理由详细化**：在评分理由中必须明确说明从几月份到几月份、各时间段加班次数和加分详情

## 测试验证

完成开发后，需要验证：
1. Excel 数据结构是否正确
2. 数据库写入是否包含新字段
3. 评分计算是否符合规则
4. 理由描述是否详细准确
5. 远程服务是否正常运行
