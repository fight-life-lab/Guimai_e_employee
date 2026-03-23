"""
员工工作经历管理API
提供从PDF履历中提取工作经历并存储的功能
"""
import logging
import re
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
import io

from app.config import get_settings
from app.models.emp_work_experience import EmpWorkExperience

# 获取数据库配置
settings = get_settings()
DATABASE_URL = f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}@localhost:{settings.mysql_port}/{settings.mysql_database}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

router = APIRouter(prefix="/api/v1/work-experience", tags=["员工工作经历"])
logger = logging.getLogger(__name__)


# 尝试导入PDF解析库
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("pdfplumber not installed, PDF extraction will not work")


class WorkExperienceItem(BaseModel):
    """工作经历项"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    company_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_current: bool = False


class WorkExperienceResponse(BaseModel):
    """工作经历响应"""
    success: bool
    message: str
    data: Optional[List[WorkExperienceItem]] = None
    extracted_count: int = 0


def parse_date(date_str: str) -> Optional[str]:
    """解析日期字符串，返回YYYY-MM-DD格式"""
    if not date_str or date_str.strip() == '':
        return None
    
    date_str = date_str.strip()
    
    # 尝试多种日期格式
    patterns = [
        (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
        (r'(\d{4})/(\d{2})/(\d{2})', '%Y/%m/%d'),
        (r'(\d{4})年(\d{2})月(\d{2})日', '%Y年%m月%d日'),
        (r'(\d{4})年(\d{1,2})月', '%Y年%m月'),
        (r'(\d{4})\.(\d{2})\.(\d{2})', '%Y.%m.%d'),
    ]
    
    for pattern, fmt in patterns:
        match = re.match(pattern, date_str)
        if match:
            try:
                if len(match.groups()) == 3:
                    year, month, day = match.groups()
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                elif len(match.groups()) == 2:
                    year, month = match.groups()
                    return f"{year}-{month.zfill(2)}-01"
            except:
                continue
    
    return None


def extract_work_experience_from_pdf(pdf_file: io.BytesIO) -> List[dict]:
    """
    从PDF文件中提取工作经历信息
    支持表格形式的工作经历数据
    """
    if not PDF_SUPPORT:
        raise HTTPException(status_code=500, detail="PDF解析库未安装，请安装 pdfplumber")
    
    experiences = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # 提取表格
                tables = page.extract_tables()
                
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    
                    # 查找表头
                    header_row = None
                    header_idx = -1
                    
                    for idx, row in enumerate(table):
                        if not row:
                            continue
                        row_text = ' '.join([str(cell or '') for cell in row])
                        # 检查是否包含工作经历相关的表头关键词
                        if any(keyword in row_text for keyword in ['开始日期', '结束日期', '工作单位', '部门', '职务', '工作经历']):
                            header_row = row
                            header_idx = idx
                            break
                    
                    if header_row is None:
                        continue
                    
                    # 确定列索引
                    col_mapping = {}
                    for idx, cell in enumerate(header_row):
                        if not cell:
                            continue
                        cell_text = str(cell).strip()
                        if '开始' in cell_text or '起始' in cell_text:
                            col_mapping['start_date'] = idx
                        elif '结束' in cell_text or '截止' in cell_text:
                            col_mapping['end_date'] = idx
                        elif '单位' in cell_text or '公司' in cell_text:
                            col_mapping['company_name'] = idx
                        elif '部门' in cell_text:
                            col_mapping['department'] = idx
                        elif '职务' in cell_text or '岗位' in cell_text or '职位' in cell_text:
                            col_mapping['position'] = idx
                    
                    # 如果没有找到关键列，尝试按位置推断
                    if 'start_date' not in col_mapping and len(header_row) >= 5:
                        # 假设第一列是开始日期，第二列是结束日期
                        col_mapping['start_date'] = 0
                        col_mapping['end_date'] = 1
                        col_mapping['company_name'] = 2
                        col_mapping['department'] = 3
                        col_mapping['position'] = 4
                    
                    # 提取数据行
                    for row in table[header_idx + 1:]:
                        if not row or all(not cell for cell in row):
                            continue
                        
                        # 检查是否是工作经历标题行
                        row_text = ' '.join([str(cell or '') for cell in row])
                        if '工作经历' in row_text and len([c for c in row if c]) <= 2:
                            continue
                        
                        experience = {}
                        
                        if 'start_date' in col_mapping and col_mapping['start_date'] < len(row):
                            experience['start_date'] = parse_date(str(row[col_mapping['start_date']] or ''))
                        
                        if 'end_date' in col_mapping and col_mapping['end_date'] < len(row):
                            end_date_str = str(row[col_mapping['end_date']] or '')
                            # 检查是否是在职状态
                            if any(keyword in end_date_str for keyword in ['至今', '现在', '在职', '—']):
                                experience['end_date'] = None
                                experience['is_current'] = True
                            else:
                                experience['end_date'] = parse_date(end_date_str)
                                experience['is_current'] = False
                        
                        if 'company_name' in col_mapping and col_mapping['company_name'] < len(row):
                            experience['company_name'] = str(row[col_mapping['company_name']] or '').strip()
                        
                        if 'department' in col_mapping and col_mapping['department'] < len(row):
                            experience['department'] = str(row[col_mapping['department']] or '').strip()
                        
                        if 'position' in col_mapping and col_mapping['position'] < len(row):
                            experience['position'] = str(row[col_mapping['position']] or '').strip()
                        
                        # 只添加有效的工作经历（至少要有公司名称）
                        if experience.get('company_name') and experience['company_name'].strip():
                            experiences.append(experience)
        
        return experiences
        
    except Exception as e:
        logger.error(f"PDF解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"PDF解析失败: {str(e)}")


@router.post("/extract-from-pdf", response_model=dict)
async def extract_work_experience_from_pdf_api(
    file: UploadFile = File(...),
    emp_code: str = Form(...),
    emp_name: str = Form(...)
):
    """
    从PDF履历文件中提取工作经历并保存到数据库
    """
    try:
        logger.info(f"[WorkExperience] 开始处理PDF文件: {file.filename}, 员工: {emp_name}({emp_code})")
        
        # 检查文件类型
        if not file.filename.lower().endswith('.pdf'):
            return {
                "success": False,
                "message": "请上传PDF文件"
            }
        
        # 读取PDF文件内容
        contents = await file.read()
        pdf_file = io.BytesIO(contents)
        
        # 提取工作经历
        experiences = extract_work_experience_from_pdf(pdf_file)
        
        logger.info(f"[WorkExperience] 提取到 {len(experiences)} 条工作经历")
        
        if not experiences:
            return {
                "success": False,
                "message": "未能从PDF中提取到工作经历信息，请检查PDF格式"
            }
        
        # 保存到数据库
        with SessionLocal() as db:
            # 先删除该员工现有的工作经历（可选，根据需求决定）
            db.query(EmpWorkExperience).filter(
                EmpWorkExperience.emp_code == emp_code
            ).delete()
            
            # 插入新的工作经历
            for exp in experiences:
                new_exp = EmpWorkExperience(
                    emp_code=emp_code,
                    emp_name=emp_name,
                    start_date=datetime.strptime(exp['start_date'], '%Y-%m-%d').date() if exp.get('start_date') else None,
                    end_date=datetime.strptime(exp['end_date'], '%Y-%m-%d').date() if exp.get('end_date') else None,
                    company_name=exp.get('company_name'),
                    department=exp.get('department'),
                    position=exp.get('position'),
                    is_current=1 if exp.get('is_current') else 0,
                    source_file=file.filename
                )
                db.add(new_exp)
            
            db.commit()
        
        return {
            "success": True,
            "message": f"成功提取并保存 {len(experiences)} 条工作经历",
            "extracted_count": len(experiences),
            "data": experiences
        }
        
    except Exception as e:
        logger.error(f"[WorkExperience] 处理PDF失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get("/{emp_code}", response_model=dict)
async def get_work_experience(emp_code: str):
    """获取员工工作经历列表"""
    try:
        with SessionLocal() as db:
            experiences = db.query(EmpWorkExperience).filter(
                EmpWorkExperience.emp_code == emp_code
            ).order_by(EmpWorkExperience.start_date.desc()).all()
            
            return {
                "success": True,
                "data": [exp.to_dict() for exp in experiences],
                "count": len(experiences)
            }
    except Exception as e:
        logger.error(f"[WorkExperience] 查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.delete("/{emp_code}", response_model=dict)
async def delete_work_experience(emp_code: str):
    """删除员工工作经历"""
    try:
        with SessionLocal() as db:
            count = db.query(EmpWorkExperience).filter(
                EmpWorkExperience.emp_code == emp_code
            ).delete()
            db.commit()
            
            return {
                "success": True,
                "message": f"已删除 {count} 条工作经历记录"
            }
    except Exception as e:
        logger.error(f"[WorkExperience] 删除失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
