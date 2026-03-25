#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试岗位说明书解析函数
"""

import pandas as pd
import os
import tempfile

# 直接复制 parse_job_description_excel 函数的代码
def parse_job_description_excel(file_path, emp_id, emp_name):
    """
    解析岗位说明书Excel文件
    
    Args:
        file_path: Excel文件路径
        emp_id: 员工ID
        emp_name: 员工姓名
        
    Returns:
        解析后的数据字典
    """
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path, header=None, dtype=str)
        
        # 初始化数据结构
        data = {
            'emp_id': emp_id,
            'emp_name': emp_name,
            'position_name': '',
            'department': '',
            'report_to': '',
            'position_purpose': '',
            'duties_and_responsibilities': [],
            'qualifications_education': {},
            'qualifications_major': {},
            'qualifications_job_work_experience': {},
            'qualifications_required_professional_certification': {},
            'qualifications_skills': {},
            'qualifications_others': {},
            'kpis': [],
            'working_hours_conditions': ''
        }
        
        # 解析基本信息 (第1-3行)
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            # 岗位名称、所在部门
            if '岗位名称' in str(row_values[0]):
                data['position_name'] = str(row_values[1]) if pd.notna(row_values[1]) else ''
                if len(row_values) > 2 and '所在部门' in str(row_values[2]):
                    data['department'] = str(row_values[3]) if len(row_values) > 3 and pd.notna(row_values[3]) else ''
            
            # 汇报对象
            if '汇报对象' in str(row_values[0]):
                data['report_to'] = str(row_values[1]) if pd.notna(row_values[1]) else ''
        
        # 解析岗位目的 (在"一、岗位目的："之后)
        purpose_started = False
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '一、岗位目的：' in str(row_values[0]):
                purpose_started = True
                continue
            
            if purpose_started and pd.notna(row_values[0]):
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('二、'):
                    break
                # 累加岗位目的内容
                if data['position_purpose']:
                    data['position_purpose'] += '\n'
                data['position_purpose'] += str(row_values[0])
        
        # 解析岗位职责 (在"二、岗位职责："之后)
        duties_started = False
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '二、岗位职责：' in str(row_values[0]):
                duties_started = True
                continue
            
            if duties_started:
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('三、'):
                    break
                
                # 跳过表头行
                if '职责模块' in str(row_values[0]) or '工作内容' in str(row_values[0]):
                    continue
                
                # 解析职责内容
                if pd.notna(row_values[0]) and len(row_values) > 1 and pd.notna(row_values[1]):
                    duty_module = str(row_values[0]).strip()
                    duty_content = str(row_values[1]).strip()
                    if duty_module and duty_content:
                        data['duties_and_responsibilities'].append({
                            'module': duty_module,
                            'content': duty_content
                        })
        
        # 解析任职资格 (在"三、任职资格："之后)
        qualifications_started = False
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '三、任职资格：' in str(row_values[0]):
                qualifications_started = True
                continue
            
            if qualifications_started:
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('四、'):
                    break
                
                # 跳过表头行
                if '维度' in str(row_values[0]) or '明细' in str(row_values[0]):
                    continue
                
                # 解析任职资格各维度
                if pd.notna(row_values[0]) and len(row_values) > 1 and pd.notna(row_values[1]):
                    dim_name = str(row_values[0]).strip()
                    dim_value = str(row_values[1]).strip()
                    
                    # 学历要求
                    if any(keyword in dim_name for keyword in ['学历', '文化程度', '教育背景']):
                        data['qualifications_education'] = {'requirement': dim_value}
                    # 专业认证要求
                    elif any(keyword in dim_name for keyword in ['专业认证', '必备专业认证', '资格证书', '证书要求']):
                        data['qualifications_required_professional_certification'] = {'requirement': dim_value}
                    # 专业要求
                    elif any(keyword in dim_name for keyword in ['专业', '专业要求', '专业背景', '所学专业', '专业知识']):
                        data['qualifications_major'] = {'requirement': dim_value}
                    # 工作经验要求
                    elif any(keyword in dim_name for keyword in ['工作经验', '岗位工作经验', '从业经验', '经验要求']):
                        data['qualifications_job_work_experience'] = {'requirement': dim_value}
                    # 知识技能要求
                    elif any(keyword in dim_name for keyword in ['知识技能', '知识技能能力', '技能要求', '能力要求']):
                        data['qualifications_skills'] = {'requirement': dim_value}
                    # 其他要求
                    elif '其他' in dim_name:
                        data['qualifications_others'] = {'requirement': dim_value}
        
        # 解析KPI (在"四、关键绩效指标（KPI）："之后)
        kpi_started = False
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '四、关键绩效指标' in str(row_values[0]):
                kpi_started = True
                continue
            
            if kpi_started:
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('五、'):
                    break
                
                # 跳过表头行
                if 'KPI指标' in str(row_values[0]) or '指标说明' in str(row_values[0]):
                    continue
                
                # 解析KPI内容
                if pd.notna(row_values[0]) and len(row_values) > 1 and pd.notna(row_values[1]):
                    kpi_indicator = str(row_values[0]).strip()
                    kpi_description = str(row_values[1]).strip()
                    if kpi_indicator and kpi_description:
                        data['kpis'].append({
                            'indicator': kpi_indicator,
                            'description': kpi_description
                        })
        
        # 解析工作时间条件 (在"五、工作时间条件："之后)
        working_hours_started = False
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '五、工作时间条件' in str(row_values[0]):
                working_hours_started = True
                continue
            
            if working_hours_started and pd.notna(row_values[0]):
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('六、'):
                    break
                # 累加工作时间条件内容
                if data['working_hours_conditions']:
                    data['working_hours_conditions'] += '\n'
                data['working_hours_conditions'] += str(row_values[0])
        
        return data
        
    except Exception as e:
        raise Exception(f"解析Excel文件失败: {str(e)}")

# 测试文件路径
file_path = '/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/20260309补充材料/岗位说明书/张谦乐-岗位说明书-内容运营.xlsx'
emp_id = 'TEST001'
emp_name = '张谦乐'

try:
    # 解析Excel文件
    data = parse_job_description_excel(file_path, emp_id, emp_name)
    
    # 打印解析结果
    print("=== 解析结果 ===")
    print(f"员工ID: {data['emp_id']}")
    print(f"员工姓名: {data['emp_name']}")
    print(f"岗位名称: {data['position_name']}")
    print(f"所在部门: {data['department']}")
    print(f"汇报对象: {data['report_to']}")
    print(f"岗位目的: {data['position_purpose']}")
    print(f"岗位职责数量: {len(data['duties_and_responsibilities'])}")
    print(f"KPI数量: {len(data['kpis'])}")
    print()
    print("=== 任职资格 ===")
    print(f"学历: {data['qualifications_education']}")
    print(f"专业: {data['qualifications_major']}")
    print(f"工作经验: {data['qualifications_job_work_experience']}")
    print(f"专业认证: {data['qualifications_required_professional_certification']}")
    print(f"知识技能: {data['qualifications_skills']}")
    print(f"其他: {data['qualifications_others']}")
    
except Exception as e:
    print(f"解析失败: {str(e)}")
    import traceback
    traceback.print_exc()
