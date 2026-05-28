import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from main import app

# Override the Gemini and ChromaDB services for testing
@pytest.fixture(autouse=True)
def mock_ai_services(monkeypatch):
    # Mock get_embedding
    monkeypatch.setattr("services.gemini.get_embedding", lambda text: [0.1] * 768)
    # Mock query_collection
    async def mock_query(*args, **kwargs):
        return {
            "ids": [["candidate_1"]],
            "distances": [[0.2]],
            "metadatas": [[{"candidate_id": "11111111-1111-1111-1111-111111111111"}]],
            "documents": [["resume text"]]
        }
    monkeypatch.setattr("services.chromadb_service.query_collection", AsyncMock(side_effect=mock_query))
    # Mock chat_with_tools
    monkeypatch.setattr("routers.ai.chat_with_tools", AsyncMock(return_value={"reply": "Test reply", "tool_calls_made": []}))
    # Mock screen_application task
    monkeypatch.setattr("tasks.screening.screen_application.delay", MagicMock())
    # Mock embed_candidate task
    monkeypatch.setattr("tasks.matching.embed_candidate.delay", MagicMock())
    # Mock get_current_candidate for resume embed endpoint
    async def mock_candidate():
        from models import Candidate
        cand = Candidate(id="22222222-2222-2222-2222-222222222222", resume_text="dummy text")
        return cand
    monkeypatch.setattr("routers.ai.get_current_candidate", mock_candidate)

@pytest.mark.asyncio
async def test_ai_match_endpoint(recruiter_client, paid_company):
    # Create job
    job_resp = await recruiter_client.post("/jobs/", json={
        "title": "Match Job",
        "description": "Test matching",
        "requirements": "Python",
        "company_id": paid_company["id"],
        "status": "active"
    })
    job_id = job_resp.json()["id"]
    resp = await recruiter_client.get(f"/ai/match/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    # Expect at least one candidate (mock returns one)
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_ai_screen_manual(recruiter_client, candidate_client, paid_company):
    # Create job and application
    job_resp = await recruiter_client.post("/jobs/", json={
        "title": "Screen Job",
        "description": "Test screening",
        "requirements": "Python",
        "company_id": paid_company["id"],
        "status": "active"
    })
    job_id = job_resp.json()["id"]
    app_resp = await candidate_client.post("/applications/", json={"job_id": job_id})
    app_id = app_resp.json()["id"]
    resp = await recruiter_client.post(f"/ai/screen/{app_id}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Screening task triggered"

@pytest.mark.asyncio
async def test_ai_chat(client):
    # Register a user
    await client.post("/auth/register", json={
        "email": "chatuser@test.com",
        "password": "pass123",
        "role": "candidate",
        "full_name": "Chat User"
    })
    login_resp = await client.post("/auth/login", json={
        "email": "chatuser@test.com",
        "password": "pass123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/ai/chat", json={
        "messages": [{"role": "user", "content": "Find me a job"}]
    }, headers=headers)
    assert resp.status_code == 200
    assert "reply" in resp.json()
    assert "tool_calls_made" in resp.json()

@pytest.mark.asyncio
async def test_ai_embed_resume(candidate_client):
    # First upload a resume (using existing /users/me/resume endpoint)
    import io
    # Create a dummy PDF bytes (simplified – we'll mock parsing)
    dummy_pdf = b"%PDF-1.4\n...\n"
    files = {"file": ("resume.pdf", dummy_pdf, "application/pdf")}
    # Mock extract_text_from_pdf to return something
    from unittest.mock import patch
    with patch("routers.users.extract_text_from_pdf", return_value="Fake resume text"):
        upload_resp = await candidate_client.post("/users/me/resume", files=files)
        assert upload_resp.status_code == 200
    # Now call embed endpoint
    resp = await candidate_client.post("/ai/embed/resume")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Resume embedding task started"