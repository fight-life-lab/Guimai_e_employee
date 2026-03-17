#!/usr/bin/env python3
"""测试不同prompt的评分效果"""
import asyncio
import json
from openai import AsyncOpenAI

# 测试数据
employees = {
    "石京京": {
        "total_records": 181,
        "late_days": 0,
        "overtime_days": 102,
        "school": "天津理工大学",
        "school_bonus": 1.8
    },
    "许博": {
        "total_records": 181,
        "late_days": 33,
        "overtime_days": 99,
        "school": "山东建筑大学",
        "school_bonus": 1.5
    }
}

# Prompt版本1：当前版本
prompt_v1 = """评分维度：工时维度

员工：{employee_name}

考勤数据（近12个月汇总）：
统计周期: 近6个月
总工作天数: {work_days}天
总迟到天数: {late_days}天
总加班天数: {overtime_days}天
每月明细: 2025-09月: 工作{work_days}天, 迟到{late_days}天, 加班{overtime_days}天

【强制规则 - 必须严格执行】

1. 首先检查【考勤数据】内容：
   - 如果显示"暂无考勤数据"或数据为空 → 直接给70分基准分
   - 如果有具体数据 → 按以下规则评分

2. 有数据时的评分规则：
   基础分70分（无迟到无加班的基准分）
   
   迟到扣分（在70分基础上扣分）：
   - 0次迟到 → 不扣分
   - 1-2次迟到 → -2分（轻微）
   - 3-5次迟到 → -5分（明显）
   - 6-9次迟到 → -10分（严重）
   - 10-15次迟到 → -15分（很严重）
   - >15次迟到 → -20分（极其严重）
   
   加班加分（在70分基础上加分）：
   - 加班天数1-5天 → +2分
   - 加班天数6-15天 → +5分
   - 加班天数16-30天 → +8分
   - 加班天数>30天 → +12分

3. 最终分数计算：
   最终分 = 70 + 加班加分 - 迟到扣分
   最低不低于0分，最高不超过100分

【严禁 - 重要】
1. 如果考勤数据显示"暂无考勤数据"，必须给70分，理由写"暂无考勤数据，按基准分70分计算"
2. 【严禁编造】不要编造具体的迟到次数、加班天数！
3. 【必须根据实际数据】理由中的数字必须与【考勤数据】中的实际数据完全一致！

输出JSON（仅包含该维度）：
{{
  "score": 82,
  "reasoning": "基础分70分，12个月内迟到0次不扣分，加班31天加12分，最终得分82分"
}}

示例2（有数据，迟到8次，加班5天）：
{{
  "score": 62,
  "reasoning": "基础分70分，迟到8次扣10分，加班5天加2分，最终得分62分"
}}"""

# Prompt版本2：更强调根据实际数据计算
prompt_v2 = """评分维度：工时维度

员工：{employee_name}

【实际考勤数据】
- 统计周期: 近6个月
- 总工作天数: {work_days}天
- 总迟到天数: {late_days}天
- 总加班天数: {overtime_days}天

【评分计算规则】
基础分70分

迟到扣分：
- 0次 → 不扣分
- 1-2次 → -2分
- 3-5次 → -5分
- 6-9次 → -10分
- 10-15次 → -15分
- >15次 → -20分

加班加分：
- 1-5天 → +2分
- 6-15天 → +5分
- 16-30天 → +8分
- >30天 → +12分

最终分 = 70 + 加班加分 - 迟到扣分

【任务】
根据上述【实际考勤数据】，严格按照【评分计算规则】计算分数。
必须给出具体的计算过程和最终分数。

输出JSON格式：
{{
  "score": <计算后的分数>,
  "reasoning": "<详细的计算过程>"
}}"""

# Prompt版本3：直接计算
prompt_v3 = """评分维度：工时维度

员工：{employee_name}

考勤数据：
- 迟到天数: {late_days}天
- 加班天数: {overtime_days}天

计算步骤：
1. 基础分 = 70分
2. 迟到扣分 = 根据{late_days}天迟到计算
3. 加班加分 = 根据{overtime_days}天加班计算
4. 最终分 = 70 - 迟到扣分 + 加班加分

请直接给出计算结果。

输出JSON：
{{
  "score": <分数>,
  "reasoning": "计算过程"
}}"""

async def test_prompt(client, model, employee_name, data, prompt_template, version):
    """测试单个prompt"""
    prompt = prompt_template.format(
        employee_name=employee_name,
        work_days=data["total_records"],
        late_days=data["late_days"],
        overtime_days=data["overtime_days"]
    )
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是HR评分专家，请根据提供的数据给出客观评分。只输出JSON格式。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.01,
        )
        
        content = response.choices[0].message.content
        # 提取JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group(0))
            return {
                "version": version,
                "employee": employee_name,
                "score": result.get("score"),
                "reasoning": result.get("reasoning", "")[:100]
            }
    except Exception as e:
        return {"version": version, "employee": employee_name, "error": str(e)}

async def main():
    client = AsyncOpenAI(
        base_url="http://localhost:8002/v1",
        api_key="dummy"
    )
    model = "qwen-14b-chat"
    
    print("=" * 80)
    print("Prompt测试 - 工时维度评分")
    print("=" * 80)
    
    prompts = [
        (prompt_v1, "V1-当前版本"),
        (prompt_v2, "V2-强调计算"),
        (prompt_v3, "V3-直接计算"),
    ]
    
    for prompt, version in prompts:
        print(f"\n{'='*80}")
        print(f"Prompt版本: {version}")
        print("=" * 80)
        
        for name, data in employees.items():
            result = await test_prompt(client, model, name, data, prompt, version)
            print(f"\n员工: {result['employee']}")
            print(f"  迟到: {data['late_days']}天, 加班: {data['overtime_days']}天")
            if 'error' in result:
                print(f"  错误: {result['error']}")
            else:
                print(f"  分数: {result['score']}")
                print(f"  理由: {result['reasoning']}")

if __name__ == "__main__":
    asyncio.run(main())
