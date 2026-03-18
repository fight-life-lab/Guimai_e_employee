"""Feishu Webhook handler - Optimized for fast response."""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from app.config import get_settings

router = APIRouter(prefix="/api/v1/feishu", tags=["feishu"])


class FeishuMessage:
    """Feishu message model."""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.event_type = data.get("header", {}).get("event_type", "")
        self.event_id = data.get("header", {}).get("event_id", "")
        self.token = data.get("token", "")
        event = data.get("event", {})
        message = event.get("message", {})
        self.message_id = message.get("message_id", "")
        self.chat_type = message.get("chat_type", "")
        self.message_type = message.get("message_type", "")
        content_str = message.get("content", "{}")
        try:
            self.content = json.loads(content_str)
        except json.JSONDecodeError:
            self.content = {"text": content_str}
        self.text = self.content.get("text", "")
        self.sender = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

    @property
    def is_text_message(self) -> bool:
        return self.message_type == "text"


class FeishuWebhookHandler:
    def __init__(self):
        self.settings = get_settings()
        self._hr_agent = None

    @property
    def hr_agent(self):
        if self._hr_agent is None:
            from app.agent import get_hr_agent
            self._hr_agent = get_hr_agent()
        return self._hr_agent

    def verify_signature(self, signature: str, timestamp: str, nonce: str, body: str) -> bool:
        if not self.settings.feishu_webhook_secret:
            return True
        try:
            sign_string = f"{timestamp}\n{nonce}\n{body}"
            calculated_sig = hmac.new(
                self.settings.feishu_webhook_secret.encode(),
                sign_string.encode(),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(calculated_sig, signature)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    async def handle_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # FAST response for URL verification
        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge", "")
            logger.info(f"URL verification: {challenge}")
            return {"challenge": challenge}

        event_type = payload.get("header", {}).get("event_type", "")
        if event_type == "im.message.receive_v1":
            import asyncio
            asyncio.create_task(self._process_message_async(payload))
        
        return {"status": "ok"}

    async def _process_message_async(self, payload: Dict[str, Any]):
        try:
            message = FeishuMessage(payload)
            if not message.is_text_message:
                return
            user_question = message.text.strip()
            if not user_question:
                return
            logger.info(f"Processing: {user_question}")
            # TODO: Process with HR agent and reply
        except Exception as e:
            logger.error(f"Error: {e}")


_handler: Optional[FeishuWebhookHandler] = None


def get_handler() -> FeishuWebhookHandler:
    global _handler
    if _handler is None:
        _handler = FeishuWebhookHandler()
    return _handler


@router.post("/webhook")
async def feishu_webhook(request: Request):
    start_time = time.time()
    try:
        body = await request.body()
        body_str = body.decode("utf-8")
        payload = json.loads(body_str)
        
        signature = request.headers.get("X-Lark-Signature", "")
        timestamp = request.headers.get("X-Lark-Timestamp", "")
        nonce = request.headers.get("X-Lark-Nonce", "")
        
        handler = get_handler()
        if not handler.verify_signature(signature, timestamp, nonce, body_str):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        result = await handler.handle_event(payload)
        
        elapsed = time.time() - start_time
        logger.info(f"Webhook processed in {elapsed:.3f}s")
        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "feishu-webhook", "timestamp": int(time.time())}
