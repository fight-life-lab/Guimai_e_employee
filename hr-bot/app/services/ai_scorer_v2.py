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
        """计算学习能力分数
        
        规则：
        一、基础学习能力（占比80%）
        1. 基础分阶段，按照全日制最高学位：
           - 学士阶段：普通院校60分，211/QS50-100得70分，985/QS前50得80分
           - 硕士阶段：普通院校70分，211/QS50-100得80分，985/QS前50得90分
           - 博士阶段：普通院校80分，211/QS50-100得90分，985/QS前50得100分
        
        2. 扣分项：
           - 专科学历：扣5分
           - 专科以下学历：扣10分
        
        3. 加分项（持续学习能力-学位提升，在职教育）：
           - 学士阶段：普通专升本+2，211/QS50-100专升本+3，985/QS前50专升本+4
           - 硕士阶段：普通硕士+3，211/QS50-100硕士+5，985/QS前50硕士+7
           - 博士阶段：普通博士+4，211/QS50-100博士+6，985/QS前50博士+8
        
        二、持续学习能力（综合评价，占比20%）- 由AI评价
        """
        # 获取数据
        education = data.get("education", "")  # 最高学历
        school_type = data.get("school_type", "")  # 学校类型（国内-985/国内-211/国内-普通/海外-QS前50/海外-QS50-100/海外-其他）
        fulltime_degree = data.get("fulltime_degree", "")  # 全日制最高学位
        degree_upgrade = data.get("degree_upgrade", False)  # 是否有学位提升
        upgrade_school_type = data.get("upgrade_school_type", "")  # 提升学位的学校类型
        
        # 判断学校档次
        def get_school_level(s_type):
            """获取学校档次：普通/211/985"""
            if not s_type:
                return "普通"
            if "985" in s_type or "QS前50" in s_type:
                return "985"
            elif "211" in s_type or "QS50-100" in s_type:
                return "211"
            else:
                return "普通"
        
        # 判断学位阶段
        def get_degree_stage(degree):
            """获取学位阶段：学士/硕士/博士/专科"""
            if not degree:
                return "学士"  # 默认学士
            if "博士" in degree:
                return "博士"
            elif "硕士" in degree:
                return "硕士"
            elif "专科" in degree or "大专" in degree:
                return "专科"
            else:
                return "学士"
        
        # 基础分表（按学位阶段和学校档次）
        base_score_table = {
            "学士": {"普通": 60, "211": 70, "985": 80},
            "硕士": {"普通": 70, "211": 80, "985": 90},
            "博士": {"普通": 80, "211": 90, "985": 100},
            "专科": {"普通": 55, "211": 55, "985": 55}  # 专科基础分统一55，后面再扣
        }
        
        # 加分表（学位提升）
        upgrade_bonus_table = {
            "学士": {"普通": 2, "211": 3, "985": 4},
            "硕士": {"普通": 3, "211": 5, "985": 7},
            "博士": {"普通": 4, "211": 6, "985": 8}
        }
        
        # 计算基础分
        degree_stage = get_degree_stage(fulltime_degree or education)
        school_level = get_school_level(school_type)
        
        # 基础学习能力分（占80%）
        base_learning_score = base_score_table.get(degree_stage, base_score_table["学士"]).get(school_level, 60)
        
        # 扣分项
        deduction = 0
        if degree_stage == "专科":
            deduction = 5
        # 注意：专科以下（高中及以下）扣10分，但数据库中可能没有这类数据
        
        # 学位提升加分
        upgrade_bonus = 0
        if degree_upgrade:
            upgrade_degree_stage = get_degree_stage(education)  # 提升后的学位
            upgrade_school_level = get_school_level(upgrade_school_type) if upgrade_school_type else school_level
            upgrade_bonus = upgrade_bonus_table.get(upgrade_degree_stage, {}).get(upgrade_school_level, 0)
        
        # 基础学习能力最终分
        base_learning_final = base_learning_score - deduction + upgrade_bonus
        base_learning_final = max(0, min(100, base_learning_final))
        
        # 构建说明
        reason_parts = []
        reason_parts.append(f"基础学习能力（80%权重）：{fulltime_degree or education}阶段，{school_type or '普通院校'}，基础分{base_learning_score}分")
        
        if deduction > 0:
            reason_parts.append(f"专科学历扣{deduction}分")
        
        if upgrade_bonus > 0:
            reason_parts.append(f"学位提升（{education}）加{upgrade_bonus}分")
        
        reason_parts.append(f"基础学习能力得分：{base_learning_final}分")
        
        # 持续学习能力（20%权重）- 由AI在后续评价
        # 这里先返回基础分，AI会在生成理由时补充持续学习能力的评价
        
        return base_learning_final, "；".join(reason_parts)
    
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
        """计算品质态度分数（工作态度）
        
        规则（用户提供）：
        基础分为70分，上限100分
        
        1. 扣分项（自然年）
           迟到/早退：迟到豁免3次/月，在豁免的基础上每多一次每次扣1分，最多扣10分。
           旷工：每旷工1次，扣10分。年度旷工超过3次以上，本大项目直接0分
        
        2. 加分项（累计得分，二选一取高分）
           工作日：按照17点30分为下班时间，最晚打卡时间为18点30分及以后的，加1分，
                   20点30分及以后的，加3分，最多加20分。
           月度加班时间达到36小时及以上的，加20分。
           以上条件二选一。
        
        3. 政治面貌：中共党员加5分
        4. 党工团兼职：党10、团7、工4，最高10分
        """
        base_score = 70
        max_score = 100
        reasons = []
        
        # ============ 1. 迟到/早退扣分 ============
        # 获取近12个月的月度考勤汇总
        monthly_summary = data.get("attendance", {}).get("monthly_summary", [])
        
        # 计算年度迟到总次数
        total_late_count = sum(m.get("late_count", 0) or 0 for m in monthly_summary)
        
        # 计算超出豁免的次数（每月豁免3次）
        months_with_late = len(monthly_summary)
        total_exemption = months_with_late * 3  # 总豁免次数
        excess_late = max(0, total_late_count - total_exemption)
        late_deduction = min(excess_late, 10)  # 最多扣10分
        
        if late_deduction > 0:
            reasons.append(f"迟到{total_late_count}次（年度豁免{total_exemption}次），超出{excess_late}次，扣{late_deduction}分")
        else:
            reasons.append(f"迟到{total_late_count}次，在年度豁免范围内（{total_exemption}次），不扣分")
        
        # ============ 2. 旷工扣分 ============
        total_absent_count = sum(m.get("absent_count", 0) or m.get("absent_days", 0) for m in monthly_summary)
        
        if total_absent_count > 3:
            # 年度旷工超过3次，本大项目直接0分
            return 0, f"基础分{base_score}分，年度旷工{total_absent_count}次，超过3次上限，本大项目直接0分"
        elif total_absent_count > 0:
            absent_deduction = total_absent_count * 10
            reasons.append(f"旷工{total_absent_count}次，扣{absent_deduction}分")
        else:
            absent_deduction = 0
            reasons.append("无旷工记录")
        
        # ============ 3. 加班加分（二选一，取高分） ============
        overtime_bonus = 0
        
        # 方式A：基于打卡时间的加班加分
        # overtime_1830_count: 18:30及以后打卡次数（每次1分）
        # overtime_2030_count: 20:30及以后打卡次数（每次3分）
        overtime_1830_count = 0
        overtime_2030_count = 0
        
        for m in monthly_summary:
            overtime_1830_count += m.get("overtime_1830_count", 0) or 0
            overtime_2030_count += m.get("overtime_2030_count", 0) or 0
        
        bonus_1830 = overtime_1830_count * 1  # 18:30后每次1分
        bonus_2030 = overtime_2030_count * 3  # 20:30后每次3分
        bonus_by_time = min(bonus_1830 + bonus_2030, 20)  # 最多加20分
        
        # 方式B：基于月度加班时长的加分
        bonus_by_hours = 0
        for m in monthly_summary:
            if m.get("overtime_hours", 0) >= 36:
                bonus_by_hours = 20  # 有一个月达到36小时就加20分
                break
        
        # 二选一，取高分
        overtime_bonus = max(bonus_by_time, bonus_by_hours)
        
        if bonus_by_time > 0:
            reasons.append(
                f"加班加分（按打卡时间）：18:30后{overtime_1830_count}次（每次1分，共{bonus_1830}分），"
                f"20:30后{overtime_2030_count}次（每次3分，共{bonus_2030}分），"
                f"合计{bonus_1830 + bonus_2030}分（ capped 20分）"
            )
        
        if bonus_by_hours > 0:
            # 找到加班时长>=36小时的月份
            months_with_36h = [m.get("month", "") for m in monthly_summary if m.get("overtime_hours", 0) >= 36]
            reasons.append(
                f"加班加分（按时长）：{', '.join(months_with_36h)}月度加班时长>=36小时，加20分"
            )
        
        if overtime_bonus > 0:
            method = "打卡时间" if bonus_by_time >= bonus_by_hours else "加班时长"
            reasons.append(f"加班加分二选一取高分（{method}方式）：{overtime_bonus}分")
        
        # ============ 4. 政治面貌加分 ============
        political_status = data.get("political_status", "")
        party_bonus = 5 if political_status and "党员" in political_status else 0
        if party_bonus > 0:
            reasons.append(f"中共党员，加{party_bonus}分")
        
        # ============ 5. 党工团兼职加分 ============
        party_position = data.get("party_position", "") or ""
        position_bonus = 0
        if "党" in party_position:
            position_bonus = max(position_bonus, 10)
        elif "团" in party_position:
            position_bonus = max(position_bonus, 7)
        elif "工" in party_position:
            position_bonus = max(position_bonus, 4)
        position_bonus = min(position_bonus, 10)  # 最高10分
        
        if position_bonus > 0:
            reasons.append(f"党工团兼职（{party_position}），加{position_bonus}分")
        
        # ============ 计算总分 ============
        total_score = base_score - late_deduction - absent_deduction + overtime_bonus + party_bonus + position_bonus
        total_score = min(total_score, max_score)  # 不超过上限
        total_score = max(total_score, 0)  # 不低于0分
        
        reason_text = (
            f"基础分{base_score}分；"
            + "；".join(reasons)
            + f"；最终得分{total_score}分（上限{max_score}分）"
        )
        
        return total_score, reason_text
    
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
