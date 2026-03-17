"""Q-A问答对知识库 - 国脉文化人力数字员工.

包含基础信息查询、薪酬与成本、考勤与合规、团队分析、入职管理、转正管理、调岗管理等问答对。
"""

from typing import Dict, List, Optional
import re


class QAKnowledgeBase:
    """Q-A知识库管理类."""
    
    def __init__(self):
        self.qa_pairs = self._load_qa_pairs()
        
    def _load_qa_pairs(self) -> List[Dict]:
        """加载所有Q-A问答对."""
        return [
            # ========== 基础信息查询 ==========
            {
                "category": "基础信息查询",
                "level": "1级",
                "question_patterns": [
                    r"(.+?)的劳动合同何时到期",
                    r"(.+?)合同什么时候到期",
                    r"(.+?)合同到期时间",
                ],
                "answer_template": "{name}的劳动合同有效期为【YYYY-MM-DD】至【YYYY-MM-DD】，将于【YYYY-MM-DD】到期，当前状态为【在职 / 待续签 / 已终止】。",
                "required_data": ["contract_start_date", "contract_end_date", "contract_status"]
            },
            {
                "category": "基础信息查询",
                "level": "1级",
                "question_patterns": [
                    r"(.+?)\s*(\d{4})\s*年全年薪资标准",
                    r"(.+?)\s*(\d{4})\s*年薪资",
                    r"(.+?)年薪多少",
                ],
                "answer_template": "{name} {year}年全年薪资标准为：固定年薪【X】元（月固定工资【Y】元），绩效年薪【Z】元（根据年度考核结果浮动），合计年薪范围为【A】元至【B】元。",
                "required_data": ["annual_salary", "monthly_salary", "performance_salary"]
            },
            {
                "category": "基础信息查询",
                "level": "2级",
                "question_patterns": [
                    r"(.+?)\s*(\d{4})\s*年\s*(\d{1,2})\s*月绩效",
                    r"(.+?)\s*(\d{4})\s*年\s*(\d{1,2})\s*月绩效酬金",
                ],
                "answer_template": "{name} {year}年{month}月绩效酬金：基础绩效为【X】元，因【具体考核项，如项目交付 / 考勤 / 团队贡献】获得浮动绩效【Y】元，整体较上月【上升 / 下降 / 持平】，浮动比例为【Z】%。",
                "required_data": ["base_performance", "float_performance", "performance_reason"]
            },
            {
                "category": "基础信息查询",
                "level": "2级",
                "question_patterns": [
                    r"(.+?)是否适配当前岗位",
                    r"(.+?)人岗适配",
                    r"(.+?)适配度",
                    r"(.+?)适合当前岗位吗",
                ],
                "answer_template": "{name}在【岗位名称】的适配度评估为：\n・核心能力匹配度：【X】%（如技术栈 / 项目经验 / 沟通能力）\n・绩效表现：【优秀 / 良好 / 待提升】，近3个月KPI完成率为【Y】%\n・综合结论：【高度适配 / 基本适配 / 需针对性提升 / 不适配】",
                "required_data": ["position", "capability_match", "performance_level", "kpi_completion"]
            },
            
            # ========== 薪酬与成本 ==========
            {
                "category": "薪酬与成本",
                "level": "1级",
                "question_patterns": [
                    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(.+?)人工成本",
                    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(.+?)成本",
                ],
                "answer_template": "{year}年{month}月{dept}人工成本合计为【X】元，其中：\n・税前应发工资：【Y】元（含基础工资、绩效、津贴等）\n・公司承担社保公积金：【Z】元\n・其他人力成本（如福利、培训）：【W】元",
                "required_data": ["total_cost", "salary_cost", "social_security", "other_cost"]
            },
            {
                "category": "薪酬与成本",
                "level": "2级",
                "question_patterns": [
                    r"(.+?)\s*(\d{4})\s*年\s*(\d{1,2})\s*月.*占.*部门.*比例",
                    r"(.+?)\s*(\d{4})\s*年\s*(\d{1,2})\s*月.*部门成本.*占比",
                ],
                "answer_template": "{name} {year}年{month}月税前应发工资为【X】元，占{dept}当月人工成本【Y】元的【Z】%。",
                "required_data": ["personal_salary", "dept_total_cost", "percentage"]
            },
            
            # ========== 考勤与合规 ==========
            {
                "category": "考勤与合规",
                "level": "1级",
                "question_patterns": [
                    r"统计\s*(.+?)\s*(\d{4})\s*年\s*(\d{1,2})\s*月.*考勤",
                    r"(.+?)\s*(\d{4})\s*年\s*(\d{1,2})\s*月考勤情况",
                    r"(.+?)\s*(\d{4})\s*年\s*(\d{1,2})\s*月.*迟到",
                ],
                "answer_template": "{dept} {year}年{month}月考勤统计：\n・应出勤人数：【X】人，实际出勤人数：【Y】人\n・迟到：【A】人次（员工A/B/C），早退：【B】人次，旷工：【C】人次\n・违反考勤规则情况：共【D】人违反，主要为【迟到次数超标 / 无故旷工】，具体名单及次数见附件。",
                "required_data": ["should_attendance", "actual_attendance", "late_count", "early_leave", "absenteeism"]
            },
            {
                "category": "考勤与合规",
                "level": "2级",
                "question_patterns": [
                    r"迟到.*处理",
                    r"迟到.*规定",
                    r"迟到.*怎么办",
                ],
                "answer_template": "根据《员工考勤管理办法》第【X】条，处理规则如下：\n・月度迟到≤3次：口头提醒\n・月度迟到4-6次：书面警告，扣发当月绩效【X】%\n・月度迟到≥7次或连续3次迟到：记过处分，扣发当月绩效【Y】%，并纳入年度考核\n・针对本次迟到员工【姓名】，建议采取【提醒 / 警告 / 记过】处理，并同步进行考勤合规培训。",
                "required_data": []
            },
            {
                "category": "考勤与合规",
                "level": "3级",
                "question_patterns": [
                    r"连续.*迟到.*岗位调整",
                    r"连续.*迟到.*解除合同",
                    r"连续.*迟到.*处理",
                ],
                "answer_template": "根据《员工手册》第【X】条，员工连续3个月月度迟到≥5次，将被认定为"严重违反考勤制度"，可触发岗位调整或解除劳动合同的前置条件，具体需由HR与部门负责人共同评估后执行。",
                "required_data": []
            },
            
            # ========== 团队分析 ==========
            {
                "category": "团队分析",
                "level": "1级",
                "question_patterns": [
                    r"(.+?)平均年龄",
                    r"(.+?)学历",
                    r"(.+?)年龄结构",
                    r"分析\s*(.+?)\s*.*年龄",
                ],
                "answer_template": "技术研发团队画像分析（{dept}）：\n・平均年龄：【X】岁，年龄分布：25-30岁占【Y】%，31-35岁占【Z】%\n・学历层级：本科及以上占【A】%，其中硕士及以上占【B】%。",
                "required_data": ["avg_age", "age_distribution", "education_distribution"]
            },
            {
                "category": "团队分析",
                "level": "2级",
                "question_patterns": [
                    r"(.+?)优劣势",
                    r"(.+?)优势",
                    r"(.+?)劣势",
                ],
                "answer_template": "对比行业平均水平：\n・优势：30岁以下年轻工程师占比【X】%，高于行业平均【Y】%，创新活力较强；硕士及以上学历占比【Z】%，高于行业平均【W】%。\n・劣势：35岁以上资深工程师占比不足，在复杂系统架构设计方面存在经验短板。",
                "required_data": []
            },
            
            # ========== 入职管理 ==========
            {
                "category": "入职管理",
                "level": "1级",
                "question_patterns": [
                    r"(.+?)入职流程",
                    r"(.+?)入职节点",
                    r"新员工\s*(.+?)\s*入职",
                ],
                "answer_template": "新员工{name}的入职流程如下：\n1. 【YYYY-MM-DD】：Offer确认与背景调查\n2. 【YYYY-MM-DD】：入职资料提交（身份证、学历证等）\n3. 【YYYY-MM-DD】：劳动合同签署\n4. 【YYYY-MM-DD】：工位、账号、设备配置\n5. 【YYYY-MM-DD】：部门入职引导与培训",
                "required_data": ["offer_date", "document_date", "contract_date", "setup_date", "training_date"]
            },
            {
                "category": "入职管理",
                "level": "2级",
                "question_patterns": [
                    r"(.+?)入职.*考核",
                    r"(.+?)入职.*指标",
                    r"(.+?)30天.*考核",
                ],
                "answer_template": "{name}入职后30天内的关键考核指标：\n・熟悉公司组织架构与业务流程（完成度100%）\n・掌握岗位核心工具与规范（通过考核）\n・完成1个入门级任务交付（质量达标）",
                "required_data": []
            },
            {
                "category": "入职管理",
                "level": "3级",
                "question_patterns": [
                    r"(.+?)试用期.*未达标",
                    r"(.+?)试用期.*处理",
                    r"试用期.*考核.*处理",
                ],
                "answer_template": "根据《试用期管理办法》，若{name}试用期考核未达标，将由部门负责人与HR共同评估：\n・可延长试用期1个月（最多一次），并制定针对性提升计划\n・若延长后仍不达标，将依法解除劳动合同",
                "required_data": []
            },
            
            # ========== 转正管理 ==========
            {
                "category": "转正管理",
                "level": "1级",
                "question_patterns": [
                    r"(.+?)转正.*状态",
                    r"(.+?)转正.*审批",
                    r"(.+?)转正申请",
                ],
                "answer_template": "{name}的转正申请于【YYYY-MM-DD】提交，当前审批状态为【部门负责人审批中 / HR审核中 / 已通过 / 已驳回】，预计【YYYY-MM-DD】完成全部流程。",
                "required_data": ["submit_date", "approval_status", "expected_date"]
            },
            {
                "category": "转正管理",
                "level": "2级",
                "question_patterns": [
                    r"(.+?)转正.*薪资",
                    r"(.+?)转正.*调整",
                    r"(.+?)转正.*等级",
                ],
                "answer_template": "{name}转正后：\n・岗位等级：由【试用期等级】调整为【正式岗等级】\n・薪资：固定工资由【X】元调整为【Y】元，绩效基数同步调整为【Z】元",
                "required_data": ["trial_level", "formal_level", "trial_salary", "formal_salary", "performance_base"]
            },
            {
                "category": "转正管理",
                "level": "3级",
                "question_patterns": [
                    r"转正.*驳回",
                    r"转正.*未通过",
                    r"转正.*后续",
                ],
                "answer_template": "转正申请被驳回后，流程如下：\n1. HR向员工及部门负责人出具驳回原因说明\n2. 部门制定1-2个月的提升计划\n3. 员工完成提升后可再次提交转正申请",
                "required_data": []
            },
            
            # ========== 调岗管理 ==========
            {
                "category": "调岗管理",
                "level": "1级",
                "question_patterns": [
                    r"(.+?)调岗.*职责",
                    r"(.+?)调岗.*汇报",
                    r"(.+?)调岗.*新岗位",
                ],
                "answer_template": "{name}调岗至【新岗位名称】，核心职责：\n・负责【核心业务模块】的技术方案设计与落地\n・向【新上级姓名】汇报\n・与【协作部门】对接需求",
                "required_data": ["new_position", "responsibilities", "report_to", "collaborate_dept"]
            },
            {
                "category": "调岗管理",
                "level": "2级",
                "question_patterns": [
                    r"(.+?)调岗.*薪资",
                    r"(.+?)调岗.*绩效",
                    r"(.+?)调岗.*福利",
                ],
                "answer_template": "{name}调岗后：\n・薪资：固定工资【保持不变 / 调整为X元】\n・绩效：考核指标由【原指标】调整为【新指标】，绩效基数【保持不变 / 调整为Y元】\n・福利：五险一金基数【保持不变 / 调整为Z元】",
                "required_data": ["salary_change", "performance_change", "benefit_change"]
            },
            {
                "category": "调岗管理",
                "level": "3级",
                "question_patterns": [
                    r"调岗.*不适应",
                    r"调岗.*回原岗",
                    r"调岗.*调整",
                ],
                "answer_template": "调岗后6个月内，若{name}经评估确实不适应新岗位，可由部门负责人与HR共同评估，优先在部门内协调其他岗位，若无可匹配岗位，可申请调回原岗，但需满足原岗编制及能力要求。",
                "required_data": []
            },
        ]
    
    def find_matching_qa(self, query: str) -> Optional[Dict]:
        """根据查询找到匹配的Q-A对.
        
        Args:
            query: 用户查询
            
        Returns:
            匹配的Q-A对，如果没有找到则返回None
        """
        for qa in self.qa_pairs:
            for pattern in qa["question_patterns"]:
                if re.search(pattern, query):
                    return qa
        return None
    
    def extract_entities(self, query: str, qa: Dict) -> Dict:
        """从查询中提取实体（员工姓名、日期等）.
        
        Args:
            query: 用户查询
            qa: Q-A对
            
        Returns:
            提取的实体字典
        """
        entities = {}
        
        # 提取员工姓名
        for pattern in qa["question_patterns"]:
            match = re.search(pattern, query)
            if match:
                # 第一个捕获组通常是员工姓名
                if match.groups():
                    entities["name"] = match.group(1)
                break
        
        # 提取年份
        year_match = re.search(r'(\d{4})\s*年', query)
        if year_match:
            entities["year"] = year_match.group(1)
        
        # 提取月份
        month_match = re.search(r'(\d{1,2})\s*月', query)
        if month_match:
            entities["month"] = month_match.group(1)
        
        # 提取部门
        dept_match = re.search(r'(云生工作室|权益部|科技研发部|运营管理部)', query)
        if dept_match:
            entities["dept"] = dept_match.group(1)
        
        return entities


# 单例实例
_qa_knowledge_base: Optional[QAKnowledgeBase] = None


def get_qa_knowledge_base() -> QAKnowledgeBase:
    """获取Q-A知识库单例."""
    global _qa_knowledge_base
    if _qa_knowledge_base is None:
        _qa_knowledge_base = QAKnowledgeBase()
    return _qa_knowledge_base
