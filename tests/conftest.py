import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=str(tmp_path / "test.db"), root_path="")


@pytest.fixture
def client(app):
    with TestClient(app, follow_redirects=False) as c:
        yield c
