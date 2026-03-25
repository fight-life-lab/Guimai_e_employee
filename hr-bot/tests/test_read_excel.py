#!/usr/bin/env python3
"""测试Excel文件读取"""

import pandas as pd
import os

# 测试江焕垣的文件
file_path = "/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表-江焕垣.xlsx"

print(f"测试文件: {file_path}")
print(f"文件存在: {os.path.exists(file_path)}")

if os.path.exists(file_path):
    try:
        print("\n正在读取文件...")
        df = pd.read_excel(file_path)
        print(f"成功读取，形状: {df.shape}")
        print("\n列名:")
        print(df.columns.tolist())
        
        print("\n前5行数据:")
        print(df.head())
        
        print("\n所有数据:")
        for col in df.columns:
            print(f"\n列: {col}")
            for val in df[col].dropna():
                if isinstance(val, str) and val.strip():
                    print(f"  - {val.strip()}")
                    
    except Exception as e:
        print(f"读取失败: {e}")
else:
    print("文件不存在")
