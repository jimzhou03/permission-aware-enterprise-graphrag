from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core import database as db_module
from app.services.ingestion_service import seed_documents_and_chunks
from app.services.seed_service import seed_demo_data


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_module.init_database()
    if settings.seed_on_startup:
        db: Session = db_module.SessionLocal()
        try:
            seed_demo_data(db)
            seed_documents_and_chunks(db)
        finally:
            db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
