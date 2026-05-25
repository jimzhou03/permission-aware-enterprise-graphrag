from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.models import User
from app.schemas.common import RetrievalConfigPublic


router = APIRouter(prefix="/system", tags=["system"])
settings = get_settings()


@router.get("/retrieval-config", response_model=RetrievalConfigPublic)
def get_retrieval_config(
    _: User = Depends(get_current_user),
) -> RetrievalConfigPublic:
    return RetrievalConfigPublic(
        embedding_provider="deterministic-mock",
        embedding_dimension=settings.embedding_dimensions,
        retrieval_engine="python-cosine-similarity-mvp",
        default_top_k=settings.qa_top_k,
        generator_mode=settings.llm_mode,
        router_mode=settings.local_router_mode,
        pgvector_sql_retrieval_enabled=False,
        pgvector_field_available=settings.database_url.startswith("postgresql"),
        cache_backend="redis" if settings.redis_url.startswith("redis://") else "memory",
        model_mode=settings.llm_mode,
    )
