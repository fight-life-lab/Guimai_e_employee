"""Build knowledge base from sample data."""

import os
from datetime import date

from app.knowledge.builder import KnowledgeBuilder


def create_sample_documents():
    """Create sample documents for knowledge base."""
    os.makedirs("./data/documents", exist_ok=True)

    # Sample employee roster CSV
    csv_content = """name,department,position,hire_date,performance_score,contract_end_date,phone,email
张三,技术部,高级工程师,2020-03-15,85.5,2025-06-30,13800138001,zhangsan@company.com
李四,技术部,工程师,2021-06-01,55.0,2025-05-31,13800138002,lisi@company.com
王五,市场部,市场经理,2019-01-10,78.0,2025-12-31,13800138003,wangwu@company.com
赵六,人事部,HR专员,2022-09-01,45.5,2025-08-31,13800138004,zhaoliu@company.com
孙七,财务部,会计,2020-05-20,92.0,2025-04-15,13800138005,sunqi@company.com"""

    with open("./data/documents/employees.csv", "w", encoding="utf-8") as f:
        f.write(csv_content)

    # Sample policy markdown
    policy_content = """# 公司员工手册

## 考勤制度

### 工作时间
- 周一至周五：9:00 - 18:00
- 午休时间：12:00 - 13:00

### 迟到早退
- 迟到/早退 15分钟以内：口头警告
- 迟到/早退 15-30分钟：扣半天工资
- 迟到/早退 30分钟以上：按旷工半天处理

## 休假制度

### 年假
- 工作满1年不满10年：5天年假
- 工作满10年不满20年：10天年假
- 工作满20年以上：15天年假

### 病假
- 需提供医院证明
- 病假期间发放基本工资的80%

## 绩效管理制度

### 考核周期
- 季度考核：每季度末进行
- 年度考核：每年12月进行

### 考核等级
- A级（优秀）：90-100分
- B级（良好）：80-89分
- C级（合格）：60-79分
- D级（不合格）：60分以下

### 绩效应用
- 连续两次D级：进入PIP改进计划
- 年度绩效D级：取消年终奖
"""

    with open("./data/documents/policy.md", "w", encoding="utf-8") as f:
        f.write(policy_content)

    # Sample conversation records
    conversation_content = """谈心谈话记录

日期：2024-01-15
员工：李四
部门：技术部

谈话内容：
李四近期工作状态不佳，项目进度延迟。经了解，主要是家庭原因导致精力分散。
建议给予一定理解，同时提醒注意工作与生活平衡。

---

日期：2024-02-20
员工：赵六
部门：人事部

谈话内容：
赵六入职以来表现一般，工作效率较低。需要加强培训，提升业务能力。
建议安排导师指导，定期跟进工作进展。

---

日期：2024-03-10
员工：张三
部门：技术部

谈话内容：
张三工作表现优秀，技术能力强。表达了希望晋升的意愿，建议纳入晋升候选人名单。
"""

    with open("./data/documents/conversations.txt", "w", encoding="utf-8") as f:
        f.write(conversation_content)

    print("Sample documents created.")


def build_knowledge_base():
    """Build knowledge base from documents."""
    print("Building knowledge base...")

    # Create sample documents
    create_sample_documents()

    # Build knowledge base
    builder = KnowledgeBuilder()

    # Load documents
    print("Loading documents...")
    documents = builder.load_directory("./data/documents")
    print(f"Loaded {len(documents)} documents")

    if not documents:
        print("No documents found!")
        return

    # Split documents
    print("Splitting documents...")
    chunks = builder.split_documents(documents)
    print(f"Created {len(chunks)} chunks")

    # Build vector store
    print("Building vector store...")
    vector_store = builder.build_vector_store(chunks)
    print("Knowledge base built successfully!")

    # Test search
    print("\nTesting search...")
    results = builder.search("年假有多少天", k=2)
    for i, doc in enumerate(results, 1):
        print(f"[{i}] {doc.page_content[:200]}...")


if __name__ == "__main__":
    build_knowledge_base()
