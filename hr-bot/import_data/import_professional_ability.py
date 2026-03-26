#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入员工专业能力数据
支持分批导入：试用期分数、绩效考核、专家、职称、职业技能、专利
"""

import pandas as pd
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.models.emp_professional_ability import EmpProfessionalAbility

# 获取数据库配置
settings = get_settings()
DATABASE_URL = f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}@localhost:{settings.mysql_port}/{settings.mysql_database}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def clear_table():
    """清空表数据"""
    with SessionLocal() as db:
        db.execute(text("TRUNCATE TABLE ods_emp_professional_ability"))
        db.commit()
        print("✓ 已清空 ods_emp_professional_ability 表")


def get_or_create_record(db, emp_code, emp_name):
    """获取或创建记录"""
    record = db.query(EmpProfessionalAbility).filter(
        EmpProfessionalAbility.emp_code == emp_code
    ).first()
    
    if not record:
        record = EmpProfessionalAbility(
            emp_code=emp_code,
            emp_name=emp_name
        )
        db.add(record)
        db.flush()  # 确保记录被创建并获取ID
    
    return record


def import_probation(file_path):
    """导入试用期分数"""
    print(f"\n导入试用期分数: {file_path}")
    df = pd.read_excel(file_path)
    
    with SessionLocal() as db:
        success_count = 0
        for _, row in df.iterrows():
            try:
                emp_code = str(row.get('员工id', '')).strip()
                emp_name = str(row.get('员工姓名', '')).strip()
                
                if not emp_code or not emp_name:
                    continue
                
                record = get_or_create_record(db, emp_code, emp_name)
                
                # 更新试用期分数
                probation_score = row.get('试用期分数')
                if pd.notna(probation_score):
                    record.probation_score = float(probation_score)
                
                success_count += 1
            except Exception as e:
                print(f"  错误: 处理 {emp_code} 失败: {e}")
        
        db.commit()
        print(f"✓ 成功导入 {success_count} 条试用期分数")


def import_performance(file_path):
    """导入绩效考核"""
    print(f"\n导入绩效考核: {file_path}")
    df = pd.read_excel(file_path)
    
    with SessionLocal() as db:
        success_count = 0
        for _, row in df.iterrows():
            try:
                emp_code = str(row.get('人员编码', '')).strip()
                emp_name = str(row.get('姓名', '')).strip()
                
                if not emp_code or not emp_name:
                    continue
                
                record = get_or_create_record(db, emp_code, emp_name)
                
                # 更新绩效历史
                performance_history = []
                for year in ['2021', '2022', '2023', '2024']:
                    col = f'{year}年度绩效'
                    if col in row and pd.notna(row.get(col)):
                        performance_history.append({
                            "year": year,
                            "score": str(row.get(col)),
                            "level": str(row.get(col))
                        })
                
                if performance_history:
                    # 合并现有绩效数据
                    existing_history = record.performance_history or []
                    existing_years = {p.get('year') for p in existing_history}
                    for ph in performance_history:
                        if ph['year'] not in existing_years:
                            existing_history.append(ph)
                    record.performance_history = existing_history
                
                success_count += 1
            except Exception as e:
                print(f"  错误: 处理 {emp_code} 失败: {e}")
        
        db.commit()
        print(f"✓ 成功导入 {success_count} 条绩效考核")


def import_expert(file_path):
    """导入专家信息"""
    print(f"\n导入专家信息: {file_path}")
    df = pd.read_excel(file_path)
    
    with SessionLocal() as db:
        success_count = 0
        for _, row in df.iterrows():
            try:
                emp_code = str(row.get('人员编码', '')).strip()
                emp_name = str(row.get('姓名', '')).strip()
                expert_type = str(row.get('专家', '')).strip()
                
                if not emp_code or not emp_name:
                    continue
                
                record = get_or_create_record(db, emp_code, emp_name)
                
                # 更新专家等级
                if '首席' in expert_type:
                    record.is_chief_expert = 1
                elif '高级' in expert_type:
                    record.is_senior_expert = 1
                elif '公司' in expert_type or '专家' in expert_type:
                    record.is_company_expert = 1
                
                success_count += 1
            except Exception as e:
                print(f"  错误: 处理 {emp_code} 失败: {e}")
        
        db.commit()
        print(f"✓ 成功导入 {success_count} 条专家信息")


def import_title(file_path):
    """导入职称信息"""
    print(f"\n导入职称信息: {file_path}")
    df = pd.read_excel(file_path)
    
    with SessionLocal() as db:
        success_count = 0
        for _, row in df.iterrows():
            try:
                emp_code = str(row.get('人员编码', '')).strip()
                emp_name = str(row.get('姓名', '')).strip()
                
                if not emp_code or not emp_name:
                    continue
                
                record = get_or_create_record(db, emp_code, emp_name)
                
                # 更新职称信息
                title_name = str(row.get('名称', '')).strip()
                cert_level = str(row.get('证书等级', '')).strip()
                company_level = str(row.get('公司等级', '')).strip()
                
                if title_name:
                    new_title = {
                        "title_name": title_name,
                        "cert_level": cert_level,
                        "company_level": company_level
                    }
                    
                    existing_titles = record.professional_titles or []
                    # 检查是否已存在相同职称
                    if not any(t.get('title_name') == title_name for t in existing_titles):
                        existing_titles.append(new_title)
                        record.professional_titles = existing_titles
                
                success_count += 1
            except Exception as e:
                print(f"  错误: 处理 {emp_code} 失败: {e}")
        
        db.commit()
        print(f"✓ 成功导入 {success_count} 条职称信息")


def import_skill(file_path):
    """导入职业技能"""
    print(f"\n导入职业技能: {file_path}")
    df = pd.read_excel(file_path)
    
    with SessionLocal() as db:
        success_count = 0
        for _, row in df.iterrows():
            try:
                emp_code = str(row.get('人员编码', '')).strip()
                emp_name = str(row.get('姓名', '')).strip()
                
                if not emp_code or not emp_name:
                    continue
                
                record = get_or_create_record(db, emp_code, emp_name)
                
                # 更新职业技能信息
                skill_name = str(row.get('名称', '')).strip()
                cert_level = str(row.get('证书等级', '')).strip()
                company_level = str(row.get('公司等级', '')).strip()
                
                if skill_name:
                    new_skill = {
                        "skill_name": skill_name,
                        "cert_level": cert_level,
                        "company_level": company_level
                    }
                    
                    existing_skills = record.professional_skills or []
                    # 检查是否已存在相同技能
                    if not any(s.get('skill_name') == skill_name for s in existing_skills):
                        existing_skills.append(new_skill)
                        record.professional_skills = existing_skills
                
                success_count += 1
            except Exception as e:
                print(f"  错误: 处理 {emp_code} 失败: {e}")
        
        db.commit()
        print(f"✓ 成功导入 {success_count} 条职业技能")


def import_patent(file_path):
    """导入专利信息"""
    print(f"\n导入专利信息: {file_path}")
    df = pd.read_excel(file_path)
    
    with SessionLocal() as db:
        success_count = 0
        for _, row in df.iterrows():
            try:
                emp_code = str(row.get('人员编码', '')).strip()
                emp_name = str(row.get('姓名', '')).strip()
                patent_name = str(row.get('名称', '')).strip()
                patent_type = str(row.get('类别', '')).strip()
                
                if not emp_code or not emp_name:
                    continue
                
                record = get_or_create_record(db, emp_code, emp_name)
                
                # 更新专利信息（JSON格式）
                if patent_name:
                    new_patent = {
                        "patent_name": patent_name,
                        "patent_type": patent_type
                    }
                    
                    existing_patents = record.patents or []
                    # 检查是否已存在相同专利
                    if not any(p.get('patent_name') == patent_name for p in existing_patents):
                        existing_patents.append(new_patent)
                        record.patents = existing_patents
                
                success_count += 1
            except Exception as e:
                print(f"  错误: 处理 {emp_code} 失败: {e}")
        
        db.commit()
        print(f"✓ 成功导入 {success_count} 条专利信息")


def main():
    """主函数"""
    print("=" * 60)
    print("员工专业能力数据导入工具")
    print("=" * 60)
    
    # 1. 清空表数据
    print("\n步骤1: 清空表数据")
    clear_table()
    
    # 2. 导入各类型数据
    base_path = "/root/shijingjing/e-employee/hr-bot/data/专业能力"
    
    print("\n步骤2: 导入各类专业能力数据")
    
    # 试用期分数
    import_probation(f"{base_path}/试用期分数.xlsx")
    
    # 绩效考核
    import_performance(f"{base_path}/【绩效考核】2021-2024员工考核结果（20250515整理，请勿外传！）.xlsx")
    
    # 专家
    import_expert(f"{base_path}/专家.xlsx")
    
    # 职称
    import_title(f"{base_path}/职称信息汇总.xlsx")
    
    # 职业技能
    import_skill(f"{base_path}/职业技能.xlsx")
    
    # 专利
    import_patent(f"{base_path}/专利.xlsx")
    
    print("\n" + "=" * 60)
    print("导入完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
