import pytest
from fastapi.testclient import TestClient
from airspace.storage import Store
from airspace.identity import provision
from airspace.api import create_app


@pytest.fixture
def environment(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'isolated-test.db'}", b"isolated-test-key-only-32-bytes-long")
    store.migrate()
    author = provision(store, "Isolated software test tenant", "author@test.invalid", "regulatory", "isolated-test-password")
    reviewer = provision(store, "Isolated software test tenant", "reviewer@test.invalid", "reviewer", "isolated-test-password", author["organisation_id"])
    other = provision(store, "Other isolated test tenant", "other@test.invalid", "regulatory", "isolated-test-password")
    client = TestClient(create_app(store, serve_frontend=False))
    def headers(email):
        response = client.post('/api/v1/session', json={"email":email,"password":"isolated-test-password"})
        assert response.status_code == 200
        return {"Authorization": "Bearer " + response.json()["token"]}
    yield store, client, author, reviewer, other, headers
    client.close()
    store.engine.dispose()
