"""FastAPI main application - 人力数字员工智能体系统."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api import feishu_router
from app.api.alignment_routes import router as alignment_router
from app.api.detailed_alignment_routes import router as detailed_alignment_router
from app.api.jd_match_routes import router as jd_match_router
from app.api.job_description_routes import router as job_description_router
from app.api.emp_roster_routes import router as emp_roster_router
from app.api.attendance_routes import router as attendance_router
from app.api.attendance_summary_routes import router as attendance_summary_router
from app.api.professional_ability_routes import router as professional_ability_router
from app.api.work_experience_routes import router as work_experience_router
from app.api.interview_evaluation_routes import router as interview_evaluation_router
from app.api.interview_evaluation_routes_v2 import router as interview_evaluation_v2_router
from app.api.interview_evaluation_ws import router as interview_evaluation_ws_router
from app.api.interview_evaluation_optimized import router as interview_evaluation_optimized_router
from app.api.pdf_routes import router as pdf_router
from app.api.strategic_alignment_routes import router as strategic_alignment_router
from app.api.value_contribution_routes import router as value_contribution_router
from app.api.interview_batch_routes import router as interview_batch_router
from app.api.batch_evaluation_routes import router as batch_evaluation_router
from app.config import get_settings
from app.database.models import init_database

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"Environment: {'development' if settings.debug else 'production'}")
    logger.info(f"vLLM Model: {settings.vllm_model}")
    logger.info(f"vLLM URL: {settings.vllm_url}")
    
    # Create necessary directories
    os.makedirs("./data", exist_ok=True)
    os.makedirs("./logs", exist_ok=True)
    os.makedirs("./models", exist_ok=True)
    
    # Initialize database
    try:
        logger.info("Initializing database...")
        await init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.warning("Application will continue without database connection")
    
    logger.info("Application started successfully")
    yield
    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title="人力数字员工智能体系统",
    description="基于大模型的HR智能问答和人岗适配评估系统",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 设置请求体大小限制（100MB，用于支持Base64编码的大文件上传）
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class LimitUploadSize(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length:
                content_length = int(content_length)
                max_size = 100 * 1024 * 1024  # 100MB
                if content_length > max_size:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "请求体过大，最大支持100MB"}
                    )
        return await call_next(request)

app.add_middleware(LimitUploadSize)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(feishu_router)
app.include_router(alignment_router)
app.include_router(detailed_alignment_router)
app.include_router(jd_match_router)
app.include_router(job_description_router, prefix="/api/v1/job-description")
app.include_router(emp_roster_router)
app.include_router(attendance_router)
app.include_router(attendance_summary_router)
app.include_router(professional_ability_router)
app.include_router(work_experience_router)
app.include_router(interview_evaluation_router)
app.include_router(interview_evaluation_v2_router)
app.include_router(interview_evaluation_ws_router)
app.include_router(interview_evaluation_optimized_router)
app.include_router(pdf_router)
app.include_router(strategic_alignment_router)
app.include_router(value_contribution_router)
app.include_router(interview_batch_router)
app.include_router(batch_evaluation_router)

# Mount static files (for web UI)
if os.path.exists("./static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount data directory (for interview data files)
if os.path.exists("./data"):
    app.mount("/data", StaticFiles(directory="data"), name="data")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "description": "人力数字员工智能体系统 - 人岗适配评估",
        "docs_url": "/docs",
        "endpoints": {
            "health": "/health",
            "config": "/api/v1/config",
            "alignment": {
                "analyze": "/api/v1/alignment/analyze",
                "analyze_stream": "/api/v1/alignment/analyze/stream",
                "compare": "/api/v1/alignment/compare",
                "dimensions": "/api/v1/alignment/dimensions",
            },
            "jd_match": {
                "analyze": "/api/v1/jd-match/analyze",
                "analyze_text": "/api/v1/jd-match/analyze-text",
                "batch_analyze": "/api/v1/jd-match/batch-analyze",
                "employees": "/api/v1/jd-match/employees",
            },
            "job_description": {
                "upload": "/api/v1/job-description/upload",
                "parse": "/api/v1/job-description/parse",
                "list": "/api/v1/job-description/list",
                "detail": "/api/v1/job-description/detail/{emp_id}",
            }
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
        "features": {
            "alignment_analysis": True,
            "streaming": True,
            "local_model": True,
        }
    }


@app.get("/api/v1/config")
async def get_config():
    """Get public configuration."""
    return {
        "app_name": settings.app_name,
        "vllm_model": settings.vllm_model,
        "embedding_model": settings.embedding_model,
        "contract_alert_days": settings.contract_alert_days,
        "performance_threshold": settings.performance_threshold,
        "feishu_configured": settings.is_feishu_configured,
        "data_local_only": True,  # 标记数据不出域
    }


if __name__ == "__main__":
    import uvicorn
    
    # 使用端口3111运行服务
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=3111,  # 指定端口3111
        reload=settings.debug,
        log_level="info",
    )
