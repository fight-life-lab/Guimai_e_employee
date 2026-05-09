#!/usr/bin/env python3
"""
批量修改文件，将硬编码的LLM配置改为使用config
"""

import re

files_to_fix = [
    "/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/app/api/interview_evaluation_routes_v2.py",
    "/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/app/api/batch_evaluation_routes.py",
    "/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/app/api/employee_recruitment_evaluation_routes.py",
    "/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/app/services/interview_services.py",
]

for filepath in files_to_fix:
    print(f"Processing {filepath}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否需要添加 get_settings import
    if 'from app.config import get_settings' not in content:
        # 在 imports 部分添加
        content = content.replace(
            'import aiohttp',
            'import aiohttp\n\nfrom app.config import get_settings'
        )

    # 替换 QWEN_API_URL, QWEN_API_KEY, QWEN_MODEL 的使用
    content = content.replace('QWEN_API_URL', 'settings.remote_llm_url')
    content = content.replace('QWEN_API_KEY', 'settings.remote_llm_api_key')
    content = content.replace('QWEN_MODEL', 'settings.remote_llm_model')

    # 在函数中添加 settings = get_settings()
    # 找到 async def 并使用这些变量的函数，添加 settings = get_settings()

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  Done!")

print("All files processed!")
