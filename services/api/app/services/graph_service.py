from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Department, Document, DocumentChunk, KnowledgeBase
from app.schemas.graph import GraphEdgePublic, GraphNodePublic
from app.schemas.qa import Citation, GraphPath
from app.services.entity_service import extract_entities

try:
    from neo4j import GraphDatabase
except Exception:  # noqa: BLE001
    GraphDatabase = None  # type: ignore[assignment]


settings = get_settings()


@dataclass
class GraphQueryResult:
    chunk_id: str
    entities: list[str]
    related_entities: list[str]


class Neo4jService:
    def __init__(self) -> None:
        self._driver = None
        self._disabled = False
        self._lock = Lock()
        self._last_sync_summary: dict[str, Any] = {}
        self._sync_needed_kbs: dict[str, str] = {}

    def _neo4j_configured(self) -> bool:
        return bool(settings.neo4j_uri.strip() and settings.neo4j_user.strip() and settings.neo4j_password.strip())

    def _driver_or_none(self):
        if self._disabled:
            return None
        if not self._neo4j_configured():
            self._disabled = True
            return None
        if self._driver is not None:
            return self._driver
        if GraphDatabase is None:
            self._disabled = True
            return None
        try:
            driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                connection_timeout=1.0,
            )
            with driver.session() as session:
                session.run("RETURN 1").single()
            self._driver = driver
            return driver
        except Exception:  # noqa: BLE001
            try:
                driver.close()  # type: ignore[name-defined]
            except Exception:  # noqa: BLE001
                pass
            self._disabled = True
            return None

    def mark_sync_needed(self, *, kb_id: UUID, kb_code: str) -> None:
        with self._lock:
            self._sync_needed_kbs[str(kb_id)] = kb_code

    def _clear_sync_needed(self, kb_ids: list[str]) -> None:
        with self._lock:
            for kb_id in kb_ids:
                self._sync_needed_kbs.pop(kb_id, None)

    def _set_last_sync_summary(self, payload: dict[str, Any]) -> None:
        safe_payload: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe_payload[key] = value
        with self._lock:
            self._last_sync_summary = safe_payload

    def get_status(self) -> dict[str, Any]:
        configured = self._neo4j_configured() and GraphDatabase is not None
        node_count: int | None = None
        relationship_count: int | None = None
        driver = self._driver_or_none() if configured else None
        available = driver is not None
        if driver is not None:
            try:
                with driver.session() as session:
                    node_count = int(session.run("MATCH (n) RETURN count(n) AS count").single()["count"])
                    relationship_count = int(
                        session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]
                    )
            except Exception:  # noqa: BLE001
                available = False
                node_count = None
                relationship_count = None

        with self._lock:
            pending_sync_codes = sorted(set(self._sync_needed_kbs.values()))
            last_sync_summary = dict(self._last_sync_summary)

        return {
            "neo4j_configured": configured,
            "neo4j_available": available,
            "graph_sync_enabled": bool(settings.sync_neo4j_on_startup),
            "graph_sync_needed": bool(pending_sync_codes),
            "pending_sync_kb_codes": pending_sync_codes,
            "node_count": node_count,
            "relationship_count": relationship_count,
            "fallback_mode": "local_entity_projection" if not available else "neo4j",
            "last_sync_summary": last_sync_summary,
        }

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:  # noqa: BLE001
                pass
            self._driver = None

    def clear_for_tests(self) -> None:
        self.close()
        self._disabled = False
        with self._lock:
            self._last_sync_summary = {}
            self._sync_needed_kbs = {}

    def sync_from_postgres(self, db: Session) -> dict[str, Any]:
        start_at = datetime.now(timezone.utc)
        driver = self._driver_or_none()
        if driver is None:
            summary = {
                "status": "neo4j_unavailable",
                "success": False,
                "started_at": start_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            self._set_last_sync_summary(summary)
            return summary

        departments = list(db.scalars(select(Department)).all())
        knowledge_bases = list(db.scalars(select(KnowledgeBase).where(KnowledgeBase.is_active.is_(True))).all())
        chunks = list(
            db.scalars(
                select(DocumentChunk).join(KnowledgeBase).where(KnowledgeBase.is_active.is_(True))
            ).all()
        )
        kb_map = {kb.id: kb for kb in knowledge_bases}

        with driver.session() as session:
            for department in departments:
                session.run(
                    "MERGE (d:Department {id: $id}) "
                    "SET d.code=$code, d.name=$name",
                    id=str(department.id),
                    code=department.code,
                    name=department.name,
                )

            for kb in knowledge_bases:
                session.run(
                    "MERGE (k:KnowledgeBase {id: $id}) "
                    "SET k.code=$code, k.name=$name, k.version=$version",
                    id=str(kb.id),
                    code=kb.code,
                    name=kb.name,
                    version=kb.version,
                )
                if kb.department_id:
                    session.run(
                        "MATCH (d:Department {id: $department_id}), (k:KnowledgeBase {id: $kb_id}) "
                        "MERGE (d)-[:OWNS_KB]->(k)",
                        department_id=str(kb.department_id),
                        kb_id=str(kb.id),
                    )

            for chunk in chunks:
                kb = kb_map.get(chunk.knowledge_base_id)
                if kb is None or chunk.document is None:
                    continue
                session.run(
                    "MERGE (doc:Document {id: $document_id}) "
                    "SET doc.title=$title",
                    document_id=str(chunk.document.id),
                    title=chunk.document.title,
                )
                session.run(
                    "MERGE (c:Chunk {id: $chunk_id}) "
                    "SET c.kb_id=$kb_id, c.document_id=$document_id, c.ordinal=$ordinal",
                    chunk_id=str(chunk.id),
                    kb_id=str(chunk.knowledge_base_id),
                    document_id=str(chunk.document.id),
                    ordinal=chunk.ordinal,
                )
                session.run(
                    "MATCH (k:KnowledgeBase {id: $kb_id}), (doc:Document {id: $document_id}) "
                    "MERGE (k)-[:HAS_DOCUMENT]->(doc)",
                    kb_id=str(kb.id),
                    document_id=str(chunk.document.id),
                )
                session.run(
                    "MATCH (doc:Document {id: $document_id}), (c:Chunk {id: $chunk_id}) "
                    "MERGE (doc)-[:HAS_CHUNK]->(c)",
                    document_id=str(chunk.document.id),
                    chunk_id=str(chunk.id),
                )
                entities = _chunk_entities(chunk)
                for entity in entities:
                    session.run(
                        "MERGE (e:Entity {name: $name})",
                        name=entity,
                    )
                    session.run(
                        "MATCH (c:Chunk {id: $chunk_id}), (e:Entity {name: $name}) "
                        "MERGE (c)-[:MENTIONS]->(e)",
                        chunk_id=str(chunk.id),
                        name=entity,
                    )
                for idx in range(len(entities) - 1):
                    left = entities[idx]
                    right = entities[idx + 1]
                    session.run(
                        "MATCH (a:Entity {name: $left}), (b:Entity {name: $right}) "
                        "MERGE (a)-[:RELATED_TO]-(b)",
                        left=left,
                        right=right,
                    )
        summary = {
            "status": "success",
            "success": True,
            "started_at": start_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "department_count": len(departments),
            "knowledge_base_count": len(knowledge_bases),
            "chunk_count": len(chunks),
        }
        self._set_last_sync_summary(summary)
        self._clear_sync_needed([str(kb.id) for kb in knowledge_bases])
        return summary

    def query_chunk_graph(
        self,
        *,
        chunk_id: str,
        allowed_kb_ids: list[str],
    ) -> GraphQueryResult | None:
        driver = self._driver_or_none()
        if driver is None:
            return None
        cypher = (
            "MATCH (c:Chunk {id: $chunk_id})-[:MENTIONS]->(e:Entity) "
            "WHERE c.kb_id IN $allowed_kb_ids "
            "OPTIONAL MATCH (e)-[:RELATED_TO]-(r:Entity) "
            "RETURN c.id AS chunk_id, "
            "collect(DISTINCT e.name)[0..6] AS entities, "
            "collect(DISTINCT r.name)[0..6] AS related"
        )
        try:
            with driver.session() as session:
                row = session.run(
                    cypher,
                    chunk_id=chunk_id,
                    allowed_kb_ids=allowed_kb_ids,
                ).single()
        except Exception:  # noqa: BLE001
            return None
        if row is None:
            return None
        return GraphQueryResult(
            chunk_id=row.get("chunk_id", chunk_id),
            entities=[item for item in (row.get("entities") or []) if isinstance(item, str)],
            related_entities=[item for item in (row.get("related") or []) if isinstance(item, str)],
        )


def _chunk_entities(chunk: DocumentChunk) -> list[str]:
    metadata = chunk.chunk_metadata if isinstance(chunk.chunk_metadata, dict) else {}
    metadata_entities = metadata.get("entities")
    if isinstance(metadata_entities, list):
        values = [item for item in metadata_entities if isinstance(item, str)]
        if values:
            return values[:6]
    return extract_entities(chunk.content, limit=6)


def _chunk_preview(text: str, max_length: int = 120) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length]}..."


def _graph_node_id(node_type: str, raw: str) -> str:
    return f"{node_type}:{raw}"


def build_graph_elements_from_chunk_rows(
    chunk_rows: list[tuple[DocumentChunk, Document, KnowledgeBase]],
    *,
    include_chunk_preview: bool,
    max_entities_per_chunk: int = 3,
) -> tuple[list[GraphNodePublic], list[GraphEdgePublic]]:
    node_map: dict[str, GraphNodePublic] = {}
    edge_map: dict[str, GraphEdgePublic] = {}

    def add_node(node: GraphNodePublic) -> None:
        if node.id not in node_map:
            node_map[node.id] = node

    def add_edge(edge: GraphEdgePublic) -> None:
        if edge.id not in edge_map:
            edge_map[edge.id] = edge

    for chunk, document, kb in chunk_rows:
        department_code = kb.department.code if kb.department else "public"
        department_node_id = _graph_node_id("department", department_code)
        kb_node_id = _graph_node_id("knowledge_base", str(kb.id))
        doc_node_id = _graph_node_id("document", str(document.id))
        chunk_node_id = _graph_node_id("chunk", str(chunk.id))

        add_node(
            GraphNodePublic(
                id=department_node_id,
                label=department_code,
                type="department",
                metadata_summary="department node",
            )
        )
        add_node(
            GraphNodePublic(
                id=kb_node_id,
                label=kb.code,
                type="knowledge_base",
                kb_id=str(kb.id),
                kb_code=kb.code,
                title=kb.name,
                metadata_summary=f"version={kb.version} visibility={kb.visibility}",
            )
        )
        add_node(
            GraphNodePublic(
                id=doc_node_id,
                label=document.title,
                type="document",
                kb_id=str(kb.id),
                kb_code=kb.code,
                title=document.title,
                metadata_summary=f"source={document.source_label}",
            )
        )
        add_node(
            GraphNodePublic(
                id=chunk_node_id,
                label=f"chunk #{chunk.ordinal}",
                type="chunk",
                kb_id=str(kb.id),
                kb_code=kb.code,
                title=str(chunk.id),
                metadata_summary=(
                    f"chunk_id={chunk.id} preview={_chunk_preview(chunk.content)}"
                    if include_chunk_preview
                    else f"chunk_id={chunk.id}"
                ),
            )
        )

        add_edge(
            GraphEdgePublic(
                id=f"{department_node_id}|BELONGS_TO|{kb_node_id}",
                source=department_node_id,
                target=kb_node_id,
                type="BELONGS_TO",
                label="BELONGS_TO",
            )
        )
        add_edge(
            GraphEdgePublic(
                id=f"{kb_node_id}|CONTAINS|{doc_node_id}",
                source=kb_node_id,
                target=doc_node_id,
                type="CONTAINS",
                label="CONTAINS",
            )
        )
        add_edge(
            GraphEdgePublic(
                id=f"{doc_node_id}|HAS_CHUNK|{chunk_node_id}",
                source=doc_node_id,
                target=chunk_node_id,
                type="HAS_CHUNK",
                label="HAS_CHUNK",
            )
        )

        entities = _chunk_entities(chunk)[: max(1, max_entities_per_chunk)]
        previous_entity_node_id: str | None = None
        for entity in entities:
            entity_node_id = _graph_node_id("entity", entity)
            add_node(
                GraphNodePublic(
                    id=entity_node_id,
                    label=entity,
                    type="entity",
                    kb_id=str(kb.id),
                    kb_code=kb.code,
                    title=entity,
                    metadata_summary="entity extracted from authorized chunk",
                )
            )
            add_edge(
                GraphEdgePublic(
                    id=f"{chunk_node_id}|MENTIONS|{entity_node_id}",
                    source=chunk_node_id,
                    target=entity_node_id,
                    type="MENTIONS",
                    label="MENTIONS",
                )
            )
            if previous_entity_node_id:
                add_edge(
                    GraphEdgePublic(
                        id=f"{previous_entity_node_id}|RELATED_TO|{entity_node_id}",
                        source=previous_entity_node_id,
                        target=entity_node_id,
                        type="RELATED_TO",
                        label="RELATED_TO",
                    )
                )
            previous_entity_node_id = entity_node_id

    return list(node_map.values()), list(edge_map.values())


def build_permission_scoped_overview(
    db: Session,
    *,
    allowed_kb_ids: list[UUID],
    max_chunks: int = 220,
) -> tuple[list[GraphNodePublic], list[GraphEdgePublic], list[str]]:
    if not allowed_kb_ids:
        return [], [], ["No allowed knowledge base is available for this user."]

    chunk_rows = list(
        db.execute(
            select(DocumentChunk, Document, KnowledgeBase)
            .join(Document, Document.id == DocumentChunk.document_id)
            .join(KnowledgeBase, KnowledgeBase.id == DocumentChunk.knowledge_base_id)
            .where(DocumentChunk.knowledge_base_id.in_(allowed_kb_ids))
            .order_by(Document.created_at.desc(), DocumentChunk.ordinal.asc())
        ).all()
    )
    total_chunks = len(chunk_rows)
    limited_rows = chunk_rows[:max_chunks]
    nodes, edges = build_graph_elements_from_chunk_rows(
        limited_rows,
        include_chunk_preview=True,
    )
    notes = [
        "Graph overview only includes nodes and edges from backend RBAC allowed_kb_ids.",
        "Chunk node metadata contains preview only and never exposes full unauthorized content.",
    ]
    if total_chunks > len(limited_rows):
        notes.append(
            f"Graph overview is truncated to {len(limited_rows)} authorized chunks from {total_chunks} total chunks."
        )
    return nodes, edges, notes


def sync_neo4j_graph(db: Session) -> dict[str, Any]:
    return neo4j_service.sync_from_postgres(db)


def build_graph_paths_for_citations(
    db: Session,
    citations: list[Citation],
    allowed_kb_ids: list[UUID],
) -> list[GraphPath]:
    allowed_set = {str(kb_id) for kb_id in allowed_kb_ids}
    paths: list[GraphPath] = []
    for citation in citations[:4]:
        if str(citation.kb_id) not in allowed_set:
            continue

        graph_row = neo4j_service.query_chunk_graph(
            chunk_id=str(citation.chunk_id),
            allowed_kb_ids=list(allowed_set),
        )
        if graph_row is not None and graph_row.entities:
            path = [
                f"KB:{citation.kb_code}",
                f"DOC:{citation.document_title}",
                *[f"ENTITY:{name}" for name in graph_row.entities[:3]],
            ]
            explanation = "Authorized graph path from Neo4j entities."
            paths.append(GraphPath(chunk_id=citation.chunk_id, path=path, explanation=explanation))
            continue

        chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.id == citation.chunk_id))
        if chunk is None:
            continue
        entities = _chunk_entities(chunk)
        path = [
            f"KB:{citation.kb_code}",
            f"DOC:{citation.document_title}",
            *[f"ENTITY:{name}" for name in entities[:3]],
        ]
        explanation = "Authorized graph path from local entity projection."
        paths.append(GraphPath(chunk_id=citation.chunk_id, path=path, explanation=explanation))
    return paths


neo4j_service = Neo4jService()
