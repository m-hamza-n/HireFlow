import pytest

@pytest.mark.asyncio
async def test_apply_to_job(candidate_client, recruiter_client, paid_company):
    # Create a job as recruiter
    job_resp = await recruiter_client.post("/jobs/", json={
        "title": "Applicable Job",
        "description": "Good job",
        "requirements": "Skills",
        "company_id": paid_company["id"],
        "status": "active"
    })
    job = job_resp.json()
    # Apply as candidate
    resp = await candidate_client.post("/applications/", json={
        "job_id": job["id"],
        "cover_letter": "I'm interested"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["job_id"] == job["id"]

@pytest.mark.asyncio
async def test_duplicate_application_409(candidate_client, recruiter_client, paid_company):
    job_resp = await recruiter_client.post("/jobs/", json={
        "title": "Duplicate Job",
        "description": "Test",
        "requirements": "Test",
        "company_id": paid_company["id"],
        "status": "active"
    })
    job = job_resp.json()
    await candidate_client.post("/applications/", json={"job_id": job["id"]})
    resp2 = await candidate_client.post("/applications/", json={"job_id": job["id"]})
    assert resp2.status_code == 409
    assert "Already applied" in resp2.json()["detail"]

@pytest.mark.asyncio
async def test_candidate_views_own_applications(candidate_client, recruiter_client, paid_company):
    job1 = (await recruiter_client.post("/jobs/", json={"title": "Job1", "description": "d1", "requirements": "r1", "company_id": paid_company["id"], "status": "active"})).json()
    job2 = (await recruiter_client.post("/jobs/", json={"title": "Job2", "description": "d2", "requirements": "r2", "company_id": paid_company["id"], "status": "active"})).json()
    await candidate_client.post("/applications/", json={"job_id": job1["id"]})
    await candidate_client.post("/applications/", json={"job_id": job2["id"]})
    resp = await candidate_client.get("/applications/mine")
    assert resp.status_code == 200
    apps = resp.json()
    assert len(apps) == 2
    assert any(app["job_id"] == job1["id"] for app in apps)

@pytest.mark.asyncio
async def test_recruiter_views_job_applications(recruiter_client, candidate_client, paid_company):
    job_resp = await recruiter_client.post("/jobs/", json={"title": "View Job", "description": "test", "requirements": "test", "company_id": paid_company["id"], "status": "active"})
    job = job_resp.json()
    # Candidate applies
    await candidate_client.post("/applications/", json={"job_id": job["id"]})
    # Recruiter views applications
    resp = await recruiter_client.get(f"/applications/job/{job['id']}")
    assert resp.status_code == 200
    apps = resp.json()
    assert len(apps) == 1
    assert apps[0]["job_id"] == job["id"]

@pytest.mark.asyncio
async def test_recruiter_updates_application_status(recruiter_client, candidate_client, paid_company):
    job_resp = await recruiter_client.post("/jobs/", json={"title": "Status Job", "description": "test", "requirements": "test", "company_id": paid_company["id"], "status": "active"})
    job = job_resp.json()
    app_resp = await candidate_client.post("/applications/", json={"job_id": job["id"]})
    app_id = app_resp.json()["id"]
    update_resp = await recruiter_client.patch(f"/applications/{app_id}/status", json={"status": "shortlisted"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "shortlisted"

@pytest.mark.asyncio
async def test_candidate_withdraw_application(candidate_client, recruiter_client, paid_company):
    job_resp = await recruiter_client.post("/jobs/", json={"title": "Withdraw Job", "description": "test", "requirements": "test", "company_id": paid_company["id"], "status": "active"})
    job = job_resp.json()
    app_resp = await candidate_client.post("/applications/", json={"job_id": job["id"]})
    app_id = app_resp.json()["id"]
    del_resp = await candidate_client.delete(f"/applications/{app_id}")
    assert del_resp.status_code == 204
    # Verify not found
    get_resp = await candidate_client.get(f"/applications/{app_id}")
    assert get_resp.status_code == 404