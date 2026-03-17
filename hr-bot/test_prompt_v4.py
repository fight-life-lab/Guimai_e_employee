#!/usr/bin/env python3
"""测试优化后的prompt"""
import asyncio
import json
from openai import AsyncOpenAI

# 测试数据
employees = {
    "石京京": {
        "late_days": 0,
        "overtime_days": 102,
    },
    "许博": {
        "late_days": 33,
        "overtime_days": 99,
    }
}

# Prompt版本4：基于V2优化
prompt_v4 = """评分维度：工时维度

员工：{employee_name}

【实际考勤数据】
- 统计周期: 近6个月
- 总迟到天数: {late_days}天
- 总加班天数: {overtime_days}天

【评分计算规则 - 必须严格执行】
基础分70分

迟到扣分（根据实际迟到天数）：
- 0次 → 扣0分
- 1-2次 → 扣2分
- 3-5次 → 扣5分
- 6-9次 → 扣10分
- 10-15次 → 扣15分
- >15次 → 扣20分

加班加分（根据实际加班天数）：
- 1-5天 → 加2分
- 6-15天 → 加5分
- 16-30天 → 加8分
- >30天 → 加12分

计算公式：最终分 = 70 + 加班加分 - 迟到扣分

【任务】
1. 根据【实际考勤数据】中的迟到天数，确定迟到扣分
2. 根据【实际考勤数据】中的加班天数，确定加班加分
3. 使用计算公式得出最终分数
4. 输出必须包含：基础分、迟到扣分、加班加分、最终分

输出JSON格式：
{{
  "score": <最终分数>,
  "reasoning": "基础分70分，迟到{late_days}天扣X分，加班{overtime_days}天加Y分，最终得分Z分"
}}"""

# Prompt版本5：更严格的格式
prompt_v5 = """评分维度：工时维度

员工：{employee_name}

考勤数据：
- 迟到天数 = {late_days}天
- 加班天数 = {overtime_days}天

评分规则：
基础分 = 70
迟到扣分 = 根据{late_days}查表: 0→0, 1-2→2, 3-5→5, 6-9→10, 10-15→15, >15→20
加班加分 = 根据{overtime_days}查表: 1-5→2, 6-15→5, 16-30→8, >30→12
最终分 = 70 + 加班加分 - 迟到扣分

请直接输出计算结果，不要解释。

{{
  "score": <最终分>,
  "reasoning": "基础分70分，迟到{late_days}天扣[扣分]分，加班{overtime_days}天加[加分]分，最终得分[最终分]分"
}}"""

async def test_prompt(client, model, employee_name, data, prompt_template, version):
    """测试单个prompt"""
    prompt = prompt_template.format(
        employee_name=employee_name,
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
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group(0))
            return {
                "version": version,
                "employee": employee_name,
                "late_days": data["late_days"],
                "overtime_days": data["overtime_days"],
                "score": result.get("score"),
                "reasoning": result.get("reasoning", "")[:150],
                "expected": 70 + (12 if data["overtime_days"] > 30 else 0) - (20 if data["late_days"] > 15 else 15 if data["late_days"] > 10 else 0)
            }
    except Exception as e:
        return {"version": version, "employee": employee_name, "error": str(e)}

async def main():
    client = AsyncOpenAI(
        base_url="http://localhost:8002/v1",
        api_key="dummy"
    )
    model = "qwen-14b-chat"
    
    print("=" * 100)
    print("Prompt优化测试 - 工时维度评分")
    print("=" * 100)
    print("\n预期分数：")
    print("  石京京: 70 + 12 - 0 = 82分 (迟到0天, 加班102天)")
    print("  许博: 70 + 12 - 20 = 62分 (迟到33天, 加班99天)")
    
    prompts = [
        (prompt_v4, "V4-明确计算步骤"),
        (prompt_v5, "V5-查表格式"),
    ]
    
    for prompt, version in prompts:
        print(f"\n{'='*100}")
        print(f"Prompt版本: {version}")
        print("=" * 100)
        
        for name, data in employees.items():
            result = await test_prompt(client, model, name, data, prompt, version)
            print(f"\n员工: {result['employee']}")
            print(f"  数据: 迟到{result['late_days']}天, 加班{result['overtime_days']}天")
            print(f"  预期: {result.get('expected', 'N/A')}分")
            if 'error' in result:
                print(f"  错误: {result['error']}")
            else:
                print(f"  实际: {result['score']}分")
                match = "✅" if result['score'] == result['expected'] else "❌"
                print(f"  匹配: {match}")
                print(f"  理由: {result['reasoning']}")

if __name__ == "__main__":
    asyncio.run(main())
