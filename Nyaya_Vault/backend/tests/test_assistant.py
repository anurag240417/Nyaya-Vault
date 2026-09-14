from __future__ import annotations

from tests.conftest import auth
from tests.test_api_end_to_end import create_case, make_pdf


class FakeLlmClient:
    """Records every call instead of hitting a real API - lets tests assert
    exactly what context was actually sent to the model, and never depends
    on a real ANTHROPIC_API_KEY or network access to pass."""

    def __init__(self, response: str = "stub answer"):
        self.response = response
        self.calls: list[dict] = []

    async def complete(self, *, system: str, user_message: str, max_tokens: int = 1500) -> str:
        self.calls.append({"system": system, "user_message": user_message, "max_tokens": max_tokens})
        return self.response


def install_fake_llm(client, response: str = "stub answer") -> FakeLlmClient:
    fake = FakeLlmClient(response)
    client.app.state.assistant.llm = fake
    return fake


def test_ask_requires_case_access(client):
    case = create_case(client)
    install_fake_llm(client)
    denied = client.post(
        f"/api/v1/cases/{case['id']}/assistant/ask", headers=auth("otherio-token"),
        json={"question": "who is involved?"},
    )
    assert denied.status_code == 403


def test_ask_grounds_answer_in_case_context_and_is_audited(client, gateway):
    case = create_case(client)
    fake = install_fake_llm(client, response="Based on the FIR, X was present.")
    r = client.post(
        f"/api/v1/cases/{case['id']}/assistant/ask", headers=auth("admin-token"),
        json={"question": "Who was involved?"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["answer"] == "Based on the FIR, X was present."

    assert len(fake.calls) == 1
    assert case["case_number"] in fake.calls[0]["user_message"]
    assert "Who was involved?" in fake.calls[0]["user_message"]
    assert "ONLY" in fake.calls[0]["system"]  # the grounding rule must actually be present

    actions = [a["action"] for a in gateway.tables["audit_logs"] if a["case_id"] == case["id"]]
    assert "AI_ASSISTANT_QUESTION_ASKED" in actions


def test_ask_rejects_empty_question(client):
    case = create_case(client)
    install_fake_llm(client)
    r = client.post(
        f"/api/v1/cases/{case['id']}/assistant/ask", headers=auth("admin-token"),
        json={"question": "   "},
    )
    assert r.status_code == 409


def test_summary_and_legal_sections_use_the_llm_and_are_audited(client, gateway):
    case = create_case(client)
    fake = install_fake_llm(client, response="stubbed output")

    summary = client.post(f"/api/v1/cases/{case['id']}/assistant/summary", headers=auth("admin-token"))
    assert summary.status_code == 200, summary.text
    assert summary.json()["summary"] == "stubbed output"

    legal = client.post(f"/api/v1/cases/{case['id']}/assistant/legal-sections", headers=auth("admin-token"))
    assert legal.status_code == 200, legal.text
    assert legal.json()["suggestion"] == "stubbed output"
    # The legal-sections call must carry the extra hedging instructions -
    # this is the higher-risk feature and must never drop that framing.
    assert "PRELIMINARY" in fake.calls[-1]["system"]
    assert "BNS" in fake.calls[-1]["system"]

    actions = [a["action"] for a in gateway.tables["audit_logs"] if a["case_id"] == case["id"]]
    assert "AI_ASSISTANT_SUMMARY_GENERATED" in actions
    assert "AI_ASSISTANT_LEGAL_SECTIONS_SUGGESTED" in actions


def test_context_excludes_documents_above_users_clearance(client, gateway):
    """The critical security property: a PUBLIC-clearance collaborator
    asking the assistant a question must not have SECRET-clearance document
    content included in what actually gets sent to the model - the
    assistant must not become a side channel around clearance checks."""
    case = create_case(client)
    pdf = make_pdf("classified informant details")

    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Classified Informant Report", "document_type": "REPORT", "clearance_level": "SECRET"},
        files={"file": ("secret.pdf", pdf, "application/pdf")},
    )
    assert up.status_code == 200, up.text

    clerk_id = next(p["id"] for p in gateway.tables["profiles"] if p["username"] == "clerk")
    add = client.post(
        f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"),
        json={"user_id": clerk_id},
    )
    assert add.status_code == 200, add.text

    fake = install_fake_llm(client, response="stub")
    r = client.post(
        f"/api/v1/cases/{case['id']}/assistant/ask", headers=auth("clerk-token"),
        json={"question": "What's in the informant report?"},
    )
    assert r.status_code == 200, r.text
    assert "Classified Informant Report" not in fake.calls[0]["user_message"]
    assert "no documents visible" in fake.calls[0]["user_message"]

    # Sanity check: the same question from the ADMIN (SECRET clearance)
    # DOES include it - proves the exclusion above is about clearance,
    # not a bug that hides the document from everyone.
    fake2 = install_fake_llm(client, response="stub")
    r2 = client.post(
        f"/api/v1/cases/{case['id']}/assistant/ask", headers=auth("admin-token"),
        json={"question": "What's in the informant report?"},
    )
    assert r2.status_code == 200
    assert "Classified Informant Report" in fake2.calls[0]["user_message"]


def test_gaps_flags_missing_evidence_without_calling_the_llm(client, gateway):
    case = create_case(client)
    fake = install_fake_llm(client, response="should never be called")

    gaps = client.get(f"/api/v1/cases/{case['id']}/assistant/gaps", headers=auth("admin-token"))
    assert gaps.status_code == 200, gaps.text
    messages = [g["message"] for g in gaps.json()]
    assert any("No evidence documents" in m for m in messages)
    # With zero documents at all, the FIR/chargesheet-specific messages are
    # redundant with the message above and correctly don't also fire.
    assert not any("FIR has been uploaded" in m for m in messages)

    # The whole point of this feature: zero LLM calls, ever.
    assert fake.calls == []


def test_gaps_flags_missing_fir_specifically_when_other_evidence_exists(client, gateway):
    case = create_case(client)
    pdf = make_pdf("a witness statement, not a FIR")
    r = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Witness Statement", "document_type": "STATEMENT", "clearance_level": "PUBLIC"},
        files={"file": ("statement.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200, r.text

    gaps = client.get(f"/api/v1/cases/{case['id']}/assistant/gaps", headers=auth("admin-token")).json()
    messages = [g["message"] for g in gaps]
    assert not any("No evidence documents" in m for m in messages)
    assert any("No FIR has been uploaded" in m for m in messages)
    assert any("chargesheet has been uploaded" in m for m in messages)


def test_gaps_clears_once_fir_and_chargesheet_exist(client, gateway):
    case = create_case(client)
    pdf = make_pdf("evidence text")
    for doc_type, title in [("FIR", "FIR 1"), ("CHARGESHEET", "Chargesheet 1")]:
        r = client.post(
            f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
            data={"title": title, "document_type": doc_type, "clearance_level": "PUBLIC"},
            files={"file": (f"{doc_type}.pdf", pdf, "application/pdf")},
        )
        assert r.status_code == 200, r.text

    gaps = client.get(f"/api/v1/cases/{case['id']}/assistant/gaps", headers=auth("admin-token")).json()
    messages = [g["message"] for g in gaps]
    assert not any("FIR has been uploaded" in m for m in messages)
    assert not any("chargesheet has been uploaded" in m for m in messages)
    assert not any("No evidence documents" in m for m in messages)


def test_assistant_returns_clear_error_when_not_configured(client):
    """If someone hits these routes on a deployment that never set an API
    key for either provider, they should get one clear, actionable error -
    not a 500 or a silent no-op."""
    case = create_case(client)
    # Don't install a fake - use the real default client with no key set.
    r = client.post(f"/api/v1/cases/{case['id']}/assistant/ask", headers=auth("admin-token"), json={"question": "test"})
    assert r.status_code == 409
    assert r.json()["details"]["reason"] == "AI_ASSISTANT_NOT_CONFIGURED"
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_default_llm_client_prefers_openai_when_both_keys_are_set():
    from app.core.config import Settings
    from app.services.assistant import AnthropicLlmClient, OpenAiLlmClient, _default_llm_client

    both = Settings(
        supabase_url="http://fake.invalid", supabase_anon_key="anon", supabase_service_role_key="service",
        openai_api_key="sk-test", anthropic_api_key="sk-ant-test",
    )
    assert isinstance(_default_llm_client(both), OpenAiLlmClient)

    anthropic_only = Settings(
        supabase_url="http://fake.invalid", supabase_anon_key="anon", supabase_service_role_key="service",
        openai_api_key=None, anthropic_api_key="sk-ant-test",
    )
    assert isinstance(_default_llm_client(anthropic_only), AnthropicLlmClient)

    neither = Settings(
        supabase_url="http://fake.invalid", supabase_anon_key="anon", supabase_service_role_key="service",
        openai_api_key=None, anthropic_api_key=None,
    )
    assert isinstance(_default_llm_client(neither), OpenAiLlmClient)