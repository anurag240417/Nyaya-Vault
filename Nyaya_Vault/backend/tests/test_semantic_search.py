from __future__ import annotations

import app.services.casevault as casevault_module
import app.services.processor as processor_module
from tests.conftest import auth
from tests.test_api_end_to_end import create_case, make_pdf


def _seed_chunk_with_embedding(gateway, *, document_id, version_id, page_number, chunk_text, embedding, with_native_column=False):
    chunk = {
        "id": f"chunk-{page_number}-{document_id}", "document_version_id": version_id,
        "chunk_index": page_number, "page_number": page_number, "chunk_text": chunk_text,
    }
    gateway.tables["document_chunks"].append(chunk)
    embedding_row = {
        "document_chunk_id": chunk["id"], "model_name": "test-model", "embedding_json": embedding,
    }
    if with_native_column:
        embedding_row["embedding"] = "[" + ",".join(str(v) for v in embedding) + "]"
    gateway.tables["document_embeddings"].append(embedding_row)
    return chunk


def _upload_pdf(client, case_id, text="placeholder body text"):
    up = client.post(
        f"/api/v1/cases/{case_id}/documents", headers=auth("admin-token"),
        data={"title": "Evidence", "clearance_level": "RESTRICTED"},
        files={"file": ("e.pdf", make_pdf(text), "application/pdf")},
    ).json()
    return up["documentId"], up["versionId"]


def test_search_unaffected_when_semantic_disabled(client, gateway):
    """Default settings - the exact behavior that existed before this
    feature, just with the new matched_by/score fields added."""
    case = create_case(client)
    doc_id, version_id = _upload_pdf(client, case["id"])
    _seed_chunk_with_embedding(
        gateway, document_id=doc_id, version_id=version_id, page_number=1,
        chunk_text="the suspect fled the scene", embedding=[1.0, 0.0, 0.0],
    )

    r = client.get("/api/v1/search", headers=auth("admin-token"), params={"q": "fled"})
    assert r.status_code == 200, r.text
    results = r.json()
    assert len(results) == 1
    assert results[0]["matched_by"] == "keyword"
    assert "score" in results[0]

    audited = [a for a in gateway.tables["audit_logs"] if a["action"] == "SEARCH_PERFORMED"]
    assert audited[-1]["metadata"]["semantic_used"] is False


def test_semantic_fallback_surfaces_a_meaning_match_keyword_search_misses(client, gateway, monkeypatch):
    """No pgvector - pure-Python cosine_similarity fallback. Chunk A shares
    no words with the query but has the closest embedding; chunk B shares a
    literal word but points in a very different embedding direction.
    Keyword search alone would find only B; hybrid should surface both,
    with A tagged semantic and B tagged keyword."""
    service = client.app.state.casevault
    service.settings.enable_semantic_embeddings = True
    service.settings.enable_pgvector_search = False
    monkeypatch.setattr(casevault_module, "embed_texts", lambda texts, model: [[1.0, 0.0, 0.0]])

    case = create_case(client)
    doc_a, ver_a = _upload_pdf(client, case["id"])
    doc_b, ver_b = _upload_pdf(client, case["id"])
    _seed_chunk_with_embedding(
        gateway, document_id=doc_a, version_id=ver_a, page_number=1,
        chunk_text="the perpetrator escaped through the rear exit", embedding=[0.99, 0.01, 0.0],
    )
    _seed_chunk_with_embedding(
        gateway, document_id=doc_b, version_id=ver_b, page_number=1,
        chunk_text="fled the scene in a blue sedan", embedding=[0.0, 0.0, 1.0],
    )

    r = client.get("/api/v1/search", headers=auth("admin-token"), params={"q": "fled"})
    assert r.status_code == 200, r.text
    results = r.json()
    by_doc = {row["document_id"]: row for row in results}

    assert doc_b in by_doc and by_doc[doc_b]["matched_by"] == "keyword"
    assert doc_a in by_doc, "semantic-only match was dropped instead of merged in"
    assert by_doc[doc_a]["matched_by"] == "semantic"
    assert by_doc[doc_a]["similarity"] > 0.9

    audited = [a for a in gateway.tables["audit_logs"] if a["action"] == "SEARCH_PERFORMED"]
    assert audited[-1]["metadata"]["semantic_used"] is True


def test_hybrid_ranks_a_double_match_above_a_single_match(client, gateway, monkeypatch):
    service = client.app.state.casevault
    service.settings.enable_semantic_embeddings = True
    service.settings.enable_pgvector_search = False
    monkeypatch.setattr(casevault_module, "embed_texts", lambda texts, model: [[1.0, 0.0, 0.0]])

    case = create_case(client)
    doc_both, ver_both = _upload_pdf(client, case["id"])
    doc_keyword_only, ver_kw = _upload_pdf(client, case["id"])
    _seed_chunk_with_embedding(
        gateway, document_id=doc_both, version_id=ver_both, page_number=1,
        chunk_text="warrant executed at the residence", embedding=[0.98, 0.02, 0.0],
    )
    _seed_chunk_with_embedding(
        gateway, document_id=doc_keyword_only, version_id=ver_kw, page_number=1,
        chunk_text="warrant filed with the registry", embedding=[0.0, 1.0, 0.0],
    )

    r = client.get("/api/v1/search", headers=auth("admin-token"), params={"q": "warrant"})
    results = r.json()
    ranked_ids = [row["document_id"] for row in results]
    assert ranked_ids.index(doc_both) < ranked_ids.index(doc_keyword_only)
    assert [row for row in results if row["document_id"] == doc_both][0]["matched_by"] == "both"


def test_pgvector_path_ignores_rows_without_the_native_column(client, gateway, monkeypatch):
    """A chunk embedded before ENABLE_PGVECTOR_SEARCH was turned on has no
    native `embedding` value yet - the indexed pgvector query must not see
    it (mirrors `where de.embedding is not null` in the real SQL), even
    though the JSON fallback column is right there."""
    service = client.app.state.casevault
    service.settings.enable_semantic_embeddings = True
    service.settings.enable_pgvector_search = True
    monkeypatch.setattr(casevault_module, "embed_texts", lambda texts, model: [[1.0, 0.0, 0.0]])

    case = create_case(client)
    doc_id, version_id = _upload_pdf(client, case["id"])
    _seed_chunk_with_embedding(
        gateway, document_id=doc_id, version_id=version_id, page_number=1,
        chunk_text="unrelated text", embedding=[1.0, 0.0, 0.0], with_native_column=False,
    )

    r = client.get("/api/v1/search", headers=auth("admin-token"), params={"q": "nomatch"})
    results = r.json()
    assert results == []


def test_pgvector_path_finds_rows_with_the_native_column(client, gateway, monkeypatch):
    service = client.app.state.casevault
    service.settings.enable_semantic_embeddings = True
    service.settings.enable_pgvector_search = True
    monkeypatch.setattr(casevault_module, "embed_texts", lambda texts, model: [[1.0, 0.0, 0.0]])

    case = create_case(client)
    doc_id, version_id = _upload_pdf(client, case["id"])
    _seed_chunk_with_embedding(
        gateway, document_id=doc_id, version_id=version_id, page_number=1,
        chunk_text="unrelated text but same meaning", embedding=[0.97, 0.03, 0.0], with_native_column=True,
    )

    r = client.get("/api/v1/search", headers=auth("admin-token"), params={"q": "nomatch"})
    results = r.json()
    assert len(results) == 1
    assert results[0]["matched_by"] == "semantic"
    assert results[0]["similarity"] > 0.9


def test_search_respects_case_access_for_semantic_matches_too(client, gateway, monkeypatch):
    """A semantic-only hit in a case the caller cannot see must not leak
    through the merge step - the same access rule the keyword branch
    already enforces via p_case_ids."""
    service = client.app.state.casevault
    service.settings.enable_semantic_embeddings = True
    service.settings.enable_pgvector_search = False
    monkeypatch.setattr(casevault_module, "embed_texts", lambda texts, model: [[1.0, 0.0, 0.0]])

    other_case = create_case(client)  # admin-only, "io" is never assigned
    doc_id, version_id = _upload_pdf(client, other_case["id"])
    _seed_chunk_with_embedding(
        gateway, document_id=doc_id, version_id=version_id, page_number=1,
        chunk_text="nothing in common with the query", embedding=[1.0, 0.0, 0.0],
    )

    r = client.get("/api/v1/search", headers=auth("io-token"), params={"q": "nomatch"})
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_processor_writes_native_vector_column_when_pgvector_enabled(client, gateway, monkeypatch):
    service = client.app.state.casevault
    service.settings.enable_semantic_embeddings = True
    service.settings.enable_pgvector_search = True
    monkeypatch.setattr(processor_module, "embed_texts", lambda texts, model: [[0.1, 0.2, 0.3] for _ in texts])

    case = create_case(client)
    doc_id, version_id = _upload_pdf(client, case["id"], text="some real extractable body text for chunking")
    r = client.post(f"/api/v1/documents/{doc_id}/process", headers=auth("admin-token"), json={"version_id": version_id})
    assert r.status_code == 200, r.text

    embedding_rows = [e for e in gateway.tables["document_embeddings"]]
    assert embedding_rows, "processing produced no embedding rows to check"
    for row in embedding_rows:
        assert row["embedding"] == "[0.1,0.2,0.3]"


def test_processor_omits_native_column_when_pgvector_disabled(client, gateway, monkeypatch):
    service = client.app.state.casevault
    service.settings.enable_semantic_embeddings = True
    service.settings.enable_pgvector_search = False
    monkeypatch.setattr(processor_module, "embed_texts", lambda texts, model: [[0.1, 0.2, 0.3] for _ in texts])

    case = create_case(client)
    doc_id, version_id = _upload_pdf(client, case["id"], text="some real extractable body text for chunking")
    r = client.post(f"/api/v1/documents/{doc_id}/process", headers=auth("admin-token"), json={"version_id": version_id})
    assert r.status_code == 200, r.text

    embedding_rows = [e for e in gateway.tables["document_embeddings"]]
    assert embedding_rows, "processing produced no embedding rows to check"
    for row in embedding_rows:
        assert "embedding" not in row
