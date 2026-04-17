#!/usr/bin/env python3
"""提取Word公告中的JD内容并保存"""

import json
import os
from docx import Document

doc_path = "/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/20260401 国脉文化公司战略与创新部副总经理总经理助理岗位招聘公告 V1.0- OA发布.docx"

doc = Document(doc_path)

# 提取所有段落文本
full_text = []
for para in doc.paragraphs:
    if para.text.strip():
        full_text.append(para.text)

# 合并文本
jd_content = "\n".join(full_text)

# 保存到共享资源文件
resources = {
    "job_description": jd_content,
    "evaluation_criteria": "",
    "interview_questions": []
}

output_path = "/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/_shared_resources.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(resources, f, ensure_ascii=False, indent=2)

print(f"JD内容已提取并保存到: {output_path}")
print(f"共 {len(jd_content)} 字符")
print("\n前500字符预览:")
print(jd_content[:500])
