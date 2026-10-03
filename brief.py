"""Analyst brief generation.

Numbers, tables and evidence lists are rendered by code. Only the connecting narrative
is written, either by the deterministic extractive writer or by a language model whose
draft must pass the guardrails. A draft that fails is repaired once and then replaced by
the extractive narrative, so a brief is never released with a failed check.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from skidsignal.config import Settings, get_logger
from skidsignal.rag import prompts
from skidsignal.rag.evidence import LIMITS_NOTE, EvidencePack
from skidsignal.rag.guardrails import GuardrailReport, check_narrative

log = get_logger(__name__)

LIMITATIONS = (
    "Complaints are voluntary, unverified owner reports and reporting rises after publicity or a recall. "
    "Disproportionality compares complaint mixes and is not a failure rate, because the number of vehicles in "
    "service is not in the data. Signals are computed for a vehicle family across all model years, so a problem "
    "confined to one model year can be diluted. The brief only uses records received on or before the as of date."
)


@dataclass
class Brief:
    vehicle: str
    as_of: str
    markdown: str
    narrative: dict
    report: GuardrailReport
    writer: str
    pack: EvidencePack

    def to_dict(self) -> dict:
        return {"vehicle": self.vehicle, "as_of": self.as_of, "writer": self.writer, "markdown": self.markdown,
                "narrative": self.narrative, "guardrails": self.report.to_dict(), "evidence": self.pack.to_dict()}


def _quote(text: str, limit: int = 170) -> str:
    text = text.replace('"', "'").replace(" ...", "")
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0]
    return re.sub(r"[.!?]+\s+", "; ", text).rstrip(" .;!?,")


def compose_extractive(pack: EvidencePack) -> dict:
    """Template based narrative. Every sentence is built from the pack and carries a citation."""
    f = pack.facts
    rank = f", rank {f['rank']} of {f['flagged_total']} flagged families" if f["rank"] else ""
    status = f"is on the {f['tier']} tier" if f["tier"] != "none" else "is not currently flagged"
    summary = [
        f"{pack.vehicle} {status} as of {pack.as_of} with a priority score of {f['score']}{rank} [S].",
        f"Between {f['window_start']} and {pack.as_of}, {f['abs_complaints']:,} of its {f['all_complaints']:,} complaints "
        f"were ABS related, a share of {f['abs_share_pct']} percent against {f['database_share_pct']} percent across all vehicles [S].",
        f"The proportional reporting ratio is {f['prr']} with a 95 percent interval of {f['prr_lo']} to {f['prr_hi']}, and the "
        f"lower credibility bound of the information component (IC025) is {f['ic025']} [S].",
    ]
    recent = (f"The most recent {f['recent_months']} months brought {f['recent_abs']} ABS complaints against "
              f"{f['expected_recent']} expected from the earlier rate, a rate ratio of {f['rate_ratio']}")
    summary.append(
        recent + (f" that stays significant after false discovery control (q {f['surge_q']}) [S]." if f["surging"]
                  else f", which does not meet the surge criterion (q {f['surge_q']}) [S].")
    )

    modes = pack.failure_modes
    fm = []
    if modes:
        lead = f"The most frequent failure mode tag is \"{modes[0]['label']}\" ({modes[0]['count']} narratives, {100 * modes[0]['share']:.1f} percent)"
        if len(modes) > 1:
            lead += f", followed by \"{modes[1]['label']}\" ({modes[1]['count']}, {100 * modes[1]['share']:.1f} percent)"
        fm.append(lead + " [S].")
    if pack.model_years:
        fm.append("Complaints concentrate in model years " + ", ".join(f"{y} ({n})" for y, n in pack.model_years[:3]) + " [S].")
    for item in pack.by_source("complaint")[:3]:
        owner = item.title.split("|")[0].strip() or pack.vehicle
        fm.append(f"An owner report for a {owner} states: \"{_quote(item.text)}\" [{item.cite}].")
    notes = [i for i in pack.by_source("reference") if i.cite != LIMITS_NOTE]
    if notes:
        first = re.split(r"(?<=[.!?])\s+", notes[0].text)[0].rstrip(".")
        fm.append(f"Reference note \"{notes[0].title}\": {first} [{notes[0].cite}].")

    own = [i for i in pack.by_source("recall") if i.role == "recall for this family"]
    related = [i for i in pack.by_source("recall") if i.role != "recall for this family"]
    context = []
    if own:
        context.append("ABS related recall campaigns already on file for this family: "
                       + ", ".join(i.cite[2:] for i in own) + " " + " ".join(f"[{i.cite}]" for i in own) + ".")
        context.append(f"The most recent of these, {own[0].cite[2:]}, states: \"{_quote(own[0].text, 220)}\" [{own[0].cite}].")
    else:
        context.append("No ABS related recall campaign for this family appears in the recall file before the as of date [S].")
    for item in related[:2]:
        context.append(f"A brake related campaign for the same make, {item.cite[2:]}, states: \"{_quote(item.text, 200)}\" [{item.cite}].")

    if f["surging"] and f["disproportionate"]:
        reading = "The evidence is consistent with a growing ABS related problem that is also unusually prominent in this family's complaint mix [S]."
    elif f["surging"]:
        reading = ("The evidence is consistent with a recent rise in ABS related complaints, although ABS issues are not "
                   "unusually prominent in this family's overall complaint mix [S].")
    elif f["disproportionate"]:
        reading = "ABS issues are persistently over represented for this family, but the recent rate is not rising faster than its own history [S]."
    else:
        reading = "Neither the disproportionality channel nor the surge channel is currently active for this family [S]."
    assessment = [
        reading,
        f"{f['severe']} of the {f['abs_complaints']:,} ABS complaints involve a crash, fire, injury or death "
        f"({f['crash']} crash, {f['fire']} fire, {f['injured']} injured, {f['deaths']} deaths) [S].",
    ]
    if f["cusum_alarm"]:
        assessment.append(f"The CUSUM chart is in alarm with a peak of {f['cusum_peak']}, which points to a sustained shift and not a single unusual month [S].")
    waiting = next((m for m in modes if m["mode"] == "remedy_unavailable" and m["share"] >= 0.15), None)
    if waiting:
        assessment.append(f"{100 * waiting['share']:.1f} percent of narratives mention unavailable repair parts, so part of the volume "
                          "may reflect a known problem awaiting remedy and not a new defect [S].")
    assessment.append(f"This is a statistical signal built from unverified owner reports and it does not establish that a defect exists [{LIMITS_NOTE}].")

    actions = ["Read the cited narratives in full and confirm the failure mode coding."]
    if f["fire"] > 0:
        actions.append("Prioritise the fire narratives and establish whether each vehicle was parked or moving.")
    if own:
        actions.append("Compare complaint model years with the recall population to test whether the recall scope and remedy are adequate.")
    else:
        actions.append("Check manufacturer communications and open investigations for this family, since no ABS recall is on file.")
    if pack.model_years:
        actions.append("Request a build date breakdown for model years " + ", ".join(str(y) for y, _ in pack.model_years[:3]) + ".")
    actions.append("Review the signal again next month and note whether the tier or score has changed.")
    return {"summary": " ".join(summary), "failure_modes": " ".join(fm), "context": " ".join(context),
            "assessment": " ".join(assessment), "actions": actions}


def parse_llm_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[start: end + 1])
    missing = {"summary", "failure_modes", "context", "assessment", "actions"} - set(data)
    if missing:
        raise ValueError(f"language model response is missing keys: {sorted(missing)}")
    if isinstance(data["actions"], str):
        data["actions"] = [a.strip("-* ") for a in data["actions"].splitlines() if a.strip()]
    return data


def _table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])


def render_markdown(pack: EvidencePack, narrative: dict, report: GuardrailReport, writer: str) -> str:
    f = pack.facts
    rank = f"{f['rank']} of {f['flagged_total']}" if f["rank"] else "not flagged"
    stats = _table(
        ["Metric", "Value", "How to read it"],
        [
            ["ABS related complaints", f"{f['abs_complaints']:,} of {f['all_complaints']:,} ({f['abs_share_pct']}%)", f"Database wide share is {f['database_share_pct']}%"],
            ["Expected ABS complaints", f["expected"], "If this family matched the database mix"],
            ["Proportional reporting ratio", f"{f['prr']} ({f['prr_lo']} to {f['prr_hi']})", "Signal criterion: at least 2"],
            ["Reporting odds ratio", f"{f['ror']} ({f['ror_lo']} to {f['ror_hi']})", "Interval excluding 1 supports an excess"],
            ["Chi square", f["chi2"], "Signal criterion: at least 4"],
            ["Information component", f"{f['ic']} (IC025 {f['ic025']})", "Signal criterion: IC025 above 0"],
            [f"Last {f['recent_months']} months", f"{f['recent_abs']} observed, {f['expected_recent']} expected", f"Rate ratio {f['rate_ratio']}, adjusted q {f['surge_q']}"],
            ["CUSUM peak", f["cusum_peak"], "In alarm" if f["cusum_alarm"] else "Not in alarm"],
            ["Severe outcomes", f"{f['severe']} ({f['severe_share_pct']}%)", f"{f['crash']} crash, {f['fire']} fire, {f['injured']} injured, {f['deaths']} deaths"],
        ],
    )
    modes = _table(["Failure mode", "Narratives", "Share"],
                   [[m["label"], m["count"], f"{100 * m['share']:.1f}%"] for m in pack.failure_modes])
    complaints = "\n".join(
        f"- **[{i.cite}]** {i.title} (received {i.date}, {i.role}): \"{i.text}\"" for i in pack.by_source("complaint"))
    others = "\n".join(
        f"- **[{i.cite}]** {i.title} ({i.role}{', ' + i.date if i.date else ''}): {i.text}"
        for i in pack.items if i.source != "complaint")
    actions = "\n".join(f"{n}. {a}" for n, a in enumerate(narrative["actions"], 1))
    series = ", ".join(f"{m}: {n}" for m, n in pack.monthly)
    checks = (f"citation validity {report.citation_validity:.2f}, citation coverage {report.citation_coverage:.2f}, "
              f"numeric fidelity {report.numeric_fidelity:.2f}")
    return f"""# SkidSignal brief: {pack.vehicle}

| As of | Tier | Priority score | Rank among flagged families | Writer | Guardrails |
|---|---|---|---|---|---|
| {pack.as_of} | {f['tier']} | {f['score']} | {rank} | {writer} | {'passed' if report.passed else 'FAILED'} |

## 1. Signal summary

{narrative['summary']}

## 2. Statistical evidence

Window: {f['window_start']} to {pack.as_of} ({f['window_months']} months). All figures are computed by the signal engine.

{stats}

## 3. Failure mode profile

{narrative['failure_modes']}

{modes}

## 4. Complaint evidence

{complaints}

## 5. Recalls and context

{narrative['context']}

{others}

## 6. Assessment

{narrative['assessment']}

## 7. Recommended analyst actions

{actions}

## 8. Limitations

{LIMITATIONS}

Monthly ABS complaints in the window: {series}

Guardrail checks: {checks}. Citation keys: S is a computed statistic, C is an owner complaint (ODI number), R is a recall campaign, K is a project reference note.
"""


def generate_brief(pack: EvidencePack, cfg: Settings, llm=None) -> Brief:
    narrative, writer = compose_extractive(pack), "extractive"
    if llm is not None:
        try:
            draft = parse_llm_json(llm.complete(prompts.SYSTEM_PROMPT, prompts.brief_prompt(pack)))
            report = check_narrative(draft, pack, cfg)
            for _ in range(cfg.llm.max_repair_attempts):
                if report.passed:
                    break
                log.warning("draft failed guardrails, requesting repair: %s", report.issues)
                draft = parse_llm_json(llm.complete(prompts.SYSTEM_PROMPT, prompts.brief_prompt(pack, report.issues, draft)))
                report = check_narrative(draft, pack, cfg)
            if report.passed:
                narrative, writer = draft, llm.name
            else:
                writer = f"extractive (fallback, {llm.name} draft failed guardrails)"
        except Exception as exc:  # network, parsing or schema failure: degrade, never crash
            log.warning("language model writer failed: %s", exc)
            writer = f"extractive (fallback, {type(exc).__name__})"
    report = check_narrative(narrative, pack, cfg)
    return Brief(pack.vehicle, pack.as_of, render_markdown(pack, narrative, report, writer), narrative, report, writer, pack)
