from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.core.models import CurrentUser
from app.integrations.supabase import SupabaseGateway
from app.services.authorization import AuthorizationService
from app.services.casevault import CaseVaultService, _singleton_type_key
from app.services.timeline import TimelineService

# Hard cap on how many documents feed into a single assistant call. This is
# investigative support for one case at a time, not a document dump - a
# smaller, curated context is also easier for the model to stay faithful to,
# which matters given the grounding rule below.
_MAX_DOCUMENTS_IN_CONTEXT = 12


class LlmClient(Protocol):
    async def complete(self, *, system: str, user_message: str, max_tokens: int = 1500) -> str: ...


class OpenAiLlmClient:
    """Thin wrapper over OpenAI's Chat Completions API. Same LlmClient shape
    as AnthropicLlmClient - the rest of AssistantService (grounding rule,
    context building, clearance filtering) doesn't know or care which
    provider is behind this interface."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(self, *, system: str, user_message: str, max_tokens: int = 1500) -> str:
        if not self.settings.openai_api_key:
            raise ConflictError(
                "AI assistant is not configured on this server - set OPENAI_API_KEY.",
                details={"reason": "AI_ASSISTANT_NOT_CONFIGURED"},
            )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self.settings.openai_model,
                    "max_completion_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                },
            )
        if response.status_code != 200:
            raise ConflictError(f"AI assistant request failed (HTTP {response.status_code}). Try again shortly.")
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ConflictError("AI assistant returned no response. Try again shortly.")
        return choices[0].get("message", {}).get("content", "") or ""


def _default_llm_client(settings: Settings) -> LlmClient:
    """OpenAI first if configured, falling back to Anthropic if only that
    key is set. If neither is set, defaults to OpenAiLlmClient so the error
    message names the key that's actually meant to be configured now -
    swap this one function if the primary provider changes again later."""
    if settings.openai_api_key:
        return OpenAiLlmClient(settings)
    if settings.anthropic_api_key:
        return AnthropicLlmClient(settings)
    return OpenAiLlmClient(settings)


class AnthropicLlmClient:
    """Thin wrapper over the Anthropic Messages API. Kept as its own class,
    separate from AssistantService, specifically so tests can inject a fake
    implementation instead of making real network calls or needing a real
    API key - see tests/test_assistant.py."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(self, *, system: str, user_message: str, max_tokens: int = 1500) -> str:
        if not self.settings.anthropic_api_key:
            raise ConflictError(
                "AI assistant is not configured on this server - set ANTHROPIC_API_KEY.",
                details={"reason": "AI_ASSISTANT_NOT_CONFIGURED"},
            )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.settings.anthropic_model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
        if response.status_code != 200:
            raise ConflictError(f"AI assistant request failed (HTTP {response.status_code}). Try again shortly.")
        data = response.json()
        return "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")


# The single grounding rule every assistant call shares. This is what keeps
# "AI assistance" from becoming a hallucination risk in a legal tool: it can
# only speak from the case's own confirmed data, must say so when it can't
# answer, and must cite what it's drawing from. Never relaxed per-feature.
_GROUNDING_RULE = (
    "You are assisting a police officer or investigator working one specific case in a legal "
    "case-management system. You may ONLY use the CASE CONTEXT provided in the user message - "
    "never use outside knowledge about any named person, place, or this case, and never invent "
    "a fact that is not explicitly present in the context. If the answer is not contained in the "
    "context, say so plainly rather than guessing or filling the gap. Every factual claim you "
    "make must reference which document, entity, or statement in the context it comes from. "
    "You are investigative support, not a legal or factual authority - a human must independently "
    "verify anything you say before it is relied on or acted upon."
)


class AssistantService:
    def __init__(
        self,
        gateway: SupabaseGateway,
        settings: Settings,
        casevault: CaseVaultService,
        timeline: TimelineService,
        llm_client: LlmClient | None = None,
    ) -> None:
        self.gateway = gateway
        self.settings = settings
        self.casevault = casevault
        self.timeline = timeline
        self.authz = AuthorizationService(gateway)
        self.llm = llm_client or _default_llm_client(settings)

    async def _build_case_context(self, user: CurrentUser, case_id: str) -> dict[str, Any]:
        """Everything gathered here is already scoped to what THIS user is
        allowed to see: clearance-filtered documents (list_case_documents
        already does this), only CONFIRMED entities (never raw/unreviewed
        extraction), only CONFIRMED timeline statements. The assistant must
        never become a side channel for reading evidence a user's clearance
        already blocks them from seeing directly - see
        test_context_excludes_documents_above_users_clearance.
        """
        case = await self.authz.require_case_access(user, case_id)
        documents = (await self.casevault.list_case_documents(user, case_id))[:_MAX_DOCUMENTS_IN_CONTEXT]

        version_ids: list[str] = []
        doc_title_by_version: dict[str, str] = {}
        for doc in documents:
            versions = await self.gateway.service_table(
                "GET", "document_versions",
                params={
                    "document_id": f"eq.{doc['id']}",
                    "version_number": f"eq.{doc['current_version_number']}",
                    "select": "id",
                },
            ) or []
            if versions:
                version_ids.append(versions[0]["id"])
                doc_title_by_version[versions[0]["id"]] = doc["title"]

        entities: list[dict[str, Any]] = []
        if version_ids:
            entities = await self.gateway.service_table(
                "GET", "document_entities",
                params={
                    "document_version_id": f"in.({','.join(version_ids)})",
                    "confirmed": "eq.true", "select": "*",
                },
            ) or []

        collaborators = await self.casevault.list_collaborators(user, case_id)
        statements = await self.timeline.list_statements(user, case_id)
        confirmed_statements = [s for s in statements if s["status"] == "CONFIRMED"]
        suggested_statements = [s for s in statements if s["status"] == "SUGGESTED"]
        conflicts = await self.timeline.list_conflicts(user, case_id)
        open_conflicts = [c for c in conflicts if c["status"] == "OPEN"]
        audit = await self.casevault.case_audit(user, case_id)

        return {
            "case": case,
            "documents": documents,
            "entities": entities,
            "doc_title_by_version": doc_title_by_version,
            "collaborators": collaborators,
            "confirmed_statements": confirmed_statements,
            "suggested_statements": suggested_statements,
            "open_conflicts": open_conflicts,
            "audit": audit,
        }

    def _render_context(self, ctx: dict[str, Any]) -> str:
        case = ctx["case"]
        lines = [
            f"CASE: {case.get('case_number')} - {case.get('title')}",
            f"Description: {case.get('description') or 'None provided.'}",
            "",
            "DOCUMENTS (already limited to this user's clearance level):",
        ]
        for d in ctx["documents"]:
            lines.append(
                f"- \"{d['title']}\" (type: {d.get('document_type') or 'unclassified'}, "
                f"clearance: {d['clearance_level']}, current version: v{d['current_version_number']})"
            )
        if not ctx["documents"]:
            lines.append("- (no documents visible to this user on this case)")

        lines.append("")
        lines.append("CONFIRMED EXTRACTED FACTS (human-verified, grouped by source document):")
        by_doc: dict[str, list[str]] = {}
        for e in ctx["entities"]:
            title = ctx["doc_title_by_version"].get(e["document_version_id"], "Unknown document")
            by_doc.setdefault(title, []).append(f"{e['entity_type']}: {e['value']}")
        for title, facts in by_doc.items():
            lines.append(f"- In \"{title}\": " + "; ".join(facts))
        if not by_doc:
            lines.append("- (no confirmed entities yet)")

        lines.append("")
        lines.append("CONFIRMED TIMELINE STATEMENTS (person, location, time window):")
        for s in ctx["confirmed_statements"]:
            lines.append(
                f"- {s['person_name']} at {s['location_name']}, {s['window_start']} to {s['window_end']} "
                f"(source: {s.get('source_excerpt') or 'manually entered by an investigator'})"
            )
        if not ctx["confirmed_statements"]:
            lines.append("- (none confirmed yet)")

        lines.append("")
        lines.append("OPEN CONTRADICTIONS DETECTED BY THE TIMELINE SOLVER:")
        for c in ctx["open_conflicts"]:
            lines.append(f"- Concerning {c['person_name']}: statements {c['statement_ids']} cannot all be true simultaneously.")
        if not ctx["open_conflicts"]:
            lines.append("- (none currently open)")

        lines.append("")
        lines.append("COLLABORATORS WITH ACCESS TO THIS CASE:")
        for c in ctx["collaborators"]:
            lines.append(f"- {c['username']} ({c['role']})")

        lines.append("")
        lines.append(f"AUDIT LOG: {len(ctx['audit'])} recorded events on this case.")
        return "\n".join(lines)

    async def ask(self, user: CurrentUser, case_id: str, question: str) -> dict[str, Any]:
        if not question or not question.strip():
            raise ConflictError("Ask a question first.")
        ctx = await self._build_case_context(user, case_id)
        context_text = self._render_context(ctx)
        answer = await self.llm.complete(
            system=_GROUNDING_RULE,
            user_message=f"CASE CONTEXT:\n{context_text}\n\nOFFICER'S QUESTION:\n{question.strip()}",
        )
        await self.gateway.append_audit_service(
            actor_user_id=user.id, case_id=case_id, document_id=None,
            action="AI_ASSISTANT_QUESTION_ASKED", metadata={"question": question.strip()[:200]},
        )
        return {"answer": answer}

    async def summarize(self, user: CurrentUser, case_id: str) -> dict[str, Any]:
        ctx = await self._build_case_context(user, case_id)
        context_text = self._render_context(ctx)
        summary = await self.llm.complete(
            system=_GROUNDING_RULE,
            user_message=(
                f"CASE CONTEXT:\n{context_text}\n\n"
                "Write a structured investigative briefing from the above, for a senior officer "
                "who has not yet reviewed this case. Cover, as plain section headings: Background, "
                "Key people and locations, Timeline of confirmed events, Evidence collected, Open "
                "contradictions needing resolution, and What appears to still be missing. Do not "
                "invent any detail not present in the context above."
            ),
            max_tokens=2000,
        )
        await self.gateway.append_audit_service(
            actor_user_id=user.id, case_id=case_id, document_id=None,
            action="AI_ASSISTANT_SUMMARY_GENERATED", metadata={},
        )
        return {"summary": summary}

    async def suggest_legal_sections(self, user: CurrentUser, case_id: str) -> dict[str, Any]:
        ctx = await self._build_case_context(user, case_id)
        context_text = self._render_context(ctx)
        suggestion = await self.llm.complete(
            system=_GROUNDING_RULE + (
                " When asked about applicable law, you are providing a PRELIMINARY, "
                "NON-AUTHORITATIVE starting point for a qualified legal officer to "
                "independently verify against the current statute. Never state with certainty "
                "that a section applies - always hedge as 'may be relevant, subject to "
                "verification by a legal officer'. Note that India's Bharatiya Nyaya Sanhita "
                "(BNS) replaced the Indian Penal Code (IPC) in 2023 - refer to BNS sections as "
                "current unless the case context itself references IPC."
            ),
            user_message=(
                f"CASE CONTEXT:\n{context_text}\n\n"
                "Based only on the facts above, list which categories of offence and which BNS "
                "(Bharatiya Nyaya Sanhita) sections may be relevant for a legal officer to review, "
                "with a one-line reason for each grounded in the case context. Explicitly say so "
                "if there isn't yet enough information to suggest anything meaningful."
            ),
            max_tokens=1200,
        )
        await self.gateway.append_audit_service(
            actor_user_id=user.id, case_id=case_id, document_id=None,
            action="AI_ASSISTANT_LEGAL_SECTIONS_SUGGESTED", metadata={},
        )
        return {"suggestion": suggestion}

    async def check_gaps(self, user: CurrentUser, case_id: str) -> list[dict[str, Any]]:
        """Deliberately NOT an LLM call. Missing-FIR, unresolved conflicts,
        and pending reviews are exact, computable facts already sitting in
        the database - running them through a model would trade perfect
        reliability for hallucination risk with no upside."""
        ctx = await self._build_case_context(user, case_id)
        gaps: list[dict[str, Any]] = []

        if not ctx["documents"]:
            gaps.append({"severity": "HIGH", "message": "No evidence documents have been uploaded to this case yet."})
        else:
            doc_types = {_singleton_type_key(d.get("document_type")) for d in ctx["documents"]}
            if "FIR" not in doc_types:
                gaps.append({"severity": "HIGH", "message": "No FIR has been uploaded for this case yet."})
            if "CHARGESHEET" not in doc_types:
                gaps.append({"severity": "MEDIUM", "message": "No chargesheet has been uploaded for this case yet."})

        if ctx["open_conflicts"]:
            gaps.append({
                "severity": "HIGH",
                "message": f"{len(ctx['open_conflicts'])} unresolved contradiction(s) in the timeline - review the Conflicts tab.",
            })

        if ctx["suggested_statements"]:
            gaps.append({
                "severity": "LOW",
                "message": f"{len(ctx['suggested_statements'])} auto-suggested timeline statement(s) awaiting confirmation.",
            })

        if len(ctx["collaborators"]) <= 1:
            gaps.append({
                "severity": "LOW",
                "message": "Only one person has access to this case - consider assigning a collaborator for review.",
            })

        return gaps