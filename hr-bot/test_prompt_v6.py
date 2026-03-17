#!/usr/bin/env python3
"""测试最终优化prompt"""
import asyncio
import json
from openai import AsyncOpenAI

# 测试数据
employees = {
    "石京京": {"late_days": 0, "overtime_days": 102},
    "许博": {"late_days": 33, "overtime_days": 99},
}

# Prompt版本6：完全展开计算
prompt_v6 = """评分维度：工时维度

员工：{employee_name}

【考勤数据】
- 迟到天数: {late_days}
- 加班天数: {overtime_days}

【评分规则】
1. 基础分 = 70
2. 迟到扣分 = 查下表:
   - 如果迟到0次, 扣0分
   - 如果迟到1-2次, 扣2分
   - 如果迟到3-5次, 扣5分
   - 如果迟到6-9次, 扣10分
   - 如果迟到10-15次, 扣15分
   - 如果迟到>15次, 扣20分
3. 加班加分 = 查下表:
   - 如果加班1-5天, 加2分
   - 如果加班6-15天, 加5分
   - 如果加班16-30天, 加8分
   - 如果加班>30天, 加12分
4. 最终分 = 70 - 迟到扣分 + 加班加分

【计算】
该员工迟到{late_days}天, 对应扣分 = ?
该员工加班{overtime_days}天, 对应加分 = ?
最终分 = 70 - ? + ? = ?

【输出】
{{
  "score": <最终分的数字>,
  "reasoning": "基础分70分, 迟到{late_days}天扣[扣分]分, 加班{overtime_days}天加[加分]分, 最终得分[最终分]分"
}}"""

async def test_prompt(client, model, employee_name, data, prompt_template, version):
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
            # 计算预期分数
            late = data["late_days"]
            overtime = data["overtime_days"]
            late_deduction = 0 if late == 0 else 2 if late <= 2 else 5 if late <= 5 else 10 if late <= 9 else 15 if late <= 15 else 20
            overtime_bonus = 2 if overtime <= 5 else 5 if overtime <= 15 else 8 if overtime <= 30 else 12
            expected = 70 + overtime_bonus - late_deduction
            
            return {
                "version": version,
                "employee": employee_name,
                "late_days": late,
                "overtime_days": overtime,
                "score": result.get("score"),
                "reasoning": result.get("reasoning", "")[:200],
                "expected": expected,
                "calculation": f"70 + {overtime_bonus} - {late_deduction} = {expected}"
            }
    except Exception as e:
        return {"version": version, "employee": employee_name, "error": str(e)}

async def main():
    client = AsyncOpenAI(base_url="http://localhost:8002/v1", api_key="dummy")
    model = "qwen-14b-chat"
    
    print("=" * 100)
    print("Prompt最终测试 - 工时维度评分")
    print("=" * 100)
    print("\n预期计算:")
    print("  石京京: 迟到0天→扣0分, 加班102天→加12分, 70+12-0=82分")
    print("  许博: 迟到33天→扣20分, 加班99天→加12分, 70+12-20=62分")
    
    print(f"\n{'='*100}")
    print("Prompt版本: V6-完全展开")
    print("=" * 100)
    
    for name, data in employees.items():
        result = await test_prompt(client, model, name, data, prompt_v6, "V6")
        print(f"\n员工: {result['employee']}")
        print(f"  计算过程: {result.get('calculation', 'N/A')}")
        print(f"  预期分数: {result.get('expected', 'N/A')}分")
        if 'error' in result:
            print(f"  错误: {result['error']}")
        else:
            print(f"  实际分数: {result['score']}分")
            match = "✅" if result['score'] == result['expected'] else "❌"
            print(f"  匹配: {match}")
            print(f"  理由: {result['reasoning']}")

if __name__ == "__main__":
    asyncio.run(main())
