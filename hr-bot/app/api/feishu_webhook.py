"""Feishu Webhook handler."""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import get_hr_agent
from app.config import get_settings
from app.database.models import Base
from app.database.crud import EmployeeCRUD, ContractCRUD
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

router = APIRouter(prefix="/api/v1/feishu", tags=["feishu"])

# Database setup
settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


class FeishuMessage:
    """Feishu message model."""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.event_type = data.get("header", {}).get("event_type", "")
        self.event_id = data.get("header", {}).get("event_id", "")
        self.token = data.get("token", "")

        # Message content
        event = data.get("event", {})
        message = event.get("message", {})
        self.message_id = message.get("message_id", "")
        self.chat_type = message.get("chat_type", "")
        self.message_type = message.get("message_type", "")

        # Parse content
        content_str = message.get("content", "{}")
        try:
            self.content = json.loads(content_str)
        except json.JSONDecodeError:
            self.content = {"text": content_str}

        self.text = self.content.get("text", "")
        self.sender = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

    @property
    def is_group_message(self) -> bool:
        """Check if message is from group chat."""
        return self.chat_type == "group"

    @property
    def is_text_message(self) -> bool:
        """Check if message is text type."""
        return self.message_type == "text"


class FeishuWebhookHandler:
    """Handler for Feishu webhook events."""

    def __init__(self):
        self.settings = get_settings()
        self.hr_agent = get_hr_agent()

    def verify_signature(
        self, signature: str, timestamp: str, nonce: str, body: str
    ) -> bool:
        """Verify Feishu webhook signature."""
        if not self.settings.feishu_webhook_secret:
            logger.warning("Feishu webhook secret not configured, skipping verification")
            return True

        try:
            # Build signature string
            sign_string = f"{timestamp}\n{nonce}\n{body}"

            # Calculate signature
            calculated_sig = hmac.new(
                self.settings.feishu_webhook_secret.encode(),
                sign_string.encode(),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(calculated_sig, signature)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    def parse_message(self, payload: Dict[str, Any]) -> Optional[FeishuMessage]:
        """Parse Feishu message from payload."""
        try:
            return FeishuMessage(payload)
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None

    async def handle_event(
        self, payload: Dict[str, Any], db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle Feishu event."""
        # Check for URL verification
        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge", "")
            logger.info(f"URL verification request, challenge: {challenge}")
            return {"challenge": challenge}

        # Parse message
        message = self.parse_message(payload)
        if not message:
            return {"status": "error", "message": "Failed to parse message"}

        # Handle message event
        if message.event_type == "im.message.receive_v1":
            return await self._handle_message(message, db)

        return {"status": "ok", "message": "Event received"}

    async def _handle_message(
        self, message: FeishuMessage, db: AsyncSession
    ) -> Dict[str, Any]:
        """Handle incoming message."""
        if not message.is_text_message:
            return {"status": "ok", "message": "Non-text message ignored"}

        user_question = message.text.strip()
        logger.info(f"Received message: {user_question}")

        if not user_question:
            return {"status": "ok", "message": "Empty message"}

        try:
            # Process with HR agent
            answer = await self.hr_agent.query(user_question, db)

            # Send reply
            await self.send_reply(message, answer)

            return {"status": "ok", "answer": answer}

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {"status": "error", "message": str(e)}

    async def send_reply(self, message: FeishuMessage, content: str):
        """Send reply to Feishu."""
        if not self.settings.feishu_webhook_url:
            logger.warning("Feishu webhook URL not configured")
            return

        try:
            # Build reply content
            reply_content = {
                "msg_type": "text",
                "content": {
                    "text": content
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.settings.feishu_webhook_url,
                    json=reply_content,
                    timeout=30.0,
                )
                response.raise_for_status()
                logger.info(f"Reply sent successfully: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending reply: {e}")


# Handler instance
_handler: Optional[FeishuWebhookHandler] = None


def get_handler() -> FeishuWebhookHandler:
    """Get or create handler singleton."""
    global _handler
    if _handler is None:
        _handler = FeishuWebhookHandler()
    return _handler


@router.post("/webhook")
async def feishu_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Feishu webhook endpoint."""
    try:
        # Get raw body
        body = await request.body()
        body_str = body.decode("utf-8")

        # Parse JSON
        payload = json.loads(body_str)

        # Get headers for signature verification
        signature = request.headers.get("X-Lark-Signature", "")
        timestamp = request.headers.get("X-Lark-Timestamp", "")
        nonce = request.headers.get("X-Lark-Nonce", "")

        # Verify signature
        handler = get_handler()
        if not handler.verify_signature(signature, timestamp, nonce, body_str):
            logger.warning("Signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Handle event
        result = await handler.handle_event(payload, db)
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
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "feishu-webhook",
        "timestamp": int(time.time()),
    }
