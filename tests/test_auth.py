import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_candidate(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "candidate1@example.com",
        "password": "secret123",
        "role": "candidate",
        "full_name": "John Doe"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data

@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "password": "password123",
        "role": "candidate",
        "full_name": "Dup"
    })
    resp = await client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "password": "password123",
        "role": "candidate",
        "full_name": "Dup2"
    })
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Email already registered"

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "login@example.com",
        "password": "pass123",
        "role": "recruiter",
        "full_name": "Login Test"
    })
    resp = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "pass123"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "wrongpass@example.com",
        "password": "correct",
        "role": "candidate",
        "full_name": "Wrong"
    })
    resp = await client.post("/auth/login", json={
        "email": "wrongpass@example.com",
        "password": "incorrect"
    })
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "email": "refresh@example.com",
        "password": "password123",
        "role": "candidate",
        "full_name": "Refresh"
    })
    refresh = reg.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

@pytest.mark.asyncio
async def test_logout_revokes_token(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "email": "logout@example.com",
        "password": "password123",
        "role": "candidate",
        "full_name": "Logout"
    })
    refresh = reg.json()["refresh_token"]
    await client.post("/auth/logout", json={"refresh_token": refresh})
    # Try to use the same refresh token again
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401