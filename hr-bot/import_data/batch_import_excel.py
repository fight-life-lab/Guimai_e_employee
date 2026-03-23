#!/usr/bin/env python3
"""
批量导入Excel文件到专业能力表
在远程服务器上直接运行，无需通过前端

使用方法:
    python3 batch_import_excel.py <excel文件路径> [数据类型]
    
示例:
    python3 batch_import_excel.py /data/试用期分数.xlsx probation
    python3 batch_import_excel.py /data/2021-2024绩效.xlsx performance
    python3 batch_import_excel.py /data/专家人才.xlsx expert
    python3 batch_import_excel.py /data/职称技能.xlsx title_skill
    python3 batch_import_excel.py /data/专利.xlsx patent
    
数据类型可选: probation(试用期), performance(绩效), expert(专家), title_skill(职称技能), patent(专利)
如果不指定数据类型，会自动检测
"""
import sys
import os
import pandas as pd
import pymysql
import json
from datetime import datetime

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'hr_user',
    'password': 'hr_password',
    'database': 'hr_employee_db',
    'charset': 'utf8mb4'
}


def detect_excel_type(columns):
    """根据列名自动检测Excel数据类型"""
    columns_str = ','.join([str(c).lower() for c in columns])
    
    # 试用期数据特征
    if '试用期分' in columns_str or ('考核时间' in columns_str and '考核人' in columns_str):
        return 'probation'
    
    # 绩效数据特征
    if any(year in columns_str for year in ['2021年度', '2022年度', '2023年度', '2024年度', '年度绩效']):
        return 'performance'
    
    # 专家数据特征
    if '专家' in columns_str and ('首席' in columns_str or '高级' in columns_str or '类别' in columns_str):
        return 'expert'
    
    # 专利数据特征
    if '专利' in columns_str or ('类别' in columns_str and ('发明' in columns_str or '实用新型' in columns_str)):
        return 'patent'
    
    # 职称/技能数据特征
    if '证书等级' in columns_str or '公司等级' in columns_str:
        return 'title_skill'
    
    # 默认类型
    return 'mixed'


def get_emp_code_and_name(row, columns):
    """从行数据中提取员工编号和姓名，支持多种列名"""
    emp_code = None
    emp_name = None
    
    # 尝试各种可能的列名
    for col in columns:
        col_lower = str(col).lower()
        if not emp_code and any(kw in col_lower for kw in ['员工id', '员工编号', '人员编码', '人员编号', 'emp_code', 'id']):
            emp_code = str(row.get(col, '')).strip()
        if not emp_name and any(kw in col_lower for kw in ['员工姓名', '姓名', 'name', '人员姓名']):
            emp_name = str(row.get(col, '')).strip()
    
    return emp_code, emp_name


def get_existing_record(cursor, emp_code):
    """查询现有记录"""
    cursor.execute("""
        SELECT * FROM ods_emp_professional_ability 
        WHERE emp_code = %s
    """, (emp_code,))
    return cursor.fetchone()


def import_probation_data(cursor, df, columns):
    """导入试用期数据"""
    success_count = 0
    update_count = 0
    
    for index, row in df.iterrows():
        emp_code, emp_name = get_emp_code_and_name(row, columns)
        if not emp_code or not emp_name:
            continue
        
        # 提取试用期分数
        probation_score = None
        for col in columns:
            if '试用期分' in str(col):
                try:
                    probation_score = float(row.get(col))
                    break
                except:
                    pass
        
        existing = get_existing_record(cursor, emp_code)
        if existing:
            if probation_score is not None:
                cursor.execute("""
                    UPDATE ods_emp_professional_ability 
                    SET emp_name = %s, probation_score = %s, updated_at = NOW()
                    WHERE emp_code = %s
                """, (emp_name, probation_score, emp_code))
                update_count += 1
        else:
            cursor.execute("""
                INSERT INTO ods_emp_professional_ability 
                (emp_code, emp_name, probation_score, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (emp_code, emp_name, probation_score))
            success_count += 1
    
    return success_count, update_count


def import_performance_data(cursor, df, columns):
    """导入绩效数据"""
    success_count = 0
    update_count = 0
    
    for index, row in df.iterrows():
        emp_code, emp_name = get_emp_code_and_name(row, columns)
        if not emp_code or not emp_name:
            continue
        
        # 提取绩效历史
        performance_history = []
        for col in columns:
            col_str = str(col)
            if '年度' in col_str or '绩效' in col_str:
                year = col_str.replace('年度', '').replace('绩效', '').strip()
                score_val = row.get(col)
                if pd.notna(score_val):
                    performance_history.append({
                        "year": year,
                        "score": str(score_val),
                        "level": str(score_val)
                    })
        
        existing = get_existing_record(cursor, emp_code)
        if existing:
            # 合并现有绩效数据
            existing_history = json.loads(existing[4]) if existing[4] else []
            existing_years = {p.get('year') for p in existing_history}
            for ph in performance_history:
                if ph['year'] not in existing_years:
                    existing_history.append(ph)
            
            cursor.execute("""
                UPDATE ods_emp_professional_ability 
                SET emp_name = %s, performance_history = %s, updated_at = NOW()
                WHERE emp_code = %s
            """, (emp_name, json.dumps(existing_history, ensure_ascii=False), emp_code))
            update_count += 1
        else:
            cursor.execute("""
                INSERT INTO ods_emp_professional_ability 
                (emp_code, emp_name, performance_history, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (emp_code, emp_name, json.dumps(performance_history, ensure_ascii=False) if performance_history else None))
            success_count += 1
    
    return success_count, update_count


def import_expert_data(cursor, df, columns):
    """导入专家数据"""
    success_count = 0
    update_count = 0
    
    for index, row in df.iterrows():
        emp_code, emp_name = get_emp_code_and_name(row, columns)
        if not emp_code or not emp_name:
            continue
        
        # 提取专家类别
        is_company_expert = 0
        is_senior_expert = 0
        is_chief_expert = 0
        
        for col in columns:
            col_str = str(col)
            val = str(row.get(col, '')).strip()
            if '专家' in col_str or '类别' in col_str:
                if '首席' in val:
                    is_chief_expert = 1
                elif '高级' in val:
                    is_senior_expert = 1
                elif '公司' in val or '专家' in val:
                    is_company_expert = 1
        
        existing = get_existing_record(cursor, emp_code)
        if existing:
            cursor.execute("""
                UPDATE ods_emp_professional_ability 
                SET emp_name = %s, is_company_expert = %s, is_senior_expert = %s, 
                    is_chief_expert = %s, updated_at = NOW()
                WHERE emp_code = %s
            """, (emp_name, is_company_expert, is_senior_expert, is_chief_expert, emp_code))
            update_count += 1
        else:
            cursor.execute("""
                INSERT INTO ods_emp_professional_ability 
                (emp_code, emp_name, is_company_expert, is_senior_expert, is_chief_expert, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """, (emp_code, emp_name, is_company_expert, is_senior_expert, is_chief_expert))
            success_count += 1
    
    return success_count, update_count


def import_patent_data(cursor, df, columns):
    """导入专利数据"""
    success_count = 0
    update_count = 0
    
    for index, row in df.iterrows():
        emp_code, emp_name = get_emp_code_and_name(row, columns)
        if not emp_code or not emp_name:
            continue
        
        existing = get_existing_record(cursor, emp_code)
        if existing:
            new_count = (existing[10] or 0) + 1
            cursor.execute("""
                UPDATE ods_emp_professional_ability 
                SET emp_name = %s, patents_count = %s, updated_at = NOW()
                WHERE emp_code = %s
            """, (emp_name, new_count, emp_code))
            update_count += 1
        else:
            cursor.execute("""
                INSERT INTO ods_emp_professional_ability 
                (emp_code, emp_name, patents_count, created_at, updated_at)
                VALUES (%s, %s, 1, NOW(), NOW())
            """, (emp_code, emp_name))
            success_count += 1
    
    return success_count, update_count


def import_title_skill_data(cursor, df, columns):
    """导入职称技能数据"""
    success_count = 0
    update_count = 0
    
    # 查找列
    name_col = None
    cert_col = None
    company_col = None
    
    for col in columns:
        col_str = str(col)
        if '名称' in col_str:
            name_col = col
        elif '证书等级' in col_str:
            cert_col = col
        elif '公司等级' in col_str:
            company_col = col
    
    for index, row in df.iterrows():
        emp_code, emp_name = get_emp_code_and_name(row, columns)
        if not emp_code or not emp_name:
            continue
        
        if name_col:
            title_name = str(row.get(name_col, '')).strip()
            cert_level = str(row.get(cert_col, '')).strip() if cert_col else ''
            company_level = str(row.get(company_col, '')).strip() if company_col else ''
            
            if title_name:
                new_title = {
                    "title_name": title_name,
                    "cert_level": cert_level,
                    "company_level": company_level
                }
                
                existing = get_existing_record(cursor, emp_code)
                if existing:
                    existing_titles = json.loads(existing[8]) if existing[8] else []
                    # 检查是否已存在相同职称
                    if not any(t.get('title_name') == title_name for t in existing_titles):
                        existing_titles.append(new_title)
                    
                    cursor.execute("""
                        UPDATE ods_emp_professional_ability 
                        SET emp_name = %s, professional_titles = %s, updated_at = NOW()
                        WHERE emp_code = %s
                    """, (emp_name, json.dumps(existing_titles, ensure_ascii=False), emp_code))
                    update_count += 1
                else:
                    cursor.execute("""
                        INSERT INTO ods_emp_professional_ability 
                        (emp_code, emp_name, professional_titles, created_at, updated_at)
                        VALUES (%s, %s, %s, NOW(), NOW())
                    """, (emp_code, emp_name, json.dumps([new_title], ensure_ascii=False)))
                    success_count += 1
    
    return success_count, update_count


def import_excel_file(file_path, data_type=None):
    """导入Excel文件"""
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"📄 正在读取文件: {file_path}")
    
    # 读取Excel文件
    df = pd.read_excel(file_path)
    columns = list(df.columns)
    
    print(f"📊 读取到 {len(df)} 行数据")
    print(f"📋 Excel列名: {columns}")
    
    if len(df) == 0:
        print("❌ Excel文件中没有数据")
        return False
    
    # 自动检测数据类型
    if not data_type:
        data_type = detect_excel_type(columns)
    
    type_names = {
        'probation': '试用期数据',
        'performance': '绩效考核数据',
        'expert': '专家数据',
        'patent': '专利数据',
        'title_skill': '职称技能数据',
        'mixed': '综合数据'
    }
    
    print(f"🔍 检测到数据类型: {type_names.get(data_type, '未知类型')} ({data_type})")
    
    # 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    
    try:
        with conn.cursor() as cursor:
            # 根据数据类型导入
            if data_type == 'probation':
                success_count, update_count = import_probation_data(cursor, df, columns)
            elif data_type == 'performance':
                success_count, update_count = import_performance_data(cursor, df, columns)
            elif data_type == 'expert':
                success_count, update_count = import_expert_data(cursor, df, columns)
            elif data_type == 'patent':
                success_count, update_count = import_patent_data(cursor, df, columns)
            elif data_type == 'title_skill':
                success_count, update_count = import_title_skill_data(cursor, df, columns)
            else:
                print(f"❌ 不支持的数据类型: {data_type}")
                return False
            
            conn.commit()
            
            print(f"\n✅ 导入完成!")
            print(f"   新增: {success_count} 条")
            print(f"   更新: {update_count} 条")
            print(f"   总计: {success_count + update_count} 条")
            
            return True
            
    except Exception as e:
        conn.rollback()
        print(f"❌ 导入失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    finally:
        conn.close()


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 batch_import_excel.py <excel文件路径> [数据类型]")
        print("")
        print("数据类型可选:")
        print("  probation    - 试用期数据")
        print("  performance  - 绩效考核数据")
        print("  expert       - 专家数据")
        print("  title_skill  - 职称技能数据")
        print("  patent       - 专利数据")
        print("")
        print("示例:")
        print("  python3 batch_import_excel.py /data/试用期分数.xlsx probation")
        print("  python3 batch_import_excel.py /data/2021-2024绩效.xlsx performance")
        sys.exit(1)
    
    file_path = sys.argv[1]
    data_type = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 60)
    print("批量导入Excel数据")
    print("=" * 60)
    print()
    
    success = import_excel_file(file_path, data_type)
    
    if success:
        print("\n🎉 导入成功!")
    else:
        print("\n❌ 导入失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()
