#!/usr/bin/env python3
"""
AI评分器V2 - 基于规则的分维度评分
"""

import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import math


class AIScorerV2:
    """AI评分器V2 - 基于规则的分维度评分"""
    
    # ============ 各维度分数计算函数 ============
    
    def _calculate_professional_score(self, data: Dict) -> tuple:
        """计算专业能力分数
        
        优先级：
        1. 有试用期考核数据 → 直接使用考核总分
        2. 有薪酬数据 → 基于方差计算
        3. 有历史绩效数据 → 使用历史平均分
        4. 默认70分
        """
        employee_name = data.get("name", "")
        
        # 1. 优先使用试用期考核数据
        probation = data.get("probation_assessment", {})
        if probation.get("total_score"):
            score = probation["total_score"]
            return score, f"有试用期考核数据，直接使用考核总分{score}分"
        
        # 2. 使用历史绩效数据（针对特定员工）
        USE_HISTORICAL_PERFORMANCE = ["钱晓莹", "唐峥嵘", "刘天隽", "张谦乐"]
        if employee_name in USE_HISTORICAL_PERFORMANCE:
            historical_performance = data.get("historical_performance", [])
            if historical_performance:
                recent_years = [2022, 2023, 2024]
                recent_scores = []
                for perf in historical_performance:
                    if perf.get("year") in recent_years:
                        recent_scores.append(perf.get("performance_score", 70))
                
                if recent_scores:
                    avg_score = sum(recent_scores) / len(recent_scores)
                    score = round(avg_score)
                    years_str = ", ".join([f"{p['year']}年{p['performance_level']}" for p in historical_performance if p.get("year") in recent_years])
                    return score, f"基于历史年度考核：{years_str}，平均分{score}分"
        
        # 3. 基于薪酬数据（方差计算）
        salary_records = data.get("salary_records", [])
        if len(salary_records) >= 2:  # 至少需要2个月数据
            # 按月份排序
            sorted_records = sorted(salary_records, key=lambda x: x.get('month', ''))
            
            # 排除首月、12月、2月份数据
            filtered_records = sorted_records[1:]  # 排除首月
            filtered_records = [r for r in filtered_records if not str(r.get('month', '')).endswith('12')]  # 排除12月
            filtered_records = [r for r in filtered_records if not str(r.get('month', '')).endswith('02')]  # 排除2月
            
            # 如果数据不足，返回70分并提示考核周期短
            if len(filtered_records) < 2:
                return 70, "考核周期较短（排除首月、12月、2月后数据不足），建议再次观察，暂按基准分70分计算"
            
            # 计算绩效工资（bonus = 月度+效益+年度）
            bonus_values = []
            for record in filtered_records:
                bonus = (record.get("monthly_performance", 0) or 0) + \
                       (record.get("benefit_performance", 0) or 0) + \
                       (record.get("annual_performance", 0) or 0)
                if bonus > 0:
                    bonus_values.append(bonus)
            
            if len(bonus_values) >= 2:
                # 计算方差和标准差
                mean_bonus = sum(bonus_values) / len(bonus_values)
                variance = sum((x - mean_bonus) ** 2 for x in bonus_values) / len(bonus_values)
                std_dev = variance ** 0.5
                
                # 变异系数（标准差/平均值）
                cv = (std_dev / mean_bonus * 100) if mean_bonus > 0 else 0
                
                # 使用函数计算分数（国企背景：波动小，需要放大波动影响）
                # 基准分70分，变异系数为0时，分数为70分
                # 使用指数函数放大波动：score = 70 - (cv^1.5) * 0.5
                # 当cv=0时，score=70；当cv=10时，score≈54；当cv=20时，score≈25
                score = 70 - math.pow(cv, 1.5) * 0.5
                score = max(0, min(100, score))
                score = round(score)
                
                # 根据分数给出评价
                if score >= 80:
                    stability = "非常稳定"
                elif score >= 70:
                    stability = "较稳定"
                elif score >= 60:
                    stability = "一般稳定"
                elif score >= 40:
                    stability = "波动较大"
                else:
                    stability = "波动很大"
                
                reason = f"绩效工资{stability}（方差={variance:.0f}, 标准差={std_dev:.0f}, 变异系数={cv:.1f}%, 函数得分={score}分）"
                return score, reason
        
        # 4. 默认70分
        return 70, "暂无薪酬数据，按基准分70分计算"
    
    def _calculate_adaptability_score(self, data: Dict) -> tuple:
        """计算适应能力分数
        
        基于员工自己的薪酬数据（salary_records），剔除12月、首月、2月数据，使用方差计算
        """
        employee_name = data.get("name", "")
        
        # 从salary_records获取员工自己的月度绩效数据
        salary_records = data.get("salary_records", [])
        
        if len(salary_records) >= 2:  # 至少需要2个月数据
            # 按月份排序
            sorted_records = sorted(salary_records, key=lambda x: x.get('month', ''))
            
            # 排除首月、12月、2月份数据
            filtered_records = sorted_records[1:]  # 排除首月
            filtered_records = [r for r in filtered_records if not str(r.get('month', '')).endswith('12')]  # 排除12月
            filtered_records = [r for r in filtered_records if not str(r.get('month', '')).endswith('02')]  # 排除2月
            
            # 如果数据不足
            if len(filtered_records) < 2:
                return 70, "考核周期较短（排除首月、12月、2月后数据不足），建议再次观察，暂按基准分70分计算"
            
            # 获取月度绩效值
            monthly_perf_values = []
            for record in filtered_records:
                mp = record.get("monthly_performance", 0) or 0
                if mp > 0:
                    monthly_perf_values.append(mp)
            
            if len(monthly_perf_values) >= 2:
                # 计算方差和标准差
                mean_mp = sum(monthly_perf_values) / len(monthly_perf_values)
                variance = sum((x - mean_mp) ** 2 for x in monthly_perf_values) / len(monthly_perf_values)
                std_dev = variance ** 0.5
                
                # 变异系数（标准差/平均值）
                cv = (std_dev / mean_mp * 100) if mean_mp > 0 else 0
                
                # 使用函数计算分数
                score = 70 - math.pow(cv, 1.5) * 0.5
                score = max(0, min(100, score))
                score = round(score)
                
                # 根据分数给出评价
                if score >= 80:
                    stability = "非常稳定"
                elif score >= 70:
                    stability = "较稳定"
                elif score >= 60:
                    stability = "一般稳定"
                elif score >= 40:
                    stability = "波动较大"
                else:
                    stability = "波动很大"
                
                reason = f"月度绩效{stability}（方差={variance:.0f}, 标准差={std_dev:.0f}, 变异系数={cv:.1f}%, 适应能力={score}分）"
                return score, reason
        
        # 无薪酬数据，使用考勤数据作为备选
        attendance = data.get("attendance", {})
        summary = attendance.get("summary", {})
        late_days = summary.get("late_days", 0)
        overtime_days = summary.get("overtime_days", 0)
        
        if late_days == 0 and overtime_days == 0:
            return 70, "无薪酬数据，根据考勤（无迟到无加班），适应能力70分"
        else:
            return 70, "无薪酬数据，按基准分70分计算"
    
    def _calculate_innovation_score(self, data: Dict) -> tuple:
        """计算创新能力分数"""
        # 从预计算分数中获取
        pre_calculated = data.get("pre_calculated_scores", {})
        if "innovation" in pre_calculated:
            return pre_calculated["innovation"]["score"], pre_calculated["innovation"]["reason"]
        return 60, "基础分60分"
    
    def _calculate_learning_score(self, data: Dict) -> tuple:
        """计算学习能力分数"""
        education = data.get("education", "")
        
        # 学历基础分
        base_score = 60
        if "博士" in education:
            edu_bonus = 20
        elif "硕士" in education:
            edu_bonus = 15
        elif "本科" in education:
            edu_bonus = 10
        else:
            edu_bonus = 5
        
        score = base_score + edu_bonus
        score = min(100, score)
        
        return score, f"基础分{base_score}分，学历加分{edu_bonus}分，学习能力{score}分"
    
    def _calculate_attendance_score(self, data: Dict) -> tuple:
        """计算工时维度分数"""
        attendance = data.get("attendance", {})
        
        # 直接从attendance获取数据（路由代码传递的是扁平结构）
        late_days = attendance.get("late_days", 0)
        overtime_days = attendance.get("overtime_days", 0)
        
        base_score = 50
        
        # 迟到扣分
        if late_days == 0:
            late_deduction = 0
        elif late_days <= 2:
            late_deduction = 5
        elif late_days <= 5:
            late_deduction = 15
        elif late_days <= 10:
            late_deduction = 25
        else:
            late_deduction = 35
        
        # 加班加分
        if overtime_days == 0:
            overtime_bonus = 0
        elif overtime_days <= 5:
            overtime_bonus = 5
        elif overtime_days <= 10:
            overtime_bonus = 15
        else:
            overtime_bonus = 25
        
        score = base_score - late_deduction + overtime_bonus
        score = max(0, min(100, score))
        
        reason = f"基础分{base_score}分，上月迟到{late_days}天扣{late_deduction}分，上月加班{overtime_days}天加{overtime_bonus}分，最终得分{score}分"
        return score, reason
    
    def _calculate_political_score(self, data: Dict) -> tuple:
        """计算政治画像分数"""
        base_score = 50
        
        attendance = data.get("attendance", {})
        # 直接从attendance获取数据（路由代码传递的是扁平结构）
        late_days = attendance.get("late_days", 0)
        
        # 根据迟到扣分
        if late_days == 0:
            deduction = 0
            reason = "基础分50分，上月无迟到无违纪"
        elif late_days <= 2:
            deduction = 10
            reason = f"基础分50分，上月迟到{late_days}次，轻微违纪，扣10分"
        elif late_days <= 5:
            deduction = 25
            reason = f"基础分50分，上月迟到{late_days}次，明显违纪，扣25分"
        elif late_days <= 10:
            deduction = 35
            reason = f"基础分50分，上月迟到{late_days}次，严重违纪，扣35分"
        else:
            deduction = 50
            reason = f"基础分50分，上月迟到{late_days}次，极其严重违纪，扣50分"
        
        score = max(0, base_score - deduction)
        
        # 党员加10分
        political_status = data.get("political_status", "")
        if political_status and "党员" in political_status:
            score = min(100, score + 10)
            reason += "，党员额外加10分"
        
        return score, reason
    
    async def calculate_scores(self, employee_data: Dict, pre_calculated_scores: Dict = None) -> Dict:
        """计算所有维度分数"""
        # 添加预计算分数到数据中
        if pre_calculated_scores:
            employee_data["pre_calculated_scores"] = pre_calculated_scores
        
        scores = {}
        raw_reasons = {}
        
        # 计算各维度分数
        scores["professional"], raw_reasons["professional"] = self._calculate_professional_score(employee_data)
        scores["adaptability"], raw_reasons["adaptability"] = self._calculate_adaptability_score(employee_data)
        scores["innovation"], raw_reasons["innovation"] = self._calculate_innovation_score(employee_data)
        scores["learning"], raw_reasons["learning"] = self._calculate_learning_score(employee_data)
        scores["attendance"], raw_reasons["attendance"] = self._calculate_attendance_score(employee_data)
        scores["political"], raw_reasons["political"] = self._calculate_political_score(employee_data)
        
        return {
            "scores": scores,
            "reasons": raw_reasons
        }


# 全局AI评分器实例
ai_scorer_v2 = AIScorerV2()
