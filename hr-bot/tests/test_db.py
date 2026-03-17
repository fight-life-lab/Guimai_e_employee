#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Jingjing Shi
# @Date: 2026/3/13 11:03
# @Filename: test_db.py
# @Software: PyCharm
# @Description: 
#
import sqlite3
import json

conn = sqlite3.connect('./hr-bot/data/hr_database.db')
cursor = conn.cursor()

# 查询钱晓莹的岗位说明书
cursor.execute('''
    SELECT * FROM job_descriptions WHERE employee_id = 13
''')

row = cursor.fetchone()

if row:
    print('=' * 100)
    print('钱晓莹的岗位说明书详细信息')
    print('=' * 100)

    print('\n【基本信息】')
    print('ID: %d' % row[0])
    print('员工ID: %d' % row[1])
    print('岗位名称: %s' % row[2])
    print('部门: %s' % row[3])
    print('二级部门: %s' % row[4])
    print('专业条线: %s' % row[5])
    print('汇报对象: %s' % row[6])
    print('直接下属: %s' % row[7])

    print('\n【岗位目的】')
    print(row[8] if row[8] else '❌ 无数据')

    print('\n【岗位职责】')
    try:
        responsibilities = json.loads(row[9]) if row[9] else []
        if responsibilities:
            for i, resp in enumerate(responsibilities, 1):
                print('%d. %s' % (i, resp[:100] + '...' if len(resp) > 100 else resp))
        else:
            print('❌ 无数据')
    except Exception as e:
        print('解析错误: %s' % e)
        print('原始数据: %s' % row[9])

    print('\n【任职资格】')
    print('学历要求: %s' % (row[10] if row[10] else '❌ 无数据'))
    print('专业要求: %s' % (row[11] if row[11] else '❌ 无数据'))
    print('经验要求: %s' % (row[12] if row[12] else '❌ 无数据'))
    print('认证要求: %s' % (row[13] if row[13] else '❌ 无数据'))

    print('\n【知识技能】')
    print(row[14] if row[14] else '❌ 无数据')

    print('\n【KPI指标】')
    try:
        kpis = json.loads(row[15]) if row[15] else []
        if kpis:
            for kpi in kpis:
                print('- %s: %s' % (kpi.get('指标', ''),
                                    kpi.get('说明', '')[:80] + '...' if len(kpi.get('说明', '')) > 80 else kpi.get(
                                        '说明', '')))
        else:
            print('❌ 无数据')
    except Exception as e:
        print('解析错误: %s' % e)

    print('\n【工作条件】')
    try:
        conditions = json.loads(row[16]) if row[16] else []
        if conditions:
            for cond in conditions:
                print('- %s: %s' % (cond.get('项目', ''), cond.get('说明', '')))
        else:
            print('❌ 无数据')
    except Exception as e:
        print('解析错误: %s' % e)
else:
    print('❌ 未找到钱晓莹的岗位说明书')

conn.close()