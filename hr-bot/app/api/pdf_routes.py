from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import base64
import os

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])

class PDFRequest(BaseModel):
    employee_name: str
    position: str
    analysis_data: dict

@router.post("/generate")
async def generate_pdf(request: PDFRequest):
    """生成人岗适配分析PDF报告"""
    try:
        # 注册中文字体
        try:
            # 尝试使用系统中的中文字体
            pdfmetrics.registerFont(TTFont('SimSun', 'SimSun.ttf'))
        except:
            # 如果系统中没有SimSun字体，使用reportlab的默认字体
            pass
        
        # 创建PDF文档
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        # 准备内容
        story = []
        styles = getSampleStyleSheet()
        
        # 标题样式
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=1,  # 居中
            fontName='SimSun' if 'SimSun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        )
        
        # 副标题样式
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=15,
            fontName='SimSun' if 'SimSun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        )
        
        # 正文样式
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            spaceAfter=8,
            leading=12,
            fontName='SimSun' if 'SimSun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        )
        
        # 标题
        title = Paragraph(f"{request.employee_name}-{request.position}人岗适配分析报告", title_style)
        story.append(title)
        
        # 获取分析数据
        data = request.analysis_data
        
        # 能力雷达对比与AI评分理由
        if 'radar_data' in data:
            story.append(Paragraph("能力雷达对比与AI评分理由", subtitle_style))
            
            # 这里可以添加雷达图数据
            story.append(Spacer(1, 10))
        
        # 维度得分汇总
        if 'dimensions' in data:
            story.append(Paragraph("维度得分汇总", subtitle_style))
            
            # 准备表格数据
            table_data = [['维度', '权重', '岗位要求', '员工得分', '差距', '评价']]
            for dim in data['dimensions']:
                table_data.append([
                    dim.get('name', ''),
                    f"{dim.get('weight', 0)}%",
                    f"{dim.get('job_requirement', 0)}分",
                    f"{dim.get('score', 0)}分",
                    f"{dim.get('gap', 0):+.1f}分",
                    dim.get('evaluation', '')
                ])
            
            # 创建表格
            table = Table(table_data, colWidths=[30*mm, 20*mm, 25*mm, 25*mm, 20*mm, 40*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'SimSun' if 'SimSun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'SimSun' if 'SimSun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 15))
        
        # 人岗适配核心指标
        if 'overall_score' in data and 'job_requirement_score' in data:
            story.append(Paragraph("人岗适配核心指标", subtitle_style))
            
            # 计算人岗适配率
            match_rate = 0
            if data['job_requirement_score'] > 0:
                match_rate = (data['overall_score'] / data['job_requirement_score']) * 100
            
            # 准备指标数据
            metrics_data = [
                ['岗位能力分数', f"{data['job_requirement_score']:.1f}分"],
                ['员工能力分数', f"{data['overall_score']:.1f}分"],
                ['人岗适配率', f"{match_rate:.1f}%"]
            ]
            
            # 创建指标表格
            metrics_table = Table(metrics_data, colWidths=[60*mm, 40*mm])
            metrics_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'SimSun' if 'SimSun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
                ('FONTSIZE', (0, 0), (0, -1), 10),
                ('FONTSIZE', (1, 0), (1, -1), 12),
                ('FONTNAME', (1, 0), (1, -1), 'SimSun' if 'SimSun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(metrics_table)
            story.append(Spacer(1, 15))
        
        # 综合评价
        if 'conclusion' in data:
            story.append(Paragraph("综合评价", subtitle_style))
            story.append(Paragraph(data['conclusion'], body_style))
            story.append(Spacer(1, 15))
        
        # 发展建议
        if 'recommendations' in data:
            story.append(Paragraph("发展建议", subtitle_style))
            for i, rec in enumerate(data['recommendations'], 1):
                story.append(Paragraph(f"{i}. {rec}", body_style))
        
        # 构建PDF
        doc.build(story)
        
        # 获取PDF内容
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        
        # 转换为base64
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
        
        return {
            "success": True,
            "pdf_base64": pdf_base64,
            "filename": f"{request.employee_name}-{request.position}-{data.get('timestamp', '')}.pdf"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF生成失败: {str(e)}")
