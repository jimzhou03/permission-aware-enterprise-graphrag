from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import RetrievalConfigPublic
from app.services.local_router_service import get_router_status
from app.services.rag_service import get_retrieval_runtime
from sqlalchemy.orm import Session


router = APIRouter(prefix="/system", tags=["system"])
settings = get_settings()


@router.get("/retrieval-config", response_model=RetrievalConfigPublic)
def get_retrieval_config(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetrievalConfigPublic:
    runtime = get_retrieval_runtime(db)
    router_status = get_router_status()
    return RetrievalConfigPublic(
        embedding_provider="deterministic-mock",
        embedding_dimension=settings.embedding_dimensions,
        retrieval_engine=runtime.retrieval_engine,
        top_k=settings.qa_top_k,
        default_top_k=settings.qa_top_k,
        generator_mode=settings.llm_mode,
        router_mode=settings.local_router_mode,
        router_model=router_status.model,
        router_availability=router_status.availability,
        router_fallback_last=router_status.fallback_used,
        router_error_last=router_status.error,
        pgvector_available=runtime.pgvector_available,
        sql_vector_search_enabled=runtime.sql_vector_search_enabled,
        pgvector_sql_retrieval_enabled=runtime.sql_vector_search_enabled,
        pgvector_field_available=runtime.backend_name == "postgresql",
        cache_backend="redis" if settings.redis_url.startswith("redis://") else "memory",
        model_mode=settings.llm_mode,
        function_calling_mode="backend-controlled-trace",
        llm_autonomous_tool_calling=False,
        permission_authority="backend-rbac",
    )
