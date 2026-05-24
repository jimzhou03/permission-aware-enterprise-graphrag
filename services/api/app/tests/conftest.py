from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core import database as db_module


@pytest.fixture()
def client():
    test_db_path = Path(f"test_phase1_{uuid4().hex}.db")
    test_database_url = f"sqlite+pysqlite:///{test_db_path.as_posix()}"

    db_module.rebind_database(test_database_url)
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    db_module.engine.dispose()
    test_db_path.unlink(missing_ok=True)
