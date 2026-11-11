"""Tests de l'API HTTP (FastAPI) sur le mini-index de conftest.py."""
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_library


@pytest.fixture
def client(lib):
    app.dependency_overrides[get_library] = lambda: lib
    yield TestClient(app)
    app.dependency_overrides.clear()


def ids(response):
    return [b["id"] for b in response.json()["results"]]


def test_stats(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert r.json()["books"] == 3 and r.json()["terms"] > 0


def test_search(client):
    r = client.get("/api/search", params={"q": "whale"})
    assert r.status_code == 200
    assert ids(r) == [1, 3]


def test_search_substring(client):
    r = client.get("/api/search", params={"q": "lov", "mode": "substring"})
    assert ids(r) == [2]


def test_advanced(client):
    r = client.get("/api/advanced", params={"regex": "wh(a|e)+l"})
    assert r.status_code == 200
    assert ids(r) == [1, 3]


def test_invalid_regex_gives_400(client):
    r = client.get("/api/advanced", params={"regex": "a(b"})
    assert r.status_code == 400
    assert "Regex invalide" in r.json()["detail"]


def test_empty_query_gives_400(client):
    assert client.get("/api/search", params={"q": " "}).status_code == 400


def test_bad_parameters_give_422(client):
    assert client.get("/api/search").status_code == 422
    assert client.get("/api/search", params={"q": "x", "limit": 0}).status_code == 422
    assert client.get("/api/search", params={"q": "x", "mode": "regex"}).status_code == 422 