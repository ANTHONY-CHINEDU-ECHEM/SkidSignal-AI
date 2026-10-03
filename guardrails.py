"""Deterministic checks applied to every generated narrative before it is released.

1. Citation validity: every citation key must exist in the evidence pack.
2. Citation coverage: evidence bearing sentences must carry at least one citation.
3. Numeric fidelity: every number in the narrative must already appear in the
   computed facts or in a cited record. The model may copy numbers, never create them.
4. Calibrated language: terms that assert a confirmed defect are rejected.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from skidsignal.config import Settings
from skidsignal.rag.evidence import EvidencePack

CITE_RE = re.compile(r"\[(S|[CRIBK]:[^\]\s]+)\]")
NUM_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?!\w)")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\[])")
COVERED_SECTIONS = ("summary", "failure_modes", "context", "assessment")


@dataclass
class GuardrailReport:
    passed: bool
    citation_validity: float
    citation_coverage: float
    numeric_fidelity: float
    invalid_citations: list[str] = field(default_factory=list)
    unsupported_numbers: list[str] = field(default_factory=list)
    overstatement_hits: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def citations(text: str) -> list[str]:
    return CITE_RE.findall(text or "")


def numbers(text: str) -> set[float]:
    found = set()
    for token in NUM_RE.findall(CITE_RE.sub(" ", text or "")):
        try:
            found.add(round(float(token.replace(",", "").rstrip(".")), 4))
        except ValueError:
            continue
    return found


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split((text or "").strip()) if s.strip()]


def allowed_numbers(pack: EvidencePack) -> set[float]:
    allowed = numbers(" ".join(pack.fact_lines)) | numbers(pack.vehicle)
    for item in pack.items:
        allowed |= numbers(item.title) | numbers(item.text) | numbers(item.date or "")
    return allowed


def _as_text(value) -> str:
    return " ".join(value) if isinstance(value, (list, tuple)) else str(value or "")


def check_narrative(narrative: dict, pack: EvidencePack, cfg: Settings) -> GuardrailReport:
    g = cfg.guardrails
    everything = " ".join(_as_text(v) for v in narrative.values())
    issues: list[str] = []

    used = citations(everything)
    valid = pack.cites()
    invalid = sorted({c for c in used if c not in valid})
    validity = 1.0 if not used else 1.0 - len([c for c in used if c not in valid]) / len(used)
    if invalid:
        issues.append(f"citations not in the evidence pack: {', '.join(invalid)}")
    if not used:
        issues.append("the narrative contains no citations")

    covered = [s for key in COVERED_SECTIONS for s in sentences(_as_text(narrative.get(key)))]
    cited = [s for s in covered if CITE_RE.search(s)]
    coverage = len(cited) / len(covered) if covered else 0.0
    if coverage < g.min_citation_coverage:
        issues.append(f"citation coverage {coverage:.2f} is below {g.min_citation_coverage}")

    stated = numbers(everything)
    unsupported = sorted(stated - allowed_numbers(pack))
    fidelity = 1.0 if not stated else 1.0 - len(unsupported) / len(stated)
    if unsupported:
        issues.append("numbers not found in the facts or cited records: " + ", ".join(f"{n:g}" for n in unsupported))

    lowered = everything.lower()
    overstated = [term for term in g.overstatement_terms if term in lowered]
    if overstated:
        issues.append("overstated language: " + ", ".join(overstated))

    return GuardrailReport(
        passed=not issues, citation_validity=round(validity, 4), citation_coverage=round(coverage, 4),
        numeric_fidelity=round(fidelity, 4), invalid_citations=invalid,
        unsupported_numbers=[f"{n:g}" for n in unsupported], overstatement_hits=overstated, issues=issues,
    )
