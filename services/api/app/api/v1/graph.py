from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models import User
from app.schemas.graph import GraphOverviewResponse, GraphStatusResponse, GraphSyncResponse
from app.services.graph_service import build_permission_scoped_overview, neo4j_service, sync_neo4j_graph
from app.services.permission_service import list_allowed_knowledge_bases


router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/status", response_model=GraphStatusResponse)
def graph_status(
    _: User = Depends(get_current_user),
) -> GraphStatusResponse:
    return GraphStatusResponse(**neo4j_service.get_status())


@router.get("/overview", response_model=GraphOverviewResponse)
def graph_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GraphOverviewResponse:
    allowed_kbs = list_allowed_knowledge_bases(db, current_user)
    allowed_kb_ids = [kb.id for kb in allowed_kbs]
    allowed_kb_codes = [kb.code for kb in allowed_kbs]
    nodes, edges, notes = build_permission_scoped_overview(db, allowed_kb_ids=allowed_kb_ids)
    status_payload = neo4j_service.get_status()
    return GraphOverviewResponse(
        allowed_kb_ids=[str(item) for item in allowed_kb_ids],
        allowed_kb_codes=allowed_kb_codes,
        nodes=nodes,
        edges=edges,
        fallback_used=not bool(status_payload.get("neo4j_available")),
        generated_at=datetime.now(timezone.utc),
        security_notes=notes,
    )


@router.post("/sync", response_model=GraphSyncResponse)
def graph_sync(
    _: User = Depends(require_permission("admin:kb:write")),
    db: Session = Depends(get_db),
) -> GraphSyncResponse:
    summary = sync_neo4j_graph(db)
    status_payload = neo4j_service.get_status()
    fallback_used = not bool(status_payload.get("neo4j_available"))
    result_status = "success" if bool(summary.get("success")) else "neo4j_unavailable"
    return GraphSyncResponse(
        status=result_status,
        fallback_used=fallback_used,
        summary=summary,
    )
