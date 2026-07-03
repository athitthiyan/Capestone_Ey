"""Real-time WebSocket route."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.realtime.websocket_manager import connection_manager

logger = logging.getLogger(__name__)
router = APIRouter()


def _authenticate_ws(token: str | None) -> bool:
    """Mirror get_current_user's JWT check. Native WebSocket clients can't set
    Authorization headers, so the token travels as a query parameter instead."""
    if not settings.AUTH_REQUIRED:
        return True
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        return False
    if not username:
        return False
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        return bool(user and user.is_active)
    finally:
        db.close()


@router.websocket("/ws/investigations/{investigation_id}")
async def websocket_investigation_endpoint(
    websocket: WebSocket, investigation_id: str, token: str | None = None
):
    """Stream real-time investigation updates to a client."""
    if not await asyncio.to_thread(_authenticate_ws, token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await connection_manager.connect(investigation_id, websocket)
    logger.info(f"WebSocket connected for investigation {investigation_id}")

    forward_task = asyncio.create_task(_forward_redis_events(investigation_id, websocket))
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"WS message on {investigation_id}: {data}")
            await websocket.send_json({"type": "ack", "investigation_id": investigation_id})
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for investigation {investigation_id}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"WebSocket error for {investigation_id}: {e}", exc_info=True)
    finally:
        forward_task.cancel()
        await connection_manager.disconnect(investigation_id, websocket)


async def _forward_redis_events(investigation_id: str, websocket: WebSocket) -> None:
    try:
        from app.realtime.redis_bus import subscribe_events

        async for event in subscribe_events(investigation_id):
            await websocket.send_json(event)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Redis forwarding stopped for {investigation_id}: {e}")
