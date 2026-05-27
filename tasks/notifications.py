import logging
from tasks.celery_app import celery_app
from tasks.sync_db import SyncSessionLocal
from models import Notification
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@celery_app.task
def notify_user(user_id: str, title: str, body: str, notification_type: str):
    session = SyncSessionLocal()
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            body=body,
            type=notification_type,
            created_at=datetime.now(timezone.utc)
        )
        session.add(notif)
        session.commit()
        logger.info(f"Notified user {user_id}: {title}")
    except Exception as e:
        logger.exception(f"Notify error: {e}")
        session.rollback()
    finally:
        session.close()''' docstring '''
class Utility:
    pass
