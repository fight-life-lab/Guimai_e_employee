"""
员工专业能力管理API
提供员工专业能力的增删改查和批量导入功能
支持多种Excel格式：试用期、绩效、专家、职称技能、专利
"""
import logging
import pandas as pd
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, create_engine
import json
import io

from app.config import get_settings
from app.models.emp_professional_ability import EmpProfessionalAbility

# 获取数据库配置
settings = get_settings()
DATABASE_URL = f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}@localhost:{settings.mysql_port}/{settings.mysql_database}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

router = APIRouter(prefix="/api/v1/professional-ability", tags=["员工专业能力"])
logger = logging.getLogger(__name__)


def detect_excel_type(columns):
    """根据列名自动检测Excel数据类型"""
    columns_str = ','.join([str(c).lower() for c in columns])
    
    # 试用期数据特征
    if '试用期分' in columns_str or ('考核时间' in columns_str and '考核人' in columns_str):
        return 'probation'
    
    # 绩效数据特征
    if any(year in columns_str for year in ['2021年度', '2022年度', '2023年度', '2024年度', '年度绩效']):
        return 'performance'
    
    # 专家数据特征
    if '专家' in columns_str and ('首席' in columns_str or '高级' in columns_str or '类别' in columns_str):
        return 'expert'
    
    # 专利数据特征
    if '专利' in columns_str or ('类别' in columns_str and ('发明' in columns_str or '实用新型' in columns_str)):
        return 'patent'
    
    # 职称/技能数据特征
    if '证书等级' in columns_str or '公司等级' in columns_str:
        return 'title_skill'
    
    # 默认类型
    return 'mixed'


def get_emp_code_and_name(row, columns):
    """从行数据中提取员工编号和姓名，支持多种列名"""
    emp_code = None
    emp_name = None
    
    # 尝试各种可能的列名
    for col in columns:
        col_lower = str(col).lower()
        if not emp_code and any(kw in col_lower for kw in ['员工id', '员工编号', '人员编码', '人员编号', 'emp_code', 'id']):
            emp_code = str(row.get(col, '')).strip()
        if not emp_name and any(kw in col_lower for kw in ['员工姓名', '姓名', 'name', '人员姓名']):
            emp_name = str(row.get(col, '')).strip()
    
    return emp_code, emp_name


@router.post("/batch-import", response_model=dict)
async def batch_import_professional_ability(file: UploadFile = File(...)):
    """
    批量导入员工专业能力数据
    支持多种Excel格式：试用期、绩效、专家、职称技能、专利
    """
    try:
        logger.info(f"[ProfessionalAbility] 开始批量导入文件: {file.filename}")
        
        # 读取上传的文件内容到 BytesIO
        contents = await file.read()
        excel_file = io.BytesIO(contents)
        
        # 读取Excel文件
        df = pd.read_excel(excel_file)
        columns = list(df.columns)
        logger.info(f"[ProfessionalAbility] 读取到 {len(df)} 行数据")
        logger.info(f"[ProfessionalAbility] Excel列名: {columns}")
        
        if len(df) == 0:
            return {
                "success": False,
                "message": "Excel文件中没有数据"
            }
        
        # 自动检测数据类型
        data_type = detect_excel_type(columns)
        logger.info(f"[ProfessionalAbility] 检测到数据类型: {data_type}")
        
        success_count = 0
        update_count = 0
        error_count = 0
        error_messages = []
        
        with SessionLocal() as db:
            for index, row in df.iterrows():
                try:
                    # 提取员工编号和姓名
                    emp_code, emp_name = get_emp_code_and_name(row, columns)
                    
                    logger.info(f"[ProfessionalAbility] 处理第{index + 2}行: emp_code={emp_code}, emp_name={emp_name}")
                    
                    if not emp_code or not emp_name:
                        error_count += 1
                        error_messages.append(f"第{index + 2}行: 员工编号或姓名为空")
                        logger.warning(f"[ProfessionalAbility] 第{index + 2}行: 员工编号或姓名为空")
                        continue
                    
                    # 检查是否已存在
                    existing = db.query(EmpProfessionalAbility).filter(
                        EmpProfessionalAbility.emp_code == emp_code
                    ).first()
                    
                    # 根据数据类型处理
                    if data_type == 'probation':
                        # 试用期数据处理
                        probation_score = None
                        for col in columns:
                            if '试用期分' in str(col):
                                try:
                                    probation_score = float(row.get(col))
                                    break
                                except:
                                    pass
                        
                        if existing:
                            existing.emp_name = emp_name
                            if probation_score is not None:
                                existing.probation_score = probation_score
                            update_count += 1
                        else:
                            new_record = EmpProfessionalAbility(
                                emp_code=emp_code,
                                emp_name=emp_name,
                                probation_score=probation_score
                            )
                            db.add(new_record)
                            success_count += 1
                    
                    elif data_type == 'performance':
                        # 绩效数据处理
                        performance_history = []
                        for col in columns:
                            col_str = str(col)
                            if '年度' in col_str or '绩效' in col_str:
                                year = col_str.replace('年度', '').replace('绩效', '').strip()
                                score_val = row.get(col)
                                if pd.notna(score_val):
                                    performance_history.append({
                                        "year": year,
                                        "score": str(score_val),
                                        "level": str(score_val)
                                    })
                        
                        if existing:
                            existing.emp_name = emp_name
                            if performance_history:
                                # 合并现有绩效数据
                                existing_history = existing.performance_history or []
                                existing_years = {p.get('year') for p in existing_history}
                                for ph in performance_history:
                                    if ph['year'] not in existing_years:
                                        existing_history.append(ph)
                                existing.performance_history = existing_history
                            update_count += 1
                        else:
                            new_record = EmpProfessionalAbility(
                                emp_code=emp_code,
                                emp_name=emp_name,
                                performance_history=performance_history if performance_history else None
                            )
                            db.add(new_record)
                            success_count += 1
                    
                    elif data_type == 'expert':
                        # 专家数据处理
                        is_company_expert = 0
                        is_senior_expert = 0
                        is_chief_expert = 0
                        
                        for col in columns:
                            col_str = str(col)
                            val = str(row.get(col, '')).strip()
                            if '专家' in col_str or '类别' in col_str:
                                if '首席' in val:
                                    is_chief_expert = 1
                                elif '高级' in val:
                                    is_senior_expert = 1
                                elif '公司' in val or '专家' in val:
                                    is_company_expert = 1
                        
                        if existing:
                            existing.emp_name = emp_name
                            existing.is_company_expert = is_company_expert
                            existing.is_senior_expert = is_senior_expert
                            existing.is_chief_expert = is_chief_expert
                            update_count += 1
                        else:
                            new_record = EmpProfessionalAbility(
                                emp_code=emp_code,
                                emp_name=emp_name,
                                is_company_expert=is_company_expert,
                                is_senior_expert=is_senior_expert,
                                is_chief_expert=is_chief_expert
                            )
                            db.add(new_record)
                            success_count += 1
                    
                    elif data_type == 'patent':
                        # 专利数据处理 - 统计每个员工的专利数量
                        if existing:
                            existing.emp_name = emp_name
                            existing.patents_count = (existing.patents_count or 0) + 1
                            update_count += 1
                        else:
                            new_record = EmpProfessionalAbility(
                                emp_code=emp_code,
                                emp_name=emp_name,
                                patents_count=1
                            )
                            db.add(new_record)
                            success_count += 1
                    
                    elif data_type == 'title_skill':
                        # 职称和技能数据处理
                        name_col = None
                        cert_col = None
                        company_col = None
                        
                        for col in columns:
                            col_str = str(col)
                            if '名称' in col_str:
                                name_col = col
                            elif '证书等级' in col_str:
                                cert_col = col
                            elif '公司等级' in col_str:
                                company_col = col
                        
                        if name_col:
                            title_name = str(row.get(name_col, '')).strip()
                            cert_level = str(row.get(cert_col, '')).strip() if cert_col else ''
                            company_level = str(row.get(company_col, '')).strip() if company_col else ''
                            
                            if title_name:
                                new_title = {
                                    "title_name": title_name,
                                    "cert_level": cert_level,
                                    "company_level": company_level
                                }
                                
                                if existing:
                                    existing.emp_name = emp_name
                                    existing_titles = existing.professional_titles or []
                                    # 检查是否已存在相同职称
                                    if not any(t.get('title_name') == title_name for t in existing_titles):
                                        existing_titles.append(new_title)
                                        existing.professional_titles = existing_titles
                                    update_count += 1
                                else:
                                    new_record = EmpProfessionalAbility(
                                        emp_code=emp_code,
                                        emp_name=emp_name,
                                        professional_titles=[new_title]
                                    )
                                    db.add(new_record)
                                    success_count += 1
                    
                    else:
                        # 混合类型或其他 - 尝试提取所有可能的数据
                        probation_score = None
                        is_company_expert = 0
                        is_senior_expert = 0
                        is_chief_expert = 0
                        
                        for col in columns:
                            col_str = str(col)
                            val = str(row.get(col, '')).strip()
                            
                            if '试用期分' in col_str:
                                try:
                                    probation_score = float(row.get(col))
                                except:
                                    pass
                            elif '专家' in col_str:
                                if '首席' in val:
                                    is_chief_expert = 1
                                elif '高级' in val:
                                    is_senior_expert = 1
                                elif val in ['是', '1', 'True']:
                                    is_company_expert = 1
                        
                        if existing:
                            existing.emp_name = emp_name
                            if probation_score is not None:
                                existing.probation_score = probation_score
                            if is_company_expert or is_senior_expert or is_chief_expert:
                                existing.is_company_expert = max(existing.is_company_expert or 0, is_company_expert)
                                existing.is_senior_expert = max(existing.is_senior_expert or 0, is_senior_expert)
                                existing.is_chief_expert = max(existing.is_chief_expert or 0, is_chief_expert)
                            update_count += 1
                        else:
                            new_record = EmpProfessionalAbility(
                                emp_code=emp_code,
                                emp_name=emp_name,
                                probation_score=probation_score,
                                is_company_expert=is_company_expert,
                                is_senior_expert=is_senior_expert,
                                is_chief_expert=is_chief_expert
                            )
                            db.add(new_record)
                            success_count += 1
                    
                    # 每100条提交一次
                    if (success_count + update_count) % 100 == 0:
                        db.commit()
                        
                except Exception as e:
                    error_count += 1
                    import traceback
                    error_detail = f"第{index + 2}行: {str(e)}"
                    error_messages.append(error_detail)
                    logger.error(f"[ProfessionalAbility] 处理第{index + 2}行出错: {e}")
                    logger.error(f"[ProfessionalAbility] 错误详情: {traceback.format_exc()}")
            
            # 最终提交
            db.commit()
        
        logger.info(f"[ProfessionalAbility] 导入完成: 新增{success_count}条, 更新{update_count}条, 失败{error_count}条")
        
        # 返回数据类型信息
        type_names = {
            'probation': '试用期数据',
            'performance': '绩效考核数据',
            'expert': '专家数据',
            'patent': '专利数据',
            'title_skill': '职称技能数据',
            'mixed': '综合数据'
        }
        
        return {
            "success": True,
            "message": f"【{type_names.get(data_type, '未知类型')}】导入完成：新增{success_count}条, 更新{update_count}条, 失败{error_count}条",
            "data_type": data_type,
            "data_type_name": type_names.get(data_type, '未知类型'),
            "total": len(df),
            "success_count": success_count,
            "update_count": update_count,
            "error_count": error_count,
            "errors": error_messages[:10]  # 只返回前10个错误
        }
        
    except Exception as e:
        logger.error(f"[ProfessionalAbility] 批量导入失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量导入失败: {str(e)}")


@router.get("/{emp_code}", response_model=dict)
async def get_professional_ability(emp_code: str):
    """获取员工专业能力信息"""
    try:
        with SessionLocal() as db:
            record = db.query(EmpProfessionalAbility).filter(
                EmpProfessionalAbility.emp_code == emp_code
            ).first()
            
            if not record:
                return {
                    "success": False,
                    "message": "未找到该员工的专业能力信息"
                }
            
            return {
                "success": True,
                "data": record.to_dict()
            }
    except Exception as e:
        logger.error(f"[ProfessionalAbility] 查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/", response_model=dict)
async def list_professional_abilities(skip: int = 0, limit: int = 100):
    """获取员工专业能力列表"""
    try:
        with SessionLocal() as db:
            records = db.query(EmpProfessionalAbility).offset(skip).limit(limit).all()
            total = db.query(EmpProfessionalAbility).count()
            
            return {
                "success": True,
                "data": [r.to_dict() for r in records],
                "total": total,
                "skip": skip,
                "limit": limit
            }
    except Exception as e:
        logger.error(f"[ProfessionalAbility] 查询列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/", response_model=dict)
async def create_professional_ability(data: dict):
    """创建或更新员工专业能力记录（用于前端直接提交）"""
    try:
        with SessionLocal() as db:
            emp_code = data.get('emp_code')
            emp_name = data.get('emp_name')
            
            if not emp_code or not emp_name:
                return {
                    "success": False,
                    "message": "员工编号和姓名不能为空"
                }
            
            # 检查是否已存在
            existing = db.query(EmpProfessionalAbility).filter(
                EmpProfessionalAbility.emp_code == emp_code
            ).first()
            
            if existing:
                # 更新现有记录
                existing.emp_name = emp_name
                if 'probation_score' in data:
                    existing.probation_score = data['probation_score']
                if 'performance_history' in data:
                    existing.performance_history = data['performance_history']
                if 'is_company_expert' in data:
                    existing.is_company_expert = data['is_company_expert']
                if 'is_senior_expert' in data:
                    existing.is_senior_expert = data['is_senior_expert']
                if 'is_chief_expert' in data:
                    existing.is_chief_expert = data['is_chief_expert']
                if 'professional_titles' in data:
                    existing.professional_titles = data['professional_titles']
                if 'professional_skills' in data:
                    existing.professional_skills = data['professional_skills']
                if 'patents_count' in data:
                    existing.patents_count = data['patents_count']
                if 'honors_count' in data:
                    existing.honors_count = data['honors_count']
                
                db.commit()
                db.refresh(existing)
                
                return {
                    "success": True,
                    "message": "更新成功",
                    "data": existing.to_dict()
                }
            else:
                # 创建新记录
                new_record = EmpProfessionalAbility(
                    emp_code=emp_code,
                    emp_name=emp_name,
                    probation_score=data.get('probation_score'),
                    performance_history=data.get('performance_history'),
                    is_company_expert=data.get('is_company_expert', 0),
                    is_senior_expert=data.get('is_senior_expert', 0),
                    is_chief_expert=data.get('is_chief_expert', 0),
                    professional_titles=data.get('professional_titles'),
                    professional_skills=data.get('professional_skills'),
                    patents_count=data.get('patents_count', 0),
                    honors_count=data.get('honors_count', 0)
                )
                
                db.add(new_record)
                db.commit()
                db.refresh(new_record)
                
                return {
                    "success": True,
                    "message": "创建成功",
                    "data": new_record.to_dict()
                }
    except Exception as e:
        logger.error(f"[ProfessionalAbility] 创建/更新失败: {e}")
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")
