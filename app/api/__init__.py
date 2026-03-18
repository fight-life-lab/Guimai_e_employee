"""API module."""

from app.api.feishu_webhook import router as feishu_router

__all__ = ["feishu_router"]
