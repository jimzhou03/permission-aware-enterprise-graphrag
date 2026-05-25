from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import RetrievalConfigPublic
from app.services.embedding_service import get_embedding_status
from app.services.graph_service import neo4j_service
from app.services.ingestion_service import SUPPORTED_UPLOAD_MIME_TYPES, SUPPORTED_UPLOAD_SUFFIXES
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
    embedding_status = get_embedding_status()
    graph_status = neo4j_service.get_status()
    last_sync_status = graph_status.get("last_sync_summary", {}).get("status")
    generator_mode = "openai-compatible" if settings.llm_mode == "api" else settings.llm_mode
    embedding_provider = (
        "deterministic-mock"
        if settings.embedding_mode == "mock"
        else (
            embedding_status.provider
            if embedding_status.availability != "not_checked"
            else f"local-{settings.local_embedding_backend}"
        )
    )
    indexing_mode = (
        "deterministic-local-embedding"
        if settings.embedding_mode == "mock"
        else f"real-local-embedding:{settings.local_embedding_backend}"
    )
    if settings.embedding_mode == "local" and embedding_status.fallback_used:
        indexing_mode = f"{indexing_mode}:fallback-to-mock"
    return RetrievalConfigPublic(
        embedding_provider=embedding_provider,
        embedding_dimension=settings.embedding_dimensions,
        retrieval_engine=runtime.retrieval_engine,
        top_k=settings.qa_top_k,
        default_top_k=settings.qa_top_k,
        generator_mode=generator_mode,
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
        model_mode=generator_mode,
        function_calling_mode="backend-controlled-trace",
        llm_autonomous_tool_calling=False,
        permission_authority="backend-rbac",
        document_upload_enabled=True,
        upload_max_size_bytes=settings.upload_max_size_bytes,
        upload_supported_types=sorted({*SUPPORTED_UPLOAD_SUFFIXES, *SUPPORTED_UPLOAD_MIME_TYPES}),
        indexing_mode=indexing_mode,
        neo4j_configured=bool(graph_status.get("neo4j_configured")),
        neo4j_available=bool(graph_status.get("neo4j_available")),
        graph_sync_enabled=bool(graph_status.get("graph_sync_enabled")),
        graph_sync_needed=bool(graph_status.get("graph_sync_needed")),
        graph_pending_sync_kb_codes=list(graph_status.get("pending_sync_kb_codes", [])),
        graph_visualization_enabled=True,
        graph_permission_scope="backend-rbac",
        graph_fallback_mode=str(graph_status.get("fallback_mode", "local_entity_projection")),
        graph_node_count=graph_status.get("node_count"),
        graph_relationship_count=graph_status.get("relationship_count"),
        graph_last_sync_status=str(last_sync_status) if last_sync_status is not None else None,
    )
