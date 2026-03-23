#!/usr/bin/env python3
"""
HR岗位能力多维度评分测试脚本 - 5维度版本

功能：
1. 调用远程LLM（Qwen/Qwen3-235B-A22B-Instruct-2507）对岗位进行5维度能力打分
2. 将评分结果保存到远程MySQL数据库
3. 支持批量处理13个测试岗位

5个评分维度（根据业务需求调整）：
- 专业能力（professional）- 能力维度
- 经验（experience）- 经验维度（工作履历、职称证书）
- 创新能力（innovation）- 能力维度
- 学习能力（learning）- 知识+潜力维度
- 工作态度（attitude）- 工时维度+党工团

运行环境：
- Python 3.13
- FastAPI + SQLAlchemy
- MySQL (远程服务器: 121.229.172.161)

安装依赖：
    pip install httpx sqlalchemy pymysql aiomysql

运行方式：
    python test_position_scoring_5d.py
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    import httpx
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
except ImportError as e:
    print(f"错误：缺少必要的依赖包 - {e}")
    print("请安装依赖：pip install httpx sqlalchemy pymysql aiomysql")
    sys.exit(1)

# 添加项目路径
sys.path.insert(0, '/root/shijingjing/e-employee/hr-bot')

# ============ 配置参数 ============

# 远程LLM配置
REMOTE_LLM_URL = "http://180.97.200.118:30071/v1/chat/completions"
REMOTE_LLM_API_KEY = "z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
REMOTE_LLM_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"

# MySQL数据库配置（远程服务器）
MYSQL_HOST = "121.229.172.161"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"

# 构建MySQL连接URL
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
ASYNC_MYSQL_URL = f"mysql+aiomysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# ============ 13个测试岗位数据 ============

TEST_POSITIONS = [
    {
        "position_name": "高级算法工程师",
        "department": "AI研发中心",
        "job_level": "P7",
        "description": "负责AIGC核心算法研发，包括大语言模型微调、RAG系统构建、多模态内容生成等前沿技术研究。",
        "responsibilities": """1. 负责大语言模型的微调与优化，提升模型在特定业务场景的表现
2. 设计和实现RAG（检索增强生成）系统，提高生成内容的准确性和相关性
3. 研究多模态内容生成技术，包括文生图、图生文等方向
4. 跟踪AI领域最新研究进展，将前沿技术落地到业务场景
5. 指导初中级算法工程师，推动团队技术能力提升
6. 与产品、工程团队紧密协作，推动算法方案的产品化落地"""
    },
    {
        "position_name": "AIGC产品经理",
        "department": "产品部",
        "job_level": "P6",
        "description": "负责AIGC相关产品的规划、设计和落地，深入理解用户需求，推动AI技术在内容创作领域的应用。",
        "responsibilities": """1. 负责AIGC产品的整体规划和路线图制定
2. 深入调研用户需求，设计符合用户场景的AI功能
3. 与技术团队紧密协作，推动产品功能落地
4. 分析产品数据，持续优化产品体验
5. 跟踪AIGC行业动态，保持产品竞争力
6. 协调设计、运营等团队，确保产品顺利上线和推广"""
    },
    {
        "position_name": "后端开发工程师",
        "department": "技术部",
        "job_level": "P5",
        "description": "负责公司核心业务系统的后端开发，使用Python/FastAPI构建高性能API服务。",
        "responsibilities": """1. 负责业务系统后端API的设计与开发
2. 优化系统性能，保障服务高可用
3. 参与数据库设计和优化
4. 编写单元测试，保障代码质量
5. 参与代码评审，提升团队代码规范
6. 配合前端完成接口对接"""
    },
    {
        "position_name": "前端开发工程师",
        "department": "技术部",
        "job_level": "P5",
        "description": "负责公司Web应用和H5页面的前端开发，使用Vue3/React构建用户界面。",
        "responsibilities": """1. 负责Web应用和移动端H5页面的开发
2. 优化前端性能，提升用户体验
3. 与设计师协作，实现高保真页面还原
4. 参与前端架构设计和技术选型
5. 编写前端组件，提高代码复用率
6. 配合后端完成接口对接和数据联调"""
    },
    {
        "position_name": "数据分析师",
        "department": "数据部",
        "job_level": "P5",
        "description": "负责业务数据分析和挖掘，为产品决策和运营策略提供数据支持。",
        "responsibilities": """1. 负责业务数据的采集、清洗和分析
2. 构建数据报表和可视化看板
3. 深入分析用户行为，挖掘业务洞察
4. 支持AB测试设计和效果评估
5. 建立数据指标体系，监控业务健康度
6. 为产品和运营团队提供数据支持"""
    },
    {
        "position_name": "UI/UX设计师",
        "department": "设计部",
        "job_level": "P5",
        "description": "负责产品界面设计和用户体验优化，打造美观易用的产品界面。",
        "responsibilities": """1. 负责产品UI界面设计，输出设计稿
2. 参与用户研究，优化产品交互体验
3. 制定和维护设计规范
4. 跟进设计落地，确保实现效果
5. 参与设计评审，提升整体设计质量
6. 关注设计趋势，保持设计创新性"""
    },
    {
        "position_name": "测试工程师",
        "department": "质量部",
        "job_level": "P4",
        "description": "负责产品质量保障，设计和执行测试用例，确保产品稳定可靠。",
        "responsibilities": """1. 编写测试用例，执行功能测试
2. 参与需求评审，识别质量风险
3. 定位和跟踪缺陷，推动问题解决
4. 编写自动化测试脚本
5. 参与性能测试和安全测试
6. 总结测试经验，完善测试流程"""
    },
    {
        "position_name": "运维工程师",
        "department": "运维部",
        "job_level": "P5",
        "description": "负责公司基础设施运维，保障系统稳定运行，优化运维流程。",
        "responsibilities": """1. 负责服务器和网络设备的运维管理
2. 监控系统运行状态，及时处理故障
3. 优化系统架构，提升服务可用性
4. 编写运维脚本，实现自动化运维
5. 制定应急预案，组织演练
6. 管理云平台资源，控制成本"""
    },
    {
        "position_name": "HRBP",
        "department": "人力资源部",
        "job_level": "P5",
        "description": "负责业务部门的人力资源支持工作，推动组织发展和人才建设。",
        "responsibilities": """1. 深入了解业务需求，提供人力资源解决方案
2. 负责人才招聘和团队搭建
3. 推动绩效管理和员工发展
4. 处理员工关系，维护团队稳定
5. 参与组织变革和文化建设
6. 分析人力数据，支持管理决策"""
    },
    {
        "position_name": "行政专员",
        "department": "行政部",
        "job_level": "P3",
        "description": "负责公司日常行政事务，为员工提供良好的办公环境和后勤支持。",
        "responsibilities": """1. 负责办公用品采购和管理
2. 管理办公场地，维护办公环境
3. 组织公司活动和会议
4. 处理员工日常行政需求
5. 管理固定资产和档案
6. 协助处理对外接待事务"""
    },
    {
        "position_name": "内容运营",
        "department": "运营部",
        "job_level": "P4",
        "description": "负责产品内容运营，策划和执行内容策略，提升用户活跃度。",
        "responsibilities": """1. 策划和执行内容运营策略
2. 撰写和编辑优质内容
3. 分析内容数据，优化运营效果
4. 维护内容社区，提升用户互动
5. 挖掘用户需求，策划话题活动
6. 协调资源，推动内容项目落地"""
    },
    {
        "position_name": "市场营销经理",
        "department": "市场部",
        "job_level": "P6",
        "description": "负责公司产品的市场推广和品牌建设，制定营销策略，推动业务增长。",
        "responsibilities": """1. 制定市场营销策略和推广计划
2. 策划和执行品牌活动
3. 管理市场预算，评估投放效果
4. 分析市场趋势和竞品动态
5. 协调内外部资源，推动项目执行
6. 建立和维护媒体关系"""
    },
    {
        "position_name": "技术总监",
        "department": "技术部",
        "job_level": "P8",
        "description": "负责公司技术战略规划，领导技术团队，推动技术创新和架构演进。",
        "responsibilities": """1. 制定公司技术战略和发展规划
2. 领导技术团队，推动团队建设
3. 把控技术架构，保障系统稳定性
4. 推动技术创新，保持技术竞争力
5. 协调跨部门技术合作
6. 培养技术人才，建立技术文化"""
    }
]


# ============ LLM调用函数 ============

def build_scoring_prompt(position_name: str, department: str, description: str, responsibilities: str) -> str:
    """构建岗位能力评分Prompt - 5维度版本"""
    return f"""作为HR专家，请根据以下岗位信息，为"{position_name}"岗位生成5个维度的能力要求分数（0-100分）及理由。

【岗位信息】
岗位名称：{position_name}
所属部门：{department}

【岗位描述】
{description}

【岗位职责】
{responsibilities}

【重要提示】
- 请严格根据上述岗位描述和职责进行评估
- 不要参考其他岗位的信息

【评分原则 - 必须有侧重点】
不同岗位对不同维度的要求应该有所差异，不要所有维度都给高分：

1. **专业能力**（professional）：
   - 技术岗位（算法/开发）：90-100分（核心要求）
   - 产品岗位：85-95分
   - 运营/行政岗位：70-85分

2. **经验**（experience）：
   - 高级管理/专家岗位：90-100分（需要丰富履历）
   - 中级岗位：75-85分（需要一定工作经验）
   - 初级岗位：60-75分（经验要求相对较低）

3. **创新能力**（innovation）：
   - 研发/算法岗位：90-100分（核心要求）
   - 产品/设计岗位：85-95分（重要）
   - 运营/行政岗位：60-75分（一般要求）

4. **学习能力**（learning）：
   - 技术岗位：85-95分（技术更新快）
   - 其他岗位：70-85分

5. **工作态度**（attitude）：
   - 管理岗位：85-95分（需要带头示范）
   - 普通岗位：75-85分（基础要求）
   - 包含：出勤稳定性、加班情况、党工团参与、团队协作等

【重要】根据岗位特性，1-2个维度给90-100分（核心要求），2-3个维度给80-90分（重要），其他维度给70-80分（基础）！

请从以下5个维度评估该岗位的能力要求：
1. 专业能力（professional）：岗位对专业技能的要求程度
2. 经验（experience）：岗位对工作年限、履历、职称证书的要求
3. 创新能力（innovation）：岗位对创新思维、新技术应用的要求
4. 学习能力（learning）：岗位对持续学习、知识更新的要求（知识+潜力）
5. 工作态度（attitude）：岗位对出勤、加班、党工团参与、团队协作的要求

输出JSON格式：
{{
  "professional": {{"score": 95, "reasoning": "算法岗位需要深厚的技术功底"}},
  "experience": {{"score": 85, "reasoning": "需要5年以上相关工作经验"}},
  "innovation": {{"score": 90, "reasoning": "推荐算法需要持续创新优化"}},
  "learning": {{"score": 90, "reasoning": "技术更新快，需持续学习"}},
  "attitude": {{"score": 80, "reasoning": "需要良好的团队协作和出勤稳定性"}},
  "summary": "该岗位是技术核心岗位，对专业能力和学习能力要求极高..."
}}"""


async def call_remote_llm(prompt: str) -> Optional[Dict[str, Any]]:
    """调用远程LLM进行评分"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {REMOTE_LLM_API_KEY}"
    }
    
    payload = {
        "model": REMOTE_LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你是HR专家，请根据岗位描述客观评估能力要求。只输出JSON格式。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.1
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"  正在调用远程LLM...")
            response = await client.post(REMOTE_LLM_URL, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                print(f"  警告：无法从响应中提取JSON")
                return None
                
    except httpx.TimeoutException:
        print(f"  错误：LLM请求超时")
        return None
    except httpx.HTTPError as e:
        print(f"  错误：HTTP请求失败 - {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"  错误：JSON解析失败 - {e}")
        return None
    except Exception as e:
        print(f"  错误：调用LLM时发生异常 - {e}")
        return None


# ============ 数据库操作 ============

def init_mysql_tables():
    """初始化MySQL数据库表结构 - 5维度版本"""
    engine = create_engine(MYSQL_URL, echo=False)
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS position_capability_models_5d (
        id INT AUTO_INCREMENT PRIMARY KEY,
        position_name VARCHAR(100) NOT NULL,
        department VARCHAR(100),
        job_level VARCHAR(32),
        
        -- 5维度能力标准（0-100分）
        professional_standard INT DEFAULT 80,
        experience_standard INT DEFAULT 80,
        innovation_standard INT DEFAULT 80,
        learning_standard INT DEFAULT 80,
        attitude_standard INT DEFAULT 80,
        
        -- 维度权重
        professional_weight FLOAT DEFAULT 1.0,
        experience_weight FLOAT DEFAULT 1.0,
        innovation_weight FLOAT DEFAULT 1.0,
        learning_weight FLOAT DEFAULT 1.0,
        attitude_weight FLOAT DEFAULT 1.0,
        
        -- 维度评分理由
        professional_reasoning TEXT,
        experience_reasoning TEXT,
        innovation_reasoning TEXT,
        learning_reasoning TEXT,
        attitude_reasoning TEXT,
        
        -- AI总结
        ai_summary TEXT,
        
        description TEXT,
        requirements TEXT,
        responsibilities TEXT,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        INDEX idx_position_name (position_name),
        INDEX idx_department (department)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
            print("✓ 数据库表初始化成功 (5维度版本)")
    except Exception as e:
        print(f"✗ 数据库表初始化失败: {e}")
        raise


def save_scoring_result(result: Dict[str, Any]):
    """保存评分结果到MySQL - 5维度版本"""
    engine = create_engine(MYSQL_URL, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    
    insert_sql = """
    INSERT INTO position_capability_models_5d (
        position_name, department, job_level,
        professional_standard, experience_standard, innovation_standard,
        learning_standard, attitude_standard,
        professional_reasoning, experience_reasoning, innovation_reasoning,
        learning_reasoning, attitude_reasoning,
        ai_summary, description, responsibilities
    ) VALUES (
        :position_name, :department, :job_level,
        :professional_standard, :experience_standard, :innovation_standard,
        :learning_standard, :attitude_standard,
        :professional_reasoning, :experience_reasoning, :innovation_reasoning,
        :learning_reasoning, :attitude_reasoning,
        :ai_summary, :description, :responsibilities
    )
    """
    
    try:
        with SessionLocal() as session:
            session.execute(text(insert_sql), result)
            session.commit()
            return True
    except Exception as e:
        print(f"  保存到数据库失败: {e}")
        return False


def clear_existing_data():
    """清空现有测试数据"""
    engine = create_engine(MYSQL_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM position_capability_models_5d"))
            conn.commit()
            print("✓ 已清空现有测试数据")
    except Exception as e:
        print(f"✗ 清空数据失败: {e}")


# ============ 主测试流程 ============

async def score_single_position(position: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """对单个岗位进行评分 - 5维度"""
    print(f"\n{'='*60}")
    print(f"正在评分: {position['position_name']} ({position['department']})")
    print(f"{'='*60}")
    
    # 构建Prompt
    prompt = build_scoring_prompt(
        position_name=position['position_name'],
        department=position['department'],
        description=position['description'],
        responsibilities=position['responsibilities']
    )
    
    # 调用LLM
    llm_result = await call_remote_llm(prompt)
    
    if not llm_result:
        print(f"  ✗ 评分失败")
        return None
    
    # 构建结果 - 5维度
    result = {
        'position_name': position['position_name'],
        'department': position['department'],
        'job_level': position.get('job_level', ''),
        'description': position['description'],
        'responsibilities': position['responsibilities'],
        
        'professional_standard': llm_result.get('professional', {}).get('score', 80),
        'experience_standard': llm_result.get('experience', {}).get('score', 80),
        'innovation_standard': llm_result.get('innovation', {}).get('score', 80),
        'learning_standard': llm_result.get('learning', {}).get('score', 80),
        'attitude_standard': llm_result.get('attitude', {}).get('score', 80),
        
        'professional_reasoning': llm_result.get('professional', {}).get('reasoning', ''),
        'experience_reasoning': llm_result.get('experience', {}).get('reasoning', ''),
        'innovation_reasoning': llm_result.get('innovation', {}).get('reasoning', ''),
        'learning_reasoning': llm_result.get('learning', {}).get('reasoning', ''),
        'attitude_reasoning': llm_result.get('attitude', {}).get('reasoning', ''),
        
        'ai_summary': llm_result.get('summary', '')
    }
    
    # 打印评分结果
    print(f"\n  评分结果:")
    print(f"  - 专业能力: {result['professional_standard']}分 - {result['professional_reasoning'][:50]}...")
    print(f"  - 经验:     {result['experience_standard']}分 - {result['experience_reasoning'][:50]}...")
    print(f"  - 创新能力: {result['innovation_standard']}分 - {result['innovation_reasoning'][:50]}...")
    print(f"  - 学习能力: {result['learning_standard']}分 - {result['learning_reasoning'][:50]}...")
    print(f"  - 工作态度: {result['attitude_standard']}分 - {result['attitude_reasoning'][:50]}...")
    
    return result


async def run_batch_scoring():
    """批量评分主流程 - 5维度"""
    print("\n" + "="*80)
    print("HR岗位能力多维度评分测试 - 5维度版本")
    print("="*80)
    print(f"\n配置信息:")
    print(f"  - LLM模型: {REMOTE_LLM_MODEL}")
    print(f"  - LLM地址: {REMOTE_LLM_URL}")
    print(f"  - 数据库: MySQL ({MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE})")
    print(f"  - 测试岗位数: {len(TEST_POSITIONS)}")
    print(f"\n5个评分维度:")
    print(f"  1. 专业能力(professional) - 能力维度")
    print(f"  2. 经验(experience) - 经验维度(工作履历、职称证书)")
    print(f"  3. 创新能力(innovation) - 能力维度")
    print(f"  4. 学习能力(learning) - 知识+潜力维度")
    print(f"  5. 工作态度(attitude) - 工时+党工团维度")
    
    # 初始化数据库
    print("\n" + "-"*80)
    print("初始化数据库...")
    init_mysql_tables()
    clear_existing_data()
    
    # 批量评分
    print("\n" + "-"*80)
    print("开始批量评分...")
    
    results = []
    success_count = 0
    fail_count = 0
    
    for i, position in enumerate(TEST_POSITIONS, 1):
        print(f"\n[{i}/{len(TEST_POSITIONS)}] ", end="")
        
        result = await score_single_position(position)
        
        if result:
            # 保存到数据库
            if save_scoring_result(result):
                print(f"  ✓ 已保存到数据库")
                results.append(result)
                success_count += 1
            else:
                print(f"  ✗ 保存失败")
                fail_count += 1
        else:
            fail_count += 1
        
        # 添加延迟避免请求过快
        if i < len(TEST_POSITIONS):
            await asyncio.sleep(1)
    
    # 输出统计
    print("\n" + "="*80)
    print("测试完成统计")
    print("="*80)
    print(f"  成功: {success_count} 个岗位")
    print(f"  失败: {fail_count} 个岗位")
    print(f"  总计: {len(TEST_POSITIONS)} 个岗位")
    
    if results:
        print("\n  评分汇总:")
        print(f"  {'岗位名称':<20} {'部门':<12} {'专业':<6} {'经验':<6} {'创新':<6} {'学习':<6} {'态度':<6}")
        print(f"  {'-'*80}")
        for r in results:
            print(f"  {r['position_name']:<20} {r['department']:<12} "
                  f"{r['professional_standard']:<6} {r['experience_standard']:<6} "
                  f"{r['innovation_standard']:<6} {r['learning_standard']:<6} "
                  f"{r['attitude_standard']:<6}")
    
    print("\n" + "="*80)
    print("测试结束")
    print("="*80)
    
    return results


# ============ 入口函数 ============

if __name__ == "__main__":
    try:
        # 运行异步主流程
        results = asyncio.run(run_batch_scoring())
        
        # 输出最终结果JSON
        if results:
            print("\n\n完整结果JSON:")
            print(json.dumps(results, ensure_ascii=False, indent=2))
            
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n\n测试执行出错: {e}")
        import traceback
        traceback.print_exc()
