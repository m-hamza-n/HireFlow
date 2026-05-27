import pytest
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_create_job_free_plan_returns_402(recruiter_client, recruiter_company):
    # Company is created with plan 'free'
    company = recruiter_company
    resp = await recruiter_client.post("/jobs/", json={
        "title": "Software Engineer",
        "description": "Develop software",
        "requirements": "Python, FastAPI",
        "company_id": company["id"],
        "job_type": "full_time",
        "location": "Remote",
        "salary_min": 50000,
        "salary_max": 80000
    })
    assert resp.status_code == 402
    assert "Free plan cannot post jobs" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_create_job_paid_plan_success(recruiter_client, paid_company):
    company = paid_company
    resp = await recruiter_client.post("/jobs/", json={
        "title": "Senior Engineer",
        "description": "Lead development",
        "requirements": "10+ years",
        "company_id": company["id"],
        "status": "active",
        "job_type": "remote",
        "location": "Worldwide",
        "salary_min": 100000,
        "salary_max": 150000
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Senior Engineer"
    assert data["status"] == "active"
    assert data["company_id"] == company["id"]

@pytest.mark.asyncio
async def test_list_jobs(recruiter_client, paid_company):
    # Create two active jobs
    await recruiter_client.post("/jobs/", json={
        "title": "Job A",
        "description": "Desc A",
        "requirements": "Req A",
        "company_id": paid_company["id"],
        "status": "active",
        "location": "New York",
        "job_type": "full_time"
    })
    await recruiter_client.post("/jobs/", json={
        "title": "Job B",
        "description": "Desc B",
        "requirements": "Req B",
        "company_id": paid_company["id"],
        "status": "active",
        "location": "London",
        "job_type": "remote"
    })
    resp = await recruiter_client.get("/jobs/?location=New%20York")
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Job A"

@pytest.mark.asyncio
async def test_update_job(recruiter_client, paid_company):
    create_resp = await recruiter_client.post("/jobs/", json={
        "title": "Original Title",
        "description": "Original Desc",
        "requirements": "Orig Req",
        "company_id": paid_company["id"],
        "status": "draft"
    })
    job_id = create_resp.json()["id"]
    update_resp = await recruiter_client.put(f"/jobs/{job_id}", json={
    "title": "Updated Title",
    "description": "Original Desc",
    "requirements": "Orig Req",
    "status": "active"
})
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Title"
    assert update_resp.json()["status"] == "active"

@pytest.mark.asyncio
async def test_delete_job(recruiter_client, paid_company):
    create_resp = await recruiter_client.post("/jobs/", json={
        "title": "To Delete",
        "description": "Delete me",
        "requirements": "None",
        "company_id": paid_company["id"]
    })
    job_id = create_resp.json()["id"]
    del_resp = await recruiter_client.delete(f"/jobs/{job_id}")
    assert del_resp.status_code == 204
    # Verify gone
    get_resp = await recruiter_client.get(f"/jobs/{job_id}")
    assert get_resp.status_code == 404

@pytest.mark.asyncio
async def test_change_job_status(recruiter_client, paid_company):
    create_resp = await recruiter_client.post("/jobs/", json={
        "title": "Status Test",
        "description": "Test",
        "requirements": "Test",
        "company_id": paid_company["id"],
        "status": "draft"
    })
    job_id = create_resp.json()["id"]
    patch_resp = await recruiter_client.patch(f"/jobs/{job_id}/status?status=active")
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "active"