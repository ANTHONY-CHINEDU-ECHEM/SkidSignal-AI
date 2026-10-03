"""Prompt templates for the optional language model writer."""
from __future__ import annotations

import json

from skidsignal.rag.evidence import EvidencePack

SYSTEM_PROMPT = """You are a vehicle safety data analyst writing an internal brief about a possible \
emerging antilock brake system (ABS) defect signal. You write for defect investigators.

Rules you must follow without exception:
1. Use only the FACTS and EVIDENCE provided. Do not use outside knowledge about the vehicle.
2. End every factual sentence with at least one citation in square brackets. Use [S] for the \
computed statistics in FACTS, and the exact key of an evidence item, for example [C:11633014] \
or [R:23V651], for anything taken from a record. Never invent a citation key.
3. Copy numbers exactly as they appear in FACTS or in an evidence item. Do not calculate, round, \
or estimate new numbers. If you need a number that is not provided, leave it out.
4. Owner complaints are unverified allegations. Use calibrated language such as "is consistent \
with", "suggests", "owners report". Never state that a defect is confirmed or proven, and never \
say a recall is required.
5. If the evidence is thin or mixed, say so plainly.

Return a single JSON object and nothing else, with these keys:
  "summary": 3 to 4 sentences on what the statistics show.
  "failure_modes": 3 to 5 sentences on what owners describe, quoting or paraphrasing cited complaints.
  "context": 2 to 4 sentences on existing recalls for this family and related campaigns.
  "assessment": 3 to 4 sentences weighing the signal, its severity and its limits.
  "actions": a list of 3 to 5 short recommended next steps for an analyst."""


def evidence_block(pack: EvidencePack) -> str:
    lines = ["FACTS (cite as [S]):"] + [f"- {line}" for line in pack.fact_lines] + ["", "EVIDENCE:"]
    for item in pack.items:
        date = f", {item.date}" if item.date else ""
        lines.append(f"[{item.cite}] ({item.source}, {item.role}{date}) {item.title}: {item.text}")
    return "\n".join(lines)


def brief_prompt(pack: EvidencePack, issues: list[str] | None = None, previous: dict | None = None) -> str:
    prompt = f"Write the brief for vehicle family {pack.vehicle} as of {pack.as_of}.\n\n{evidence_block(pack)}"
    if issues:
        prompt += (
            "\n\nYour previous draft failed automated checks. Fix every issue and return the full JSON again.\n"
            "Issues:\n" + "\n".join(f"- {i}" for i in issues) + "\n\nPrevious draft:\n" + json.dumps(previous, indent=2)
        )
    return prompt


QA_SYSTEM_PROMPT = """You answer questions about antilock brake safety records using only the \
passages provided. Cite the key of every passage you rely on in square brackets, for example \
[C:11633014]. Copy numbers exactly. Owner complaints are unverified allegations, so describe them \
as reports. If the passages do not answer the question, say that the knowledge base does not \
contain enough evidence. Answer in at most six sentences."""


def qa_prompt(question: str, hits: list) -> str:
    passages = "\n".join(f"[{h.doc_id}] {h.title}: {h.text}" for h in hits)
    return f"Question: {question}\n\nPassages:\n{passages}"
