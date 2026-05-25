from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core import database as db_module
from app.models import KnowledgeBase
from app.services import rag_service
from app.services.rag_service import (
    RETRIEVAL_ENGINE_PGVECTOR_SQL,
    RETRIEVAL_ENGINE_PYTHON_FALLBACK,
    RetrievalRuntime,
    get_retrieval_runtime,
    retrieve_permission_scoped_chunks,
)


def test_sqlite_runtime_uses_python_fallback(client):
    db = db_module.SessionLocal()
    try:
        runtime = get_retrieval_runtime(db)
        assert runtime.retrieval_engine == RETRIEVAL_ENGINE_PYTHON_FALLBACK
        assert runtime.backend_name == "sqlite"
        assert runtime.sql_vector_search_enabled is False
        assert runtime.pgvector_available is False
    finally:
        db.close()


def test_postgresql_runtime_can_enable_pgvector_sql(monkeypatch):
    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    class _DummySession:
        def get_bind(self):
            return _Bind()

    monkeypatch.setattr(rag_service, "_probe_pgvector_available", lambda db: True)
    runtime = get_retrieval_runtime(_DummySession())  # type: ignore[arg-type]
    assert runtime.retrieval_engine == RETRIEVAL_ENGINE_PGVECTOR_SQL
    assert runtime.sql_vector_search_enabled is True


def test_pgvector_runtime_prefers_sql_path_when_enabled(monkeypatch, client):
    db = db_module.SessionLocal()
    try:
        kbs = list(
            db.scalars(
                select(KnowledgeBase).where(KnowledgeBase.code.in_(["cn-public", "cn-internal"]))
            ).all()
        )
        allowed_ids = [kb.id for kb in kbs]
        internal_kb = next(kb for kb in kbs if kb.code == "cn-internal")

        calls: dict[str, object] = {}

        def fake_sql(*, selected_ids, **kwargs):
            calls["sql_selected_ids"] = selected_ids
            return []

        def fake_python(**kwargs):
            calls["python_called"] = True
            return []

        monkeypatch.setattr(rag_service, "_retrieve_with_pgvector_sql", fake_sql)
        monkeypatch.setattr(rag_service, "_retrieve_with_python_cosine_fallback", fake_python)

        runtime = RetrievalRuntime(
            retrieval_engine=RETRIEVAL_ENGINE_PGVECTOR_SQL,
            pgvector_available=True,
            sql_vector_search_enabled=True,
            backend_name="postgresql",
        )
        retrieve_permission_scoped_chunks(
            db=db,
            question="test",
            allowed_kb_ids=allowed_ids,
            scoped_kb_codes=["cn-internal"],
            top_k=3,
            runtime=runtime,
        )

        assert calls.get("python_called") is None
        assert calls.get("sql_selected_ids") == {internal_kb.id}
    finally:
        db.close()


def test_pgvector_sql_failure_falls_back_to_python(monkeypatch, client):
    db = db_module.SessionLocal()
    try:
        kbs = list(
            db.scalars(
                select(KnowledgeBase).where(KnowledgeBase.code.in_(["cn-public", "cn-internal"]))
            ).all()
        )
        allowed_ids = [kb.id for kb in kbs]

        calls: dict[str, object] = {}

        def fake_sql(**kwargs):
            raise RuntimeError("pgvector unavailable")

        def fake_python(**kwargs):
            calls["python_called"] = True
            return []

        monkeypatch.setattr(rag_service, "_retrieve_with_pgvector_sql", fake_sql)
        monkeypatch.setattr(rag_service, "_retrieve_with_python_cosine_fallback", fake_python)

        runtime = RetrievalRuntime(
            retrieval_engine=RETRIEVAL_ENGINE_PGVECTOR_SQL,
            pgvector_available=True,
            sql_vector_search_enabled=True,
            backend_name="postgresql",
        )
        result = retrieve_permission_scoped_chunks(
            db=db,
            question="test",
            allowed_kb_ids=allowed_ids,
            scoped_kb_codes=[],
            top_k=3,
            runtime=runtime,
        )
        assert result == []
        assert calls.get("python_called") is True
    finally:
        db.close()


def test_pgvector_sql_statement_contains_kb_scope_filter(monkeypatch, client):
    db = db_module.SessionLocal()
    try:
        kbs = list(
            db.scalars(
                select(KnowledgeBase).where(KnowledgeBase.code.in_(["cn-public", "cn-internal"]))
            ).all()
        )
        kb_by_id = {kb.id: kb for kb in kbs}
        selected_ids = {kbs[0].id}
        captured: dict[str, str] = {}

        class _Result:
            def all(self):
                return []

        def fake_execute(statement):
            captured["sql"] = str(
                statement.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": False},
                )
            )
            return _Result()

        monkeypatch.setattr(db, "execute", fake_execute)
        rows = rag_service._retrieve_with_pgvector_sql(
            db=db,
            question="scope test",
            kb_by_id=kb_by_id,
            selected_ids=selected_ids,
            limit=2,
        )
        assert rows == []
        sql_text = captured.get("sql", "")
        assert "WHERE document_chunks.knowledge_base_id IN" in sql_text
        assert "ORDER BY" in sql_text
        assert "LIMIT" in sql_text
    finally:
        db.close()
