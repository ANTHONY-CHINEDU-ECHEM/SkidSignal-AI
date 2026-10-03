"""Mutation tests for the guardrails.

A clean brief is generated for every flagged vehicle family, then four kinds of fault
are injected into its narrative. A guardrail earns trust only if clean briefs pass and
every injected fault is caught for the right reason.
"""
from __future__ import annotations

import json
import re

from skidsignal.config import get_logger
from skidsignal.rag.guardrails import CITE_RE, check_narrative

log = get_logger(__name__)


def _fabricated_citation(n: dict) -> dict:
    return {**n, "summary": n["summary"] + " A further owner report describes the same fault [C:99999999]."}


def _altered_number(n: dict) -> dict:
    return {**n, "summary": re.sub(r"\d[\d,]* of its", "987,654 of its", n["summary"], count=1)}


def _overstatement(n: dict) -> dict:
    return {**n, "assessment": n["assessment"] + " This proves the ABS module is defective [S]."}


def _citations_removed(n: dict) -> dict:
    return {**n, "summary": CITE_RE.sub("", n["summary"]), "failure_modes": CITE_RE.sub("", n["failure_modes"])}


MUTATIONS = {
    "fabricated_citation": (_fabricated_citation, lambda r: bool(r.invalid_citations)),
    "altered_number": (_altered_number, lambda r: bool(r.unsupported_numbers)),
    "overstatement": (_overstatement, lambda r: bool(r.overstatement_hits)),
    "citations_removed": (_citations_removed, lambda r: r.citation_coverage < 0.9),
}


def evaluate_guardrails(engine, max_vehicles: int = 40) -> dict:
    vehicles = engine.signals()["vehicle"].head(max_vehicles).tolist()
    clean_pass, caught = 0, {name: 0 for name in MUTATIONS}
    for vehicle in vehicles:
        brief = engine.brief(vehicle, use_llm=False)
        clean_pass += int(brief.report.passed)
        for name, (mutate, detected) in MUTATIONS.items():
            report = check_narrative(mutate(brief.narrative), brief.pack, engine.cfg)
            caught[name] += int((not report.passed) and detected(report))
    n = len(vehicles)
    result = {
        "briefs": n, "writer": "extractive", "clean_pass_rate": round(clean_pass / n, 4) if n else None,
        "mutation_detection_rate": {name: round(hits / n, 4) for name, hits in caught.items()} if n else {},
    }
    (engine.cfg.path("reports") / "guardrail_eval.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
