"""FastAPI main application."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api import feishu_router
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(f"Starting {settings.app_name}...")

    # Create necessary directories
    os.makedirs("./data", exist_ok=True)
    os.makedirs("./logs", exist_ok=True)
    os.makedirs("./models", exist_ok=True)

    logger.info("Application started successfully")
    yield
    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title="人力数字员工智能体系统",
    description="基于大模型的HR智能问答和管理预警系统",
    version="1.0.0",
    lifespan=lifespan,
)

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


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "description": "人力数字员工智能体系统",
        "docs_url": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
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
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
