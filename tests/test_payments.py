import pytest
from datetime import datetime
from sqlalchemy import select, update

@pytest.mark.asyncio
async def test_create_checkout_session(recruiter_client, recruiter_company):
    resp = await recruiter_client.post("/payments/checkout", json={"plan": "basic"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["plan"] == "basic"
    assert data["amount_cents"] == 2900

@pytest.mark.asyncio
async def test_confirm_payment(recruiter_client, recruiter_company):
    # First create a session
    checkout = await recruiter_client.post("/payments/checkout", json={"plan": "pro"})
    session_id = checkout.json()["session_id"]
    confirm_resp = await recruiter_client.post(f"/payments/confirm/{session_id}")
    assert confirm_resp.status_code == 200
    company_resp = await recruiter_client.get(f"/companies/{recruiter_company['id']}")
    assert company_resp.json()["plan"] == "pro"

@pytest.mark.asyncio
async def test_confirm_already_confirmed(recruiter_client, recruiter_company):
    checkout = await recruiter_client.post("/payments/checkout", json={"plan": "basic"})
    session_id = checkout.json()["session_id"]
    await recruiter_client.post(f"/payments/confirm/{session_id}")
    second = await recruiter_client.post(f"/payments/confirm/{session_id}")
    assert second.status_code == 400
    assert "already processed" in second.json()["detail"]

@pytest.mark.asyncio
async def test_payment_history(recruiter_client, recruiter_company):
    # Create two payments
    checkout1 = await recruiter_client.post("/payments/checkout", json={"plan": "basic"})
    await recruiter_client.post(f"/payments/confirm/{checkout1.json()['session_id']}")
    checkout2 = await recruiter_client.post("/payments/checkout", json={"plan": "pro"})
    await recruiter_client.post(f"/payments/confirm/{checkout2.json()['session_id']}")
    # Get history
    resp = await recruiter_client.get("/payments/history")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 2
    # Should be sorted descending by created_at
    assert history[0]["plan"] == "pro"
    assert history[1]["plan"] == "basic"
    assert history[0]["status"] == "completed"

@pytest.mark.asyncio
async def test_job_post_unlocked_after_upgrade(recruiter_client, recruiter_company):
    # Initially company is on free plan
    # Try to post job -> should fail with 402
    job_data = {
        "title": "Test Job",
        "description": "Test",
        "requirements": "Skills",
        "company_id": recruiter_company["id"],
        "status": "active"
    }
    resp_free = await recruiter_client.post("/jobs/", json=job_data)
    assert resp_free.status_code == 402
    assert "Free plan cannot post jobs" in resp_free.json()["detail"]
    # Upgrade to basic
    checkout = await recruiter_client.post("/payments/checkout", json={"plan": "basic"})
    session_id = checkout.json()["session_id"]
    await recruiter_client.post(f"/payments/confirm/{session_id}")
    # Try again
    resp_upgraded = await recruiter_client.post("/jobs/", json=job_data)
    assert resp_upgraded.status_code == 201

@pytest.mark.asyncio
async def test_plans_endpoint_public(client):
    resp = await client.get("/payments/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert "basic" in plans
    assert plans["basic"]["price"] == 29
    assert plans["pro"]["price"] == 99