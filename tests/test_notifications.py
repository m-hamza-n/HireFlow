import pytest
from auth import decode_token

async def create_notif(recruiter_client, title="Test", body="Body"):
    """Helper: create notification by triggering an action that creates one,
    or insert via a workaround using the app's own session."""
    # We'll use the /users/me endpoint to get user_id, then insert via DB override
    me = await recruiter_client.get("/users/me")
    user_id = me.json()["id"]
    # Insert directly using the app's overridden DB session via a raw endpoint call
    # Since we don't have a direct create endpoint, use notify_user with app's DB
    from tasks.sync_db import SyncSessionLocal
    from models import Notification
    from unittest.mock import patch
    # Use test DB URL
    from config import settings
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    TEST_SYNC_URL = settings.DATABASE_URL.replace("hireflow", "hireflow_test").replace("+asyncpg", "")
    engine = create_engine(TEST_SYNC_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    notif = Notification(user_id=user_id, title=title, body=body, type="system", is_read=False)
    session.add(notif)
    session.commit()
    session.close()
    engine.dispose()

@pytest.mark.asyncio
async def test_get_notifications_empty(recruiter_client):
    resp = await recruiter_client.get("/notifications/")
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_create_and_get_notification(recruiter_client):
    await create_notif(recruiter_client, "Test Title", "Test Body")
    resp = await recruiter_client.get("/notifications/")
    assert resp.status_code == 200
    notifs = resp.json()
    assert len(notifs) == 1
    assert notifs[0]["title"] == "Test Title"
    assert notifs[0]["is_read"] == False

@pytest.mark.asyncio
async def test_mark_read(recruiter_client):
    await create_notif(recruiter_client, "Unread")
    notifs = (await recruiter_client.get("/notifications/")).json()
    notif_id = notifs[0]["id"]
    resp = await recruiter_client.patch(f"/notifications/{notif_id}/read")
    assert resp.status_code == 200
    notifs = (await recruiter_client.get("/notifications/")).json()
    assert notifs[0]["is_read"] == True

@pytest.mark.asyncio
async def test_mark_all_read(recruiter_client):
    await create_notif(recruiter_client, "Notif 1")
    await create_notif(recruiter_client, "Notif 2")
    resp = await recruiter_client.patch("/notifications/read-all")
    assert resp.status_code == 200
    notifs = (await recruiter_client.get("/notifications/")).json()
    assert all(n["is_read"] for n in notifs)

@pytest.mark.asyncio
async def test_delete_notification(recruiter_client):
    await create_notif(recruiter_client, "To Delete")
    notifs = (await recruiter_client.get("/notifications/")).json()
    notif_id = notifs[0]["id"]
    resp = await recruiter_client.delete(f"/notifications/{notif_id}")
    assert resp.status_code == 200
    notifs = (await recruiter_client.get("/notifications/")).json()
    assert len(notifs) == 0
