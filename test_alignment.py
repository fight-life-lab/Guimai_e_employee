#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人岗适配性测试脚本
用于本地测试人岗适配分析功能
"""

import sys
import os
import json
import pandas as pd
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'hr-bot'))

# 先导入配置和数据库相关模块
from app.config import get_settings
from app.database.session import SessionLocal
from sqlalchemy.exc import SQLAlchemyError

from pydantic import BaseModel


class AlignmentAnalyzeRequest(BaseModel):
    """人岗适配分析请求模型"""
    employee_name: str
    position_name: str = None


def load_employees_from_excel(file_path):
    """
    从Excel文件加载员工列表
    """
    try:
        df = pd.read_excel(file_path)
        # 假设员工姓名在第一列
        employees = df.iloc[:, 0].dropna().tolist()
        return employees
    except Exception as e:
        print(f"读取Excel文件失败: {e}")
        return []


def test_database_connection():
    """
    测试数据库连接
    """
    print("测试数据库连接...")
    try:
        db = SessionLocal()
        # 测试数据库连接
        db.execute("SELECT 1")
        db.close()
        print("✅ 数据库连接成功")
        return True
    except SQLAlchemyError as e:
        print(f"❌ 数据库连接失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False


def test_single_employee(employee_name):
    """
    测试单个员工的人岗适配分析
    """
    print(f"\n=== 测试员工: {employee_name} ===")
    
    try:
        # 动态导入，避免启动时依赖
        from app.api.alignment_routes import analyze_alignment
        
        # 创建请求对象
        request = AlignmentAnalyzeRequest(employee_name=employee_name)
        
        # 执行分析
        result = analyze_alignment(request)
        
        # 输出结果
        if result.get('success'):
            data = result.get('data')
            print(f"✅ 分析成功")
            print(f"员工: {data.get('employee_name')}")
            print(f"部门: {data.get('department')}")
            print(f"岗位: {data.get('position')}")
            print(f"综合得分: {data.get('overall_score', 0):.1f}")
            print(f"岗位要求得分: {data.get('job_requirement_score', 0):.1f}")
            
            # 输出四象限结果
            quadrant = data.get('quadrant', {})
            print(f"\n四象限分析:")
            print(f"  象限: {quadrant.get('quadrant_name', '未知')}")
            print(f"  能力指数: {quadrant.get('ability_index', 0)}%")
            print(f"  匹配指数: {quadrant.get('match_index', 0)}%")
            print(f"  描述: {quadrant.get('quadrant_desc', '')}")
            
            # 输出各维度得分
            print(f"\n各维度得分:")
            for dim in data.get('dimensions', []):
                print(f"  {dim.get('name')}: {dim.get('score', 0):.1f}分 (要求: {dim.get('job_requirement', 0):.1f}分)")
            
            return True
        else:
            print(f"❌ 分析失败: {result.get('message', '未知错误')}")
            return False
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """
    主函数
    """
    print("人岗适配性测试脚本")
    print("=" * 50)
    
    # 测试数据库连接
    if not test_database_connection():
        print("数据库连接失败，无法继续测试")
        return
    
    # 员工列表
    employees = [
        "钱晓莹",
        "唐峥嵘",
        "刘天隽",
        "张谦乐",
        "胡冰",
        "尹娣"
    ]
    
    # 也可以从Excel文件加载
    # excel_path = "员工列表.xlsx"
    # if os.path.exists(excel_path):
    #     employees = load_employees_from_excel(excel_path)
    #     print(f"从Excel加载了 {len(employees)} 名员工")
    # else:
    #     print("未找到Excel文件，使用默认员工列表")
    
    # 测试每个员工
    results = []
    for emp in employees:
        success = test_single_employee(emp)
        results.append({"employee": emp, "success": success})
    
    # 输出测试结果汇总
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['employee']}")
    
    # 保存结果到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"alignment_test_results_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
