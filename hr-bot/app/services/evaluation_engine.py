"""
评估引擎模块 - 定义统一的评估接口和员工/干部评估实现

核心设计：
1. EvaluationEngine 基类：定义通用评估接口
2. EmployeeEvaluationEngine：员工招聘评估实现（注重执行力）
3. CadreEvaluationEngine：干部选拔评估实现（注重管理能力和战略思维）

两者区别：
- 评分维度权重不同
- 评估prompt不同（关注重点不同）
- 薪酬预算范围不同
- 内部候选人处理不同（干部有加分机制）
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

from app.models.interview_models import (
    EvaluationConfig,
    EMPLOYEE_CONFIG,
    CADRE_CONFIG,
    get_evaluation_config,
    EvaluationResult,
    DimensionScore
)
from .interview_services import call_qwen_api, parse_json_from_response

logger = logging.getLogger(__name__)


class EvaluationEngine(ABC):
    """
    评估引擎基类 - 定义通用评估接口
    
    子类需要实现：
    1. _build_prompt() - 构建评估提示词
    2. _post_process() - 后处理评估结果
    """
    
    def __init__(self, evaluation_type: str):
        """
        初始化评估引擎
        
        Args:
            evaluation_type: 评估类型（employee/cadre）
        """
        self.evaluation_type = evaluation_type
        self.config = get_evaluation_config(evaluation_type)
    
    @abstractmethod
    def _build_prompt(
        self,
        jd_content: str,
        resume_content: str,
        transcript: str,
        questions: List[Dict] = None
    ) -> str:
        """
        构建评估提示词
        
        Args:
            jd_content: 岗位JD内容
            resume_content: 简历内容
            transcript: 面试录音转录文本
            questions: 结构化面试问题列表（可选）
        
        Returns:
            完整的提示词字符串
        """
        pass
    
    @abstractmethod
    def _post_process(self, evaluation: dict) -> dict:
        """
        后处理评估结果
        
        Args:
            evaluation: 原始评估结果
        
        Returns:
            处理后的评估结果
        """
        return evaluation
    
    async def evaluate(
        self,
        jd_content: str,
        resume_content: str,
        transcript: str,
        questions: List[Dict] = None
    ) -> Optional[EvaluationResult]:
        """
        执行评估
        
        Args:
            jd_content: 岗位JD内容
            resume_content: 简历内容
            transcript: 面试录音转录文本
            questions: 结构化面试问题列表（可选）
        
        Returns:
            EvaluationResult 对象或 None
        """
        try:
            # 构建提示词
            prompt = self._build_prompt(jd_content, resume_content, transcript, questions)
            
            # 调用LLM
            response = await call_qwen_api(prompt, temperature=0.3, max_tokens=3000)
            if not response:
                logger.error("[评估引擎] LLM调用失败")
                return None
            
            # 解析JSON
            evaluation = await parse_json_from_response(response)
            if not evaluation:
                logger.error("[评估引擎] JSON解析失败")
                return None
            
            # 后处理
            evaluation = self._post_process(evaluation)
            
            # 转换为EvaluationResult对象
            return self._convert_to_result(evaluation)
            
        except Exception as e:
            logger.error(f"[评估引擎] 评估失败: {e}")
            return None
    
    def _convert_to_result(self, evaluation: dict) -> EvaluationResult:
        """
        将字典转换为EvaluationResult对象
        
        Args:
            evaluation: 评估结果字典
        
        Returns:
            EvaluationResult 对象
        """
        # 处理维度评分
        dimensions = []
        for dim in evaluation.get("dimensions", []):
            dimensions.append(DimensionScore(
                name=dim.get("name", ""),
                score=dim.get("score", 0),
                weight=dim.get("weight", 0),
                analysis=dim.get("analysis", "")
            ))
        
        return EvaluationResult(
            overall_score=evaluation.get("overall_score", 0),
            evaluation_level=evaluation.get("evaluation_level", ""),
            dimensions=dimensions,
            summary=evaluation.get("summary", ""),
            strengths=evaluation.get("strengths", []),
            weaknesses=evaluation.get("weaknesses", []),
            recommendations=evaluation.get("recommendations", []),
            question_answers=evaluation.get("question_answers", []),
            timestamp=evaluation.get("timestamp")
        )


class EmployeeEvaluationEngine(EvaluationEngine):
    """
    员工招聘评估引擎 - 注重执行力和团队协作能力
    """
    
    def __init__(self):
        super().__init__("employee")
    
    def _build_prompt(
        self,
        jd_content: str,
        resume_content: str,
        transcript: str,
        questions: List[Dict] = None
    ) -> str:
        """
        构建员工评估提示词
        """
        # 如果没有JD内容，使用默认JD
        if not jd_content.strip():
            jd_content = """岗位职责：
1. 负责日常业务流程执行和优化
2. 完成上级交办的各项任务
3. 与团队成员协作完成项目目标
4. 及时汇报工作进展和问题

岗位要求：
1. 本科及以上学历
2. 1-3年相关工作经验
3. 具备良好的沟通能力和团队协作精神
4. 执行力强，能按时完成工作任务
5. 具备良好的学习能力和适应能力"""
        
        prompt = f"""你是一位在大型企业工作多年的资深HR面试官，专门负责员工招聘面试。你熟悉现代企业的用人标准、组织文化和员工管理要求，擅长从专业能力、工作经验、团队协作等多维度对候选人进行严格、客观、有区分度的面试评价。

## 你的角色定位
- **企业HR面试官**：熟悉企业员工招聘标准，注重候选人的专业能力、工作经验、团队协作
- **专业眼光**：能够从岗位需求角度评估候选人的能力和潜力
- **严谨客观**：坚持实事求是，确保评分公正公平
- **经验丰富**：参与过大量员工招聘面试，对人才评价有独到见解

## 核心评价原则

### **评分差异化要求（极其重要）**
**你必须确保评分有显著区分度，这是最重要的要求**：
- **绝对禁止所有候选人分数集中在75-85分区间**，这种评分是无效的
- 优秀候选人（表现突出、经验丰富、沟通优秀）必须给 **85-95分**
- 良好候选人（表现较好、符合要求）应该给 **75-84分**
- 一般候选人（基本合格但有不足）应该给 **60-74分**
- 较差候选人（明显不足、经验欠缺）必须给 **40-59分**
- **同一批候选人中，最高分与最低分的差距必须至少达到25分以上**
- **示例：不要给所有候选人80-83分，而应该给优秀者90分、良好者78分、一般者65分、较差者50分**

### **评分理由详细性要求（极其重要）**
**每个维度的analysis必须详细说明为什么给这个分数**：
- 必须引用面试中的**具体事例或回答内容**作为评分依据
- 必须说明候选人的**具体表现**（做了什么、说了什么）
- 必须解释**为什么值得这个分数**（符合哪些标准、达到什么水平）
- 必须指出**与岗位要求的匹配程度**
- **analysis长度至少100字**，不能只有简单的一句话评价
- 示例："候选人在回答薪酬体系设计问题时，详细描述了在太平金科期间主导MD职级体系重构的经历（具体事例），展示了系统的专业知识和项目管理能力（能力体现），方案设计逻辑完整且考虑了多维度因素（水平说明），符合高级薪酬经理的专业要求（匹配度），因此给予88分的高分（分数理由）。"

### **评分与评语一致性要求**
- 如果analysis详细描述了优秀表现并引用具体事例，分数必须在80分以上
- 如果analysis指出明显不足或经验欠缺，分数必须在70分以下
- **analysis的评价描述与最终分数必须完全一致**

**重要：该岗位侧重执行力评估**：
- 执行力是员工岗位的核心要求，在评判所有维度时，必须重点考察候选人的执行力表现
- 执行力包括：目标导向、结果意识、行动效率、任务闭环能力、遇到困难时的推进能力
- 请在各维度分析中，明确指出候选人的执行力表现，并据此调整分数
- **执行力强的候选人应在各维度获得明显更高的分数，执行力弱的候选人应在各维度获得明显更低的分数**

## 岗位JD
{jd_content}

## 候选人简历
{resume_content}

## 面试录音转录
{transcript}

## 评分维度与详细标准

### 第一部分：6个核心维度评分（0-100分，必须严格按照以下标准评分）

**评分档次定义：**
- **A档（90-100分）**：卓越表现，远超岗位要求
- **B档（80-89分）**：优秀表现，完全符合岗位要求
- **C档（60-79分）**：合格表现，基本符合岗位要求
- **D档（0-59分）**：不合格表现，不符合岗位要求

**各维度详细评分标准（员工招聘视角，重点考察执行力）：**

1. **专业能力**（权重20%）- 考察岗位胜任力、专业深度及执行落地能力：
   - A档（90-100）：专业功底深厚，不仅能提出方案，更能高效执行落地，有明确的结果产出
   - B档（80-89）：专业知识扎实，能独立执行复杂任务，按时保质完成工作
   - C档（60-79）：具备基本专业知识，能执行常规工作，但执行效率和结果质量一般
   - D档（0-59）：专业知识不足，执行力弱，任务经常无法按时完成或达不到要求
   - **执行力考察重点**：是否善于将计划转化为行动，执行过程中是否主动推进、及时反馈

2. **工作经验**（权重20%）- 考察相关工作经历、项目经验及执行成果：
   - A档（90-100）：有丰富经验，主导过重要项目并拿到结果，执行力强，有量化业绩证明
   - B档（80-89）：有3-5年经验，参与过重要项目，能按质按量完成任务，有可靠执行记录
   - C档（60-79）：有1-3年经验，参与过项目但执行深度有限，成果不够突出
   - D档（0-59）：经验不足或缺乏相关经验，执行力未得到验证
   - **执行力考察重点**：过往工作中是否以结果为导向，能否举例说明如何克服困难完成任务

3. **沟通表达**（权重15%）- 考察沟通能力、团队协作及执行协同效率：
   - A档（90-100）：表达清晰，善于跨部门协作推进工作，能高效协调资源促成任务落地
   - B档（80-89）：沟通顺畅，能进行有效协作，配合团队完成执行目标
   - C档（60-79）：沟通能力一般，协作效率不高，执行中偶有拖延或信息不同步
   - D档（0-59）：沟通困难，协作意识弱，影响团队执行效率
   - **执行力考察重点**：沟通是否以推进工作为目标，是否能及时同步进展、主动协调解决问题

4. **逻辑思维**（权重15%）- 考察分析判断、解决问题及执行策略能力：
   - A档（90-100）：思维缜密，能快速分析问题并制定可执行方案，执行路径清晰
   - B档（80-89）：逻辑清晰，能分析问题并找到解决方案，执行步骤合理
   - C档（60-79）：思维基本清晰，但分析不够深入，执行方案不够完善
   - D档（0-59）：思维混乱，缺乏逻辑性，无法制定有效执行计划
   - **执行力考察重点**：是否能把复杂问题拆解为可执行步骤，面对障碍时能否灵活调整策略继续推进

5. **学习能力**（权重15%）- 考察适应发展、学习潜力及执行中的自我提升：
   - A档（90-100）：学习意识强，能快速掌握新技能并应用到工作中，执行新任务上手快
   - B档（80-89）：学习态度端正，能主动学习，适应新任务和新环境
   - C档（60-79）：学习意愿一般，掌握新技能较慢，执行新任务需要较多指导
   - D档（0-59）：学习意识淡薄，难以适应变化，影响执行效率
   - **执行力考察重点**：是否能在执行过程中不断总结经验、优化方法，快速提升执行效率

6. **综合素质**（权重15%）- 考察职业素养、责任心、抗压能力及执行韧性：
   - A档（90-100）：职业素养高，责任心极强，抗压能力强，面对困难仍能坚持执行到底
   - B档（80-89）：职业素养良好，有责任心，能承担压力，基本完成执行任务
   - C档（60-79）：职业素养一般，责任心和抗压能力一般，执行中容易放弃或拖延
   - D档（0-59）：职业素养不足，缺乏责任心，遇到困难就退缩，执行力差
   - **执行力考察重点**：是否有强烈的结果导向意识，能否在压力下保持高效执行，是否善于自我驱动

### 第二部分：薪酬匹配度（单独维度，不参与综合评分计算）
**薪酬匹配度计算方法**：
1. 从候选人简历和面试中提取薪酬信息
2. 匹配度评分标准：
   - 90-100分：期望薪资在预算范围内，匹配度高
   - 70-89分：期望薪资略低于预算下限，有谈判空间
   - 50-69分：期望薪资略高于预算上限，需谨慎评估
   - 0-49分：期望薪资严重超出预算，不匹配

## 综合评分计算方法
综合评分 = Σ(维度分数 × 维度权重) / 100

请按以下JSON格式输出结果：

```json
{{
    "overall_score": 82,
    "evaluation_level": "良好",
    "dimensions": [
        {{
            "name": "专业能力",
            "score": 85,
            "weight": 20,
            "analysis": "候选人在回答薪酬体系设计问题时，详细描述了在太平金科期间主导MD职级体系重构的经历，从需求分析、方案设计到落地实施全程参与，展示了扎实的专业功底。特别是在处理复杂薪酬结构时，能够考虑到固定薪酬、浮动薪酬、社保公积金等多个维度，体现了系统的专业知识。方案设计逻辑完整，符合大型国企的薪酬管理要求，执行力强，能够推动项目落地。因此给予85分的高分。"
        }},
        {{
            "name": "工作经验",
            "score": 78,
            "weight": 20,
            "analysis": "候选人拥有15年HR从业经历，涵盖工行、平安普惠、太平金科及券商等多元企业类型，积累了丰富的跨行业经验。在工行期间从业务岗位转型到HR岗位，经历了完整的职业发展历程。但在新筹管理岗位上的独立牵头经验主要集中在中小规模企业，对超大规模组织的系统性统筹经验略显不足，且近期岗位变动较频繁，稳定性有待观察。综合评估给予78分。"
        }},
        {{
            "name": "沟通表达",
            "score": 80,
            "weight": 15,
            "analysis": "候选人表达条理清晰，能够围绕问题展开结构化回答，语言流畅，逻辑连贯。在解释复杂薪酬结构、预算机制时能够使用通俗易懂的方式说明，具备良好的信息传递能力。面试中能够主动与面试官互动，回答问题时有明确的重点和层次。但在部分问题的回答上略显冗长，可以进一步提升表达的精准度和简洁性。综合评估给予80分。"
        }},
        {{
            "name": "逻辑思维",
            "score": 82,
            "weight": 15,
            "analysis": "候选人在回答问题时展现出较强的逻辑思维能力，能够将复杂问题拆解为可执行的步骤。在描述薪酬体系优化案例时，从现状分析、问题诊断、方案设计到实施落地的逻辑链条清晰完整。面对国企人工成本管控的挑战，能够提出系统性的解决方案，包括预算编制、过程监控、数据分析等多维度措施。思维缜密，分析深入，给予82分。"
        }},
        {{
            "name": "学习能力",
            "score": 88,
            "weight": 15,
            "analysis": "候选人展现出强烈的学习意识和快速学习能力。主动考取高级薪税师证书，关注政策变化（如个税抵扣），并能快速适应不同行业（银行、保险、证券、电信）的人力资源管理要求。在薪酬体系转型中引入外部咨询、推动MD序列改革，体现出较强的市场敏感度与学习转化能力。能够将学习的新知识快速应用到实际工作中，给予88分的高分。"
        }},
        {{
            "name": "综合素质",
            "score": 80,
            "weight": 15,
            "analysis": "候选人职业素养良好，学历背景优秀（本科毕业于华师大数学系），职业路径清晰，具备从执行到战略层面的过渡能力。对国企机制有一定认知，认同长期稳定发展，价值观与企业文化匹配度较高。虽然当前薪酬期望与岗位预算存在差距，但表现出一定灵活性。在团队协作方面，多次提及与财务、业务部门协同推进项目，体现出跨部门沟通意识。综合评估给予80分。"
        }}
    ],
    "summary": "候选人是一位经验丰富的HR专业人士，在薪酬管理领域有15年从业经历，具备扎实的专业知识和较强的学习能力。在太平金科期间主导MD职级体系重构的经历体现了其项目管理和执行落地能力。沟通表达清晰，逻辑思维较强，能够系统性分析问题。但需要注意其在超大规模组织中的系统性统筹经验相对有限，且近期岗位变动较频繁。整体而言，候选人符合岗位要求，建议录用。",
    "strengths": ["15年丰富HR从业经验，跨行业背景", "主导过MD职级体系重构等重要项目", "学习能力强，主动考取高级薪税师证书", "沟通表达清晰，逻辑思维较强", "对国企机制有认知，价值观匹配度高"],
    "weaknesses": ["超大规模组织统筹经验相对有限", "近期岗位变动较频繁，稳定性需关注", "部分回答略显冗长，表达精准度可提升"],
    "recommendations": ["建议在后续面试中进一步考察其在大型组织中推动变革的实际影响力与抗压能力", "可探讨其对上市公司股权激励机制的理解深度", "关注其薪酬期望与岗位预算的匹配度，评估谈判空间"],
    "question_answers": [
        {{
            "question": "请结合过往经历分享薪酬体系优化案例",
            "answer_summary": "候选人详细描述了在太平金科期间主导MD职级体系重构的经历，包括需求分析、方案设计、落地实施等全流程",
            "score": 85,
            "evaluation": "回答内容充实，案例具体，体现了较强的专业能力和项目管理经验"
        }}
    ]
}}
```

## 重要注意事项（违反以下任何一条都会导致评分无效）
1. **评分差异化**：绝对禁止所有候选人分数集中在75-85分，必须根据实际表现给予40-95分的差异化评分
2. **评分理由详细性**：每个维度的analysis必须至少100字，必须引用具体事例，必须解释为什么给这个分数
3. **评分与评语一致**：analysis描述优秀则分数必须在80分以上，指出不足则分数必须在70分以下
4. **overall_score计算**：必须是各维度分数按权重加权计算的真实结果，范围0-100
5. **权重严格执行**：专业能力20%、工作经验20%、沟通表达15%、逻辑思维15%、学习能力15%、综合素质15%
6. **只输出JSON**：不要有任何其他文字说明，确保JSON格式完全正确"""
        
        return prompt
    
    def _post_process(self, evaluation: dict) -> dict:
        """
        后处理评估结果 - 员工评估特有处理
        
        主要检查：
        1. 确保维度权重正确
        2. 确保综合评分计算正确
        3. 添加timestamp
        """
        import time
        
        # 确保维度权重符合配置
        weight_map = {dim["name"]: dim["weight"] for dim in self.config.dimensions}
        for dim in evaluation.get("dimensions", []):
            dim["weight"] = weight_map.get(dim.get("name"), 16)
        
        # 重新计算综合评分（确保正确性）
        total_weighted_score = 0
        total_weight = 0
        for dim in evaluation.get("dimensions", []):
            weight = dim.get("weight", 0)
            score = dim.get("score", 0)
            total_weighted_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            evaluation["overall_score"] = round(total_weighted_score / total_weight)
        
        # 更新评价等级
        overall_score = evaluation.get("overall_score", 0)
        if overall_score >= 90:
            evaluation["evaluation_level"] = "优秀"
        elif overall_score >= 80:
            evaluation["evaluation_level"] = "良好"
        elif overall_score >= 60:
            evaluation["evaluation_level"] = "一般"
        else:
            evaluation["evaluation_level"] = "较差"
        
        # 添加时间戳
        evaluation["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        return evaluation


class CadreEvaluationEngine(EvaluationEngine):
    """
    干部选拔评估引擎 - 注重管理能力和战略思维
    """
    
    def __init__(self):
        super().__init__("cadre")
    
    def _build_prompt(
        self,
        jd_content: str,
        resume_content: str,
        transcript: str,
        questions: List[Dict] = None
    ) -> str:
        """
        构建干部评估提示词
        """
        # 如果没有JD内容，使用默认JD
        if not jd_content.strip():
            jd_content = """岗位职责：
1. 负责部门整体战略规划和目标制定
2. 领导团队完成各项业务指标
3. 负责部门预算管理和资源分配
4. 与上级领导和其他部门沟通协调
5. 推动组织变革和流程优化

岗位要求：
1. 本科及以上学历，MBA优先
2. 8年以上工作经验，5年以上管理经验
3. 具备优秀的领导能力和团队管理经验
4. 具备战略思维和决策能力
5. 良好的沟通协调能力和政治素质"""
        
        # 构建面试问题列表
        questions_text = ""
        if questions:
            questions_text = "\n".join([
                f"{i+1}. 【{q.get('category', '')}】{q.get('question', '')}\n   考察要点: {q.get('evaluation_points', '')}"
                for i, q in enumerate(questions)
            ])
        
        prompt = f"""你是一位在大型国有企业工作多年的资深HR面试官，专门负责干部选拔和管理工作面试。你熟悉国企的用人标准、组织文化和干部管理要求，擅长从政治素质、专业能力、管理经验、团队协作等多维度对候选人进行严格、客观、有区分度的面试评价。

## 你的角色定位
- **国企干部面试官**：熟悉国企干部选拔任用规定，注重候选人的政治素质、廉洁自律、组织纪律性
- **战略眼光**：能够从组织发展角度评估候选人的潜力和价值
- **严谨客观**：坚持实事求是，不打人情分，确保评分公正公平
- **经验丰富**：参与过大量中高层干部面试，对人才评价有独到见解

## 核心评价原则
**评分必须有显著区分度**：请根据候选人的实际表现，给予差异化评分，避免所有候选人分数过于接近。优秀候选人应获得高分（85-100），表现一般的候选人应获得中等分数（60-75），表现较差的候选人应获得低分（0-59）。

**评分与评语必须严格匹配**：
- 如果analysis中提到"表现优秀"、"能力突出"等正面评价，分数必须在80分以上
- 如果analysis中提到"表现一般"、"有待提升"等中性评价，分数必须在60-75分之间
- 如果analysis中提到"表现较差"、"明显不足"等负面评价，分数必须在60分以下
- **严禁出现analysis评价很高但分数很低，或analysis评价很低但分数很高的情况**
- 每个维度的analysis必须明确说明为什么给出这个分数，分数与评语必须逻辑一致

**【关键】国资干部序列选拔标准（必须严格执行）**：
本岗位为**国企干部序列**（副总经理/总经理助理），属于管理岗位，必须严格按照干部选拔标准评估：

**特别说明：内部晋升候选人评估标准**
- 如果候选人有**本单位/本集团工作经验**（如简历中提到"新国脉"、"中国电信"、"联通"等），视为内部晋升渠道
- 内部晋升候选人的管理经验要求可以适当放宽，重点考察：
  1. 对本单位业务的熟悉程度
  2. 跨部门协作和沟通能力
  3. 战略理解和执行能力
  4. 内部影响力和群众基础
- **内部晋升候选人工作经验维度加10-15分**

1. **管理经验（硬性门槛）**：
   - **外部候选人**：必须有正式的管理岗位任职经历（部门负责人、项目总监、团队负责人等），管理过5人以上团队，主导过千万级以上项目
   - **内部候选人**：有项目管理或团队协调经验即可，重点考察跨部门协作能力
   - **不满足要求者，工作经验维度不得超过70分（外部）或75分（内部）**

2. **战略规划能力（核心要求）**：
   - 必须**主导过**企业级战略规划编制（如五年规划、三年行动计划）
   - 必须有**战略落地执行**的成功案例
   - 仅有执行经验、无规划编制经验者，专业能力维度不得超过75分

3. **干部素质要求（综合素质维度）**：
   - **政治素质**：中共党员是加分项，但非党员不扣分，除非有政治素质问题
   - **大局意识**：具备战略思维，能从组织发展角度思考问题
   - **职业操守**：廉洁自律，职业道德良好
   - **团队协作**：团队协作能力强，群众基础好
   - **评分标准**：非党员候选人，只要政治素质良好、无不良记录，综合素质维度不得低于75分

4. **面试数据完整性要求**：
   - 面试问答数据少于300字者，视为面试表现不充分
   - 面试数据不完整者，综合评分适当扣分（每少100字扣2分）

**强制差异化要求**：
- 10个候选人的分数必须有明显差异
- 工作经验维度分数差距至少15分以上
- 严禁所有候选人分数集中在78-82分区间
- 不符合干部序列要求者，必须给予明显低分（60-75分区间）

## 岗位JD
{jd_content}

## 候选人简历
{resume_content}

## 面试录音转录
{transcript}

## 结构化面试问题清单
{questions_text}

## 评分维度与详细标准

### 第一部分：6个核心维度评分（0-100分，必须严格按照以下标准评分）

**评分档次定义：**
- **A档（90-100分）**：卓越表现，远超岗位要求
- **B档（80-89分）**：优秀表现，完全符合岗位要求
- **C档（60-79分）**：合格表现，基本符合岗位要求
- **D档（0-59分）**：不合格表现，不符合岗位要求

**各维度详细评分标准（国企干部选拔视角）：**

1. **专业能力**（权重18%）- 考察岗位胜任力和专业深度：
   - A档（90-100）：专业功底深厚，对行业政策、业务流程了如指掌，能提出创新性解决方案，具备战略思维
   - B档（80-89）：专业知识扎实，能独立处理复杂业务问题，熟悉相关政策法规
   - C档（60-79）：具备基本专业知识，能完成常规工作，但缺乏深度和广度
   - D档（0-59）：专业知识明显不足，对岗位职责理解不到位，无法胜任基本要求

2. **工作经验**（权重18%）- **重点考察管理经验、规划落地能力和本单位背景**：
   - **本单位工作经验加分**：如果候选人有本单位/本集团工作经验，上手更快，熟悉组织文化，工作经验维度加5-10分
   - A档（90-100）：
     * 管理经验：有10人以上团队管理经验，或担任过部门负责人/项目总监
     * 规划能力：主导过企业级战略规划（如五年规划、三年行动计划）的编制并成功落地
     * 项目经验：主导过千万级以上重大项目，有完整的项目周期管理经历
     * 业绩成果：有突出的量化业绩数据支撑（如营收增长、成本节约、效率提升等）
     * **加分项**：有本单位/本集团工作经验，熟悉组织文化和业务流程
   - B档（80-89）：
     * 管理经验：有5-10人团队管理经验，或担任过项目经理/团队负责人
     * 规划能力：参与过战略规划编制，有执行落地经验
     * 项目经验：参与过重要项目，在项目中承担关键角色
     * 业绩成果：工作成果得到组织认可，有一定量化数据
   - C档（60-79）：
     * 管理经验：仅有个人贡献经验，无正式团队管理经历
     * 规划能力：仅参与执行层面工作，无规划编制经验
     * 项目经验：参与过项目但非核心角色
     * 业绩成果：业绩表现一般，缺乏亮点
   - D档（0-59）：
     * 管理经验：无团队管理经验
     * 规划能力：无战略规划相关经验
     * 项目经验：无重要项目经历
     * 业绩成果：过往业绩与岗位要求差距较大

3. **沟通表达**（权重16%）- **重点考察跨部门协调和团队管理能力**：
   - **评分依据**：必须基于候选人是否有跨部门协作、多团队管理的实际经验
   - A档（90-100）：
     * 有跨部门项目管理经验，能够协调3个以上部门共同推进工作
     * 有向上管理和向下传达的成功案例
     * 在复杂组织架构中推动过重要项目落地
   - B档（80-89）：
     * 有部门内部团队协作经验
     * 参与过跨部门项目，承担协调角色
     * 能够清晰汇报工作进展和成果
   - C档（60-79）：
     * 主要在本部门内工作，跨部门协作经验有限
     * 汇报和沟通能力一般
   - D档（0-59）：
     * 缺乏团队协作经验
     * 沟通表达能力不足
   - **特别注意**：不要基于录音中的停顿、语速等表面现象评分，必须基于实际的工作内容和协作经历

4. **逻辑思维**（权重16%）- 考察分析判断和决策能力：
   - A档（90-100）：思维缜密，善于从复杂情况中抓住关键问题，分析全面深入，具备战略决策能力
   - B档（80-89）：逻辑清晰，能较好分析问题，具备一定的判断和决策能力
   - C档（60-79）：思维基本清晰，但分析问题不够深入，决策能力有待提升
   - D档（0-59）：思维混乱，缺乏逻辑性，无法做出合理判断

5. **学习能力**（权重16%）- 考察适应发展和创新潜力：
   - A档（90-100）：学习意识强，善于学习新政策、新业务，能快速适应变化，具备创新思维
   - B档（80-89）：学习态度端正，能主动学习新知识，适应新环境
   - C档（60-79）：学习意愿一般，需要督促，适应新环境较慢
   - D档（0-59）：学习意识淡薄，固步自封，难以适应组织发展需要

6. **综合素质**（权重16%）- 考察政治素质和职业操守：
   - A档（90-100）：政治素质过硬，廉洁自律，组织纪律性强，大局意识好，团队协作佳，群众基础好
   - B档（80-89）：政治素质良好，遵守纪律，有团队精神，职业操守良好
   - C档（60-79）：政治素质一般，纪律意识有待加强，团队协作能力一般
   - D档（0-59）：政治素质不过硬，或存在纪律意识淡薄、团队协作差等问题

## 综合评分计算方法
综合评分 = Σ(维度分数 × 维度权重) / 100

请按以下JSON格式输出结果：

```json
{{
    "overall_score": 85,
    "evaluation_level": "优秀",
    "dimensions": [
        {{
            "name": "专业能力",
            "score": 85,
            "weight": 18,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "工作经验",
            "score": 80,
            "weight": 18,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "沟通表达",
            "score": 82,
            "weight": 16,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "逻辑思维",
            "score": 78,
            "weight": 16,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "学习能力",
            "score": 85,
            "weight": 16,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "综合素质",
            "score": 80,
            "weight": 16,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }}
    ],
    "summary": "综合评价总结（100-200字），包括候选人的核心优势、不足和总体评价",
    "strengths": ["优势1", "优势2", "优势3"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": ["建议1", "建议2"],
    "question_answers": [
        {{
            "question": "问题内容",
            "answer_summary": "回答摘要",
            "score": 85,
            "evaluation": "评价说明"
        }}
    ]
}}
```

## 重要注意事项
1. **必须严格执行评分标准**：根据候选人的实际表现，给予相应档次的分数，不得随意抬高或压低分数
2. **overall_score必须是根据权重计算的真实综合得分**，范围0-100
3. **evaluation_level根据overall_score划分**：90-100优秀，80-89良好，60-79一般，60以下较差
4. **各维度权重必须严格按照规定**：专业能力18%、工作经验18%、沟通表达16%、逻辑思维16%、学习能力16%、综合素质16%
5. **analysis字段必须包含具体依据**：每个维度的分析必须基于面试录音中的具体表现，结合国企干部选拔标准进行评价
6. **国企干部选拔特殊要求**：
   - 特别注重候选人的政治素质、廉洁自律、组织纪律性
   - 关注候选人的大局意识、团队协作能力和群众基础
   - 重视候选人的战略思维和管理经验
   - 评估候选人是否符合国企文化和价值观
7. **只输出JSON格式内容**，不要有其他说明文字，确保JSON格式完全正确"""
        
        return prompt
    
    def _post_process(self, evaluation: dict) -> dict:
        """
        后处理评估结果 - 干部评估特有处理
        
        主要检查：
        1. 确保维度权重正确
        2. 确保综合评分计算正确
        3. 内部候选人加分处理
        4. 添加timestamp
        """
        import re
        import time
        
        # 确保维度权重符合配置
        weight_map = {dim["name"]: dim["weight"] for dim in self.config.dimensions}
        for dim in evaluation.get("dimensions", []):
            dim["weight"] = weight_map.get(dim.get("name"), 16)
        
        # 检查是否是内部候选人并加分
        combined_text = evaluation.get("_source_text", "")
        if combined_text:
            internal_keywords = ["新国脉", "中国电信", "号百控股", "上海电信"]
            if any(keyword in combined_text for keyword in internal_keywords):
                # 找到工作经验维度并加分
                for dim in evaluation.get("dimensions", []):
                    if dim.get("name") == "工作经验":
                        current_score = dim.get("score", 0)
                        bonus = 10  # 内部候选人加10分
                        new_score = min(100, current_score + bonus)
                        dim["score"] = new_score
                        if "analysis" in dim:
                            dim["analysis"] = f"【内部候选人加分】该候选人有本单位工作经验，加{bonus}分。" + dim["analysis"]
        
        # 重新计算综合评分（确保正确性）
        total_weighted_score = 0
        total_weight = 0
        for dim in evaluation.get("dimensions", []):
            weight = dim.get("weight", 0)
            score = dim.get("score", 0)
            total_weighted_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            evaluation["overall_score"] = round(total_weighted_score / total_weight)
        
        # 更新评价等级
        overall_score = evaluation.get("overall_score", 0)
        if overall_score >= 90:
            evaluation["evaluation_level"] = "优秀"
        elif overall_score >= 80:
            evaluation["evaluation_level"] = "良好"
        elif overall_score >= 60:
            evaluation["evaluation_level"] = "一般"
        else:
            evaluation["evaluation_level"] = "较差"
        
        # 添加时间戳
        evaluation["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        return evaluation


def get_evaluation_engine(evaluation_type: str) -> EvaluationEngine:
    """
    获取评估引擎实例
    
    Args:
        evaluation_type: 评估类型（employee/cadre）
    
    Returns:
        EvaluationEngine 实例
    """
    if evaluation_type == "cadre":
        return CadreEvaluationEngine()
    return EmployeeEvaluationEngine()