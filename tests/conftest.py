import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import update
from datetime import datetime, timedelta, timezone
from main import app
from database import get_db
from models import Base, Company
from config import settings

TEST_DATABASE_URL = settings.DATABASE_URL.replace("hireflow", "hireflow_test")

async def make_client(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    session = session_factory()
    async def override_get_db():
        yield session
    app.dependency_overrides[get_db] = override_get_db
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    await ac.__aenter__()
    return ac, session

@pytest.fixture(autouse=True)
async def client():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        async def override_get_db():
            yield session
        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()
        await session.rollback()
    await engine.dispose()

@pytest.fixture
async def recruiter_client():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        async def override_get_db():
            yield session
        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/register", json={
                "email": "recruiter@test.com", "password": "testpass123",
                "role": "recruiter", "full_name": "Test Recruiter"
            })
            ac.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
            yield ac
        app.dependency_overrides.clear()
        await session.rollback()
    await engine.dispose()

@pytest.fixture
async def candidate_client():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        async def override_get_db():
            yield session
        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/auth/register", json={
                "email": "candidate@test.com", "password": "testpass123",
                "role": "candidate", "full_name": "Test Candidate"
            })
            ac.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
            yield ac
        app.dependency_overrides.clear()
        await session.rollback()
    await engine.dispose()

@pytest.fixture
async def recruiter_company(recruiter_client):
    resp = await recruiter_client.post("/companies/", json={
        "name": "Test Company",
        "description": "A test company",
        "website": "https://test.com"
    })
    assert resp.status_code in (200, 201)
    return resp.json()

@pytest.fixture
async def paid_company(recruiter_client):
    resp = await recruiter_client.post("/companies/", json={
        "name": "Paid Company",
        "description": "Has basic plan",
        "website": "https://paid.com"
    })
    assert resp.status_code in (200, 201)
    company = resp.json()
    company_id = company["id"]
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await session.execute(
            update(Company).where(Company.id == company_id).values(
                plan="basic",
                plan_expires_at=datetime.utcnow() + timedelta(days=30)
            )
        )
        await session.commit()
    await engine.dispose()
    company["plan"] = "basic"
    return company
