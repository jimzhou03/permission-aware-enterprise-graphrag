from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Department, DocumentChunk, KnowledgeBase
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

    def _driver_or_none(self):
        if self._disabled:
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

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:  # noqa: BLE001
                pass
            self._driver = None

    def sync_from_postgres(self, db: Session) -> None:
        driver = self._driver_or_none()
        if driver is None:
            return

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


def sync_neo4j_graph(db: Session) -> None:
    neo4j_service.sync_from_postgres(db)


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
