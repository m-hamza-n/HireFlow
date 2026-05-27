from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from routers import auth, users, companies, jobs, applications, ai
from services.chromadb_service import get_or_create_collection, upsert_document
from services.gemini import get_embedding
import logging
from routers import notifications
from routers import payments
from routers import admin
from fastapi.responses import HTMLResponse
from pathlib import Path
import asyncio


logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed knowledge base if empty
    try:
        collection = get_or_create_collection("knowledge_base")
        # Check if empty (by trying to query)
        if collection.count() == 0:
            logger.info("Seeding knowledge base...")
            # Read hiring_guidelines.txt
            kb_path = Path("knowledge_base/hiring_guidelines.txt")
            if kb_path.exists():
                text = kb_path.read_text(encoding="utf-8")
                # Chunk by paragraphs (~500 chars)
                chunks = []
                current = ""
                for para in text.split("\n\n"):
                    if len(current) + len(para) < 500:
                        current += para + "\n\n"
                    else:
                        if current:
                            chunks.append(current.strip())
                        current = para + "\n\n"
                if current:
                    chunks.append(current.strip())
                # Embed and upsert
                for i, chunk in enumerate(chunks):
                    embedding = await asyncio.to_thread(get_embedding, chunk)
                    if embedding:
                        upsert_document(
                            collection,
                            doc_id=f"kb_{i}",
                            embedding=embedding,
                            metadata={"chunk_id": i, "source": "hiring_guidelines.txt"},
                            document=chunk
                        )
                logger.info(f"Seeded {len(chunks)} chunks into knowledge_base")
            else:
                logger.warning("knowledge_base/hiring_guidelines.txt not found")
        else:
            logger.info("Knowledge base already seeded")
    except Exception as e:
        logger.exception(f"Failed to seed knowledge base: {e}")
    yield
    # Shutdown: nothing needed

app = FastAPI(title="HireFlow", lifespan=lifespan)

# Create static directories
Path("static/resumes").mkdir(parents=True, exist_ok=True)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(companies.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(ai.router)
app.include_router(notifications.router)
app.include_router(payments.router)
app.include_router(admin.router)


# Mount static files (for frontend later)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = Path("static/index.html")
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return HTMLResponse("<h1>HireFlow API</h1><p>Frontend not found.</p>")