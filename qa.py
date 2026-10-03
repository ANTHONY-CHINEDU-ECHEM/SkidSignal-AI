"""Grounded question answering over the knowledge base."""
from __future__ import annotations

from skidsignal.config import Settings
from skidsignal.index.store import HybridIndex
from skidsignal.rag import prompts
from skidsignal.rag.evidence import snippet
from skidsignal.rag.guardrails import citations


def answer_question(index: HybridIndex, question: str, cfg: Settings, llm=None, k: int = 6, **filters) -> dict:
    hits = index.search(question, k=k, **filters)
    if not hits:
        return {"question": question, "answer": "The knowledge base holds no records that match this question and these filters.",
                "citations": [], "hits": [], "writer": "extractive"}
    valid = {h.doc_id for h in hits}
    answer, writer = None, "extractive"
    if llm is not None:
        try:
            draft = llm.complete(prompts.QA_SYSTEM_PROMPT, prompts.qa_prompt(question, hits))
            used = citations(draft)
            if used and set(used) <= valid:
                answer, writer = draft.strip(), llm.name
            else:
                writer = "extractive (fallback, draft had missing or invalid citations)"
        except Exception as exc:
            writer = f"extractive (fallback, {type(exc).__name__})"
    if answer is None:
        lines = [f"The {len(hits)} most relevant records are listed below. Owner complaints are unverified reports."]
        lines += [f"- [{h.doc_id}] {h.title}: {snippet(h.text, 300)}" for h in hits]
        answer = "\n".join(lines)
    return {"question": question, "answer": answer, "citations": sorted(set(citations(answer))),
            "hits": [h.to_dict() for h in hits], "writer": writer}
