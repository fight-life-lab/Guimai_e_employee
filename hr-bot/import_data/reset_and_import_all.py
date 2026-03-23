#!/usr/bin/env python3
"""
一键清空并批量导入所有Excel文件
在远程服务器上运行

使用方法:
    python3 reset_and_import_all.py <excel文件目录>
    
示例:
    python3 reset_and_import_all.py /data/excel_files

目录中的Excel文件命名建议:
    - 试用期分数.xlsx 或 *试用期*.xlsx
    - 2021-2024绩效.xlsx 或 *绩效*.xlsx
    - 专家人才.xlsx 或 *专家*.xlsx
    - 职称技能.xlsx 或 *职称*.xlsx 或 *技能*.xlsx
    - 专利.xlsx 或 *专利*.xlsx
"""
import sys
import os
import glob
import pymysql

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'hr_user',
    'password': 'hr_password',
    'database': 'hr_employee_db',
    'charset': 'utf8mb4'
}


def clear_professional_ability_data():
    """清空ods_emp_professional_ability表的所有数据"""
    conn = pymysql.connect(**DB_CONFIG)
    
    try:
        with conn.cursor() as cursor:
            # 先查询有多少条数据
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability")
            count = cursor.fetchone()[0]
            print(f"当前表中共有 {count} 条数据")
            
            if count > 0:
                cursor.execute("TRUNCATE TABLE ods_emp_professional_ability")
                conn.commit()
                print(f"✅ 已清空所有 {count} 条数据")
            else:
                print("表中没有任何数据，无需清空")
                
    finally:
        conn.close()


def detect_file_type(filename):
    """根据文件名检测数据类型"""
    filename_lower = filename.lower()
    
    if '试用' in filename_lower:
        return 'probation', '试用期数据'
    elif '绩效' in filename_lower:
        return 'performance', '绩效考核数据'
    elif '专家' in filename_lower:
        return 'expert', '专家数据'
    elif '专利' in filename_lower:
        return 'patent', '专利数据'
    elif '职称' in filename_lower or '技能' in filename_lower:
        return 'title_skill', '职称技能数据'
    else:
        return None, None


def find_excel_files(directory):
    """查找目录中的所有Excel文件"""
    patterns = ['*.xlsx', '*.xls']
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(directory, pattern)))
    return sorted(files)


def import_single_file(file_path, data_type):
    """调用batch_import_excel.py导入单个文件"""
    import subprocess
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    import_script = os.path.join(script_dir, 'batch_import_excel.py')
    
    cmd = ['python3', import_script, file_path, data_type]
    
    print(f"\n{'='*60}")
    print(f"正在导入: {os.path.basename(file_path)}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    return result.returncode == 0


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 reset_and_import_all.py <excel文件目录>")
        print("")
        print("示例:")
        print("  python3 reset_and_import_all.py /data/excel_files")
        sys.exit(1)
    
    directory = sys.argv[1]
    
    if not os.path.isdir(directory):
        print(f"❌ 目录不存在: {directory}")
        sys.exit(1)
    
    print("=" * 60)
    print("一键清空并批量导入所有Excel文件")
    print("=" * 60)
    print()
    
    # 步骤1: 清空数据
    print("【步骤1】清空现有数据...")
    print("-" * 60)
    clear_professional_ability_data()
    
    # 步骤2: 查找Excel文件
    print("\n【步骤2】查找Excel文件...")
    print("-" * 60)
    
    excel_files = find_excel_files(directory)
    
    if not excel_files:
        print(f"❌ 在 {directory} 目录中没有找到Excel文件")
        sys.exit(1)
    
    print(f"找到 {len(excel_files)} 个Excel文件:")
    for i, f in enumerate(excel_files, 1):
        data_type, type_name = detect_file_type(os.path.basename(f))
        type_str = f" -> {type_name}" if type_name else " -> (类型未知)"
        print(f"  {i}. {os.path.basename(f)}{type_str}")
    
    # 步骤3: 导入文件
    print("\n【步骤3】开始导入数据...")
    
    success_files = []
    failed_files = []
    
    for file_path in excel_files:
        filename = os.path.basename(file_path)
        data_type, type_name = detect_file_type(filename)
        
        if not data_type:
            print(f"\n⚠️  跳过 {filename} (无法识别数据类型)")
            continue
        
        if import_single_file(file_path, data_type):
            success_files.append(filename)
        else:
            failed_files.append(filename)
    
    # 步骤4: 汇总结果
    print("\n" + "=" * 60)
    print("导入完成汇总")
    print("=" * 60)
    print(f"✅ 成功导入: {len(success_files)} 个文件")
    for f in success_files:
        print(f"   - {f}")
    
    if failed_files:
        print(f"\n❌ 导入失败: {len(failed_files)} 个文件")
        for f in failed_files:
            print(f"   - {f}")
    
    # 验证数据
    print("\n【步骤4】验证导入结果...")
    print("-" * 60)
    
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability")
            total_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability WHERE probation_score IS NOT NULL")
            probation_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability WHERE performance_history IS NOT NULL AND performance_history != '[]'")
            performance_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability WHERE is_company_expert=1 OR is_senior_expert=1 OR is_chief_expert=1")
            expert_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability WHERE professional_titles IS NOT NULL AND professional_titles != '[]'")
            title_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability WHERE patents_count > 0")
            patent_count = cursor.fetchone()[0]
            
            print(f"总记录数: {total_count}")
            print(f"  - 有试用期分数: {probation_count}")
            print(f"  - 有绩效数据: {performance_count}")
            print(f"  - 有专家身份: {expert_count}")
            print(f"  - 有职称: {title_count}")
            print(f"  - 有专利: {patent_count}")
    finally:
        conn.close()
    
    print("\n🎉 全部完成!")


if __name__ == "__main__":
    main()
