from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database import get_db
from models import Notification, User
from dependencies import get_current_active_user
from auth import decode_token
from services.ws_manager import manager
from uuid import UUID

router = APIRouter(prefix="/notifications", tags=["notifications"])

# ---------- REST Endpoints ----------
@router.get("/")
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get own notifications, unread first."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.is_read.asc(), Notification.created_at.desc())
    )
    notifications = result.scalars().all()
    return notifications

@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    await db.commit()
    return {"message": "Marked as read"}

@router.patch("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark all own notifications as read."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "All notifications marked as read"}

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.delete(notif)
    await db.commit()
    return {"message": "Deleted"}

# ---------- WebSocket ----------
@router.websocket("/ws")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for live notifications. Expects ?token=JWT_ACCESS_TOKEN."""
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=1008, reason="Invalid token")
        return

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == UUID(user_id), User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        await websocket.close(code=1008, reason="User not found or inactive")
        return

    await manager.connect(str(user.id), websocket)
    try:
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(str(user.id))