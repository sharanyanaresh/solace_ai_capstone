"""Tests for query endpoints with a mocked pipeline."""
from __future__ import annotations

from unittest.mock import patch

MOCK_PIPELINE_RESULT = {
    "retrieval_mode": "hybrid",
    "reasoning_mode": "graph",
    "flags": [],
    "overall": "moderate",
    "claims": [
        {
            "claim_text": "Test claim about metformin.",
            "evidence_strength": "moderate",
            "consensus_label": "consensus",
            "is_abstention": False,
            "order_idx": 0,
            "citations": [
                {
                    "source_ref": "PMID:12345",
                    "source_type": "pubmed",
                    "title": "Test Paper",
                    "journal": "Test Journal",
                    "snippet": "A test snippet.",
                    "relevance": 85,
                    "contested": False,
                }
            ],
            "provenance": {
                "agent_id": "fact_checker",
                "prompt_version": "v1",
                "model_id": "llama-3.3-70b-versatile",
                "retrieval_pass": 1,
            },
        }
    ],
    "narrative_md": "Metformin shows moderate evidence.",
    "explanation_md": "## Overview\nDetailed explanation here.",
    "stage_logs": [
        {"stage_no": "1", "agent_id": "researcher", "model_id": "llama-3.1-8b-instant",
         "latency_ms": 500, "tokens": 200, "status": "ok"},
    ],
}


@patch("backend.app.routers.queries.run_pipeline", return_value=MOCK_PIPELINE_RESULT)
def test_submit_query(mock_pipe, auth_header):
    client, headers = auth_header
    res = client.post("/api/v1/queries", json={"query": "Does metformin reduce cancer?"}, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "completed"
    assert data["narrative_md"] == "Metformin shows moderate evidence."
    assert len(data["claims"]) == 1
    assert len(data["citations"]) == 1
    mock_pipe.assert_called_once()


@patch("backend.app.routers.queries.run_pipeline", return_value=MOCK_PIPELINE_RESULT)
def test_list_queries(mock_pipe, auth_header):
    client, headers = auth_header
    client.post("/api/v1/queries", json={"query": "Test question one here"}, headers=headers)
    client.post("/api/v1/queries", json={"query": "Test question two here"}, headers=headers)
    res = client.get("/api/v1/queries", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 2


@patch("backend.app.routers.queries.run_pipeline", return_value=MOCK_PIPELINE_RESULT)
def test_get_query_by_id(mock_pipe, auth_header):
    client, headers = auth_header
    create = client.post("/api/v1/queries", json={"query": "Test query for fetch"}, headers=headers)
    qid = create.json()["query_id"]
    res = client.get(f"/api/v1/queries/{qid}", headers=headers)
    assert res.status_code == 200
    assert res.json()["query_id"] == qid


@patch("backend.app.routers.queries.run_pipeline", return_value=MOCK_PIPELINE_RESULT)
def test_query_ownership(mock_pipe, client, db_session):
    """A second user cannot see the first user's query."""
    # register two users
    r1 = client.post("/api/v1/auth/register", json={"email": "u1@test.com", "password": "password123"})
    r2 = client.post("/api/v1/auth/register", json={"email": "u2@test.com", "password": "password123"})
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    create = client.post("/api/v1/queries", json={"query": "Private query test!"}, headers=h1)
    qid = create.json()["query_id"]

    # user 2 should get 404
    res = client.get(f"/api/v1/queries/{qid}", headers=h2)
    assert res.status_code == 404


def test_submit_query_unauthenticated(client):
    res = client.post("/api/v1/queries", json={"query": "Should fail without auth"})
    assert res.status_code == 401


def test_submit_query_too_short(auth_header):
    client, headers = auth_header
    res = client.post("/api/v1/queries", json={"query": "Hi"}, headers=headers)
    assert res.status_code == 422


@patch("backend.app.routers.queries.run_pipeline", return_value=MOCK_PIPELINE_RESULT)
def test_export_markdown(mock_pipe, auth_header):
    client, headers = auth_header
    create = client.post("/api/v1/queries", json={"query": "Export test query here"}, headers=headers)
    qid = create.json()["query_id"]
    res = client.get(f"/api/v1/queries/{qid}/export?format=md", headers=headers)
    assert res.status_code == 200
    assert "Solace AI" in res.text


@patch("backend.app.routers.queries.run_pipeline", return_value=MOCK_PIPELINE_RESULT)
def test_export_pdf(mock_pipe, auth_header):
    client, headers = auth_header
    create = client.post("/api/v1/queries", json={"query": "PDF export test query"}, headers=headers)
    qid = create.json()["query_id"]
    res = client.get(f"/api/v1/queries/{qid}/export?format=pdf", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 100
