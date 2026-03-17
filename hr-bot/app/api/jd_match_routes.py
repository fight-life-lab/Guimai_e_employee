"""
JD匹配API路由 - 提供JD与简历匹配分析接口
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import logging

from app.database.models import get_async_session, Employee, EmployeeResume
from app.services.jd_matcher import get_jd_matcher, JDMatchResult
from app.services.file_parser import get_file_parser
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jd-match", tags=["JD匹配"])


# ============ 请求/响应模型 ============

class JDRequirementDimension(BaseModel):
    """JD要求维度"""
    name: str = Field(..., description="维度名称")
    importance: int = Field(..., description="重要程度(0-100)")
    requirement_level: str = Field(..., description="要求等级(高/中/低)")
    description: str = Field(..., description="JD对该维度的具体要求描述")
    keywords: List[str] = Field(default=[], description="关键词")


class JDMatchResponse(BaseModel):
    """JD匹配响应"""
    success: bool = Field(..., description="是否成功")
    overall_score: float = Field(..., description="综合匹配分数")
    match_level: str = Field(..., description="匹配等级")
    dimensions: List[dict] = Field(..., description="各维度匹配详情")
    jd_requirements: List[dict] = Field(..., description="JD各维度要求")
    summary: str = Field(..., description="匹配总结")
    strengths: List[str] = Field(default=[], description="候选人优势")
    weaknesses: List[str] = Field(default=[], description="候选人不足")
    recommendations: List[str] = Field(default=[], description="建议")
    radar_chart_data: dict = Field(..., description="候选人雷达图数据")
    jd_radar_chart_data: dict = Field(..., description="JD要求雷达图数据")


# ============ API路由 ============

@router.post("/analyze", response_model=JDMatchResponse)
async def analyze_jd_match(
    jd_content: Optional[str] = Form(None, description="JD文本内容"),
    jd_file: Optional[UploadFile] = File(None, description="JD文件(PDF/Word/Excel)"),
    employee_name: Optional[str] = Form(None, description="员工姓名"),
    resume_file: Optional[UploadFile] = File(None, description="简历文件(PDF/Word/Excel)"),
    use_remote_llm: Optional[bool] = Form(None, description="是否使用远程大模型（默认使用远程）"),
    db: AsyncSession = Depends(get_async_session)
):
    """
    分析JD与简历的匹配度

    - JD来源：jd_content 文本 或 jd_file 文件
    - 简历来源：employee_name 数据库 或 resume_file 文件
    """
    try:
        # 获取JD内容
        jd_text = jd_content or ""
        if jd_file:
            content = await jd_file.read()
            parsed_jd = get_file_parser().parse_file(content, jd_file.filename)
            if parsed_jd:
                jd_text = parsed_jd
            else:
                raise HTTPException(status_code=400, detail=f"无法解析JD文件: {jd_file.filename}")

        if not jd_text.strip():
            raise HTTPException(status_code=400, detail="请提供JD内容或上传JD文件")

        # 获取简历内容
        resume_text = ""
        if resume_file:
            content = await resume_file.read()
            parsed_resume = get_file_parser().parse_file(content, resume_file.filename)
            if parsed_resume:
                resume_text = parsed_resume
            else:
                raise HTTPException(status_code=400, detail=f"无法解析简历文件: {resume_file.filename}")
        elif employee_name:
            # 从数据库获取员工简历
            result = await db.execute(
                select(Employee, EmployeeResume)
                .join(EmployeeResume, Employee.id == EmployeeResume.employee_id, isouter=True)
                .where(Employee.name == employee_name)
            )
            employee, resume = result.first() or (None, None)

            if not employee:
                raise HTTPException(status_code=404, detail=f"未找到员工: {employee_name}")

            # 构建简历内容
            resume_parts = []
            resume_parts.append(f"姓名: {employee.name}")
            if employee.department:
                resume_parts.append(f"部门: {employee.department}")
            if employee.position:
                resume_parts.append(f"职位: {employee.position}")
            if employee.education:
                resume_parts.append(f"学历: {employee.education}")
            if employee.school:
                resume_parts.append(f"学校: {employee.school}")
            if employee.major:
                resume_parts.append(f"专业: {employee.major}")

            if resume:
                if resume.education_history:
                    resume_parts.append(f"\n教育经历:\n{resume.education_history}")
                if resume.work_experience:
                    resume_parts.append(f"\n工作经历:\n{resume.work_experience}")
                if resume.skills:
                    resume_parts.append(f"\n技能:\n{resume.skills}")
                if resume.raw_text:
                    resume_parts.append(f"\n简历原文:\n{resume.raw_text}")

            resume_text = "\n".join(resume_parts)

        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="请提供简历内容、上传简历文件或选择员工")

        # 调用匹配服务
        matcher = get_jd_matcher()
        match_result = await matcher.analyze_match(
            jd_content=jd_text,
            resume_content=resume_text,
            use_remote=use_remote_llm
        )

        # 获取候选人雷达图数据
        radar_data = matcher.get_radar_chart_data(match_result)

        # 获取JD要求雷达图数据
        jd_radar_data = matcher.get_jd_radar_chart_data(match_result)

        return JDMatchResponse(
            success=True,
            overall_score=match_result.overall_score,
            match_level=match_result.match_level,
            dimensions=[dim.model_dump() for dim in match_result.dimensions],
            jd_requirements=[req.model_dump() for req in match_result.jd_requirements],
            summary=match_result.summary,
            strengths=match_result.strengths,
            weaknesses=match_result.weaknesses,
            recommendations=match_result.recommendations,
            radar_chart_data=radar_data,
            jd_radar_chart_data=jd_radar_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[JD匹配] 分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/analyze-text", response_model=JDMatchResponse)
async def analyze_jd_match_text(
    jd_content: Optional[str] = Form(None, description="JD文本内容"),
    jd_file: Optional[UploadFile] = File(None, description="JD文件(PDF/Word/Excel)"),
    resume_content: Optional[str] = Form(None, description="简历文本内容"),
    resume_file: Optional[UploadFile] = File(None, description="简历文件(PDF/Word/Excel)"),
    use_remote_llm: Optional[bool] = Form(None, description="是否使用远程大模型（默认使用远程）")
):
    """
    直接分析JD和简历的匹配度（支持文本或文件）
    """
    try:
        # 获取JD内容
        jd_text = jd_content or ""
        if jd_file:
            content = await jd_file.read()
            parsed_jd = get_file_parser().parse_file(content, jd_file.filename)
            if parsed_jd:
                jd_text = parsed_jd
            else:
                raise HTTPException(status_code=400, detail=f"无法解析JD文件: {jd_file.filename}")

        if not jd_text.strip():
            raise HTTPException(status_code=400, detail="请提供JD内容或上传JD文件")

        # 获取简历内容
        resume_text = resume_content or ""
        if resume_file:
            content = await resume_file.read()
            parsed_resume = get_file_parser().parse_file(content, resume_file.filename)
            if parsed_resume:
                resume_text = parsed_resume
            else:
                raise HTTPException(status_code=400, detail=f"无法解析简历文件: {resume_file.filename}")

        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="请提供简历内容或上传简历文件")

        # 调用匹配服务
        matcher = get_jd_matcher()
        match_result = await matcher.analyze_match(
            jd_content=jd_text,
            resume_content=resume_text,
            use_remote=use_remote_llm
        )

        # 获取候选人雷达图数据
        radar_data = matcher.get_radar_chart_data(match_result)

        # 获取JD要求雷达图数据
        jd_radar_data = matcher.get_jd_radar_chart_data(match_result)

        return JDMatchResponse(
            success=True,
            overall_score=match_result.overall_score,
            match_level=match_result.match_level,
            dimensions=[dim.model_dump() for dim in match_result.dimensions],
            jd_requirements=[req.model_dump() for req in match_result.jd_requirements],
            summary=match_result.summary,
            strengths=match_result.strengths,
            weaknesses=match_result.weaknesses,
            recommendations=match_result.recommendations,
            radar_chart_data=radar_data,
            jd_radar_chart_data=jd_radar_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[JD匹配] 文本分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.get("/employees")
async def get_employees(
    db: AsyncSession = Depends(get_async_session)
):
    """
    获取所有员工列表（用于选择候选人）
    """
    try:
        result = await db.execute(
            select(Employee.id, Employee.name, Employee.department, Employee.position)
            .order_by(Employee.name)
        )
        employees = result.all()

        return {
            "success": True,
            "employees": [
                {
                    "id": emp.id,
                    "name": emp.name,
                    "department": emp.department,
                    "position": emp.position
                }
                for emp in employees
            ]
        }

    except Exception as e:
        logger.error(f"[JD匹配] 获取员工列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取员工列表失败: {str(e)}")
