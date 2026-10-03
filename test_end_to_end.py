"""The real pipeline on the bundled sample: prepare, index, signals, brief, guardrails, API."""
import json

import pytest
from fastapi.testclient import TestClient

from skidsignal.api import app as api_module
from skidsignal.rag.brief import compose_extractive
from skidsignal.rag.guardrails import check_narrative, numbers
from skidsignal.signals.backtest import run_backtest


@pytest.fixture(scope="module")
def vehicle(engine) -> str:
    table = engine.signals(flagged_only=False)
    return table.sort_values("abs_complaints", ascending=False)["vehicle"].iloc[0]


def test_prepare_builds_all_tables(engine, cfg):
    profile = json.loads((cfg.path("processed") / "data_profile.json").read_text())
    assert profile["complaints"] > 2000 and profile["abs_complaints"] >= 400
    assert profile["kb_by_source"]["reference"] >= 20 and profile["kb_by_source"]["recall"] > 100
    assert engine.panel.abs.sum() == profile["abs_complaints"]


def test_signals_only_use_data_up_to_the_as_of_month(engine):
    early = engine.signals("2022-06", flagged_only=False)
    months = engine.panel.months
    cutoff = engine.panel.month_index("2022-06")
    start = max(0, cutoff - engine.cfg.signals.window_months + 1)
    assert early["abs_complaints"].sum() == engine.panel.abs[:, start: cutoff + 1].sum()
    assert early["as_of"].iloc[0] == "2022-06" and months[cutoff] == "2022-06"


def test_backtest_runs_and_reports_every_rule(engine, cfg):
    report = run_backtest(engine.panel, engine.campaigns, engine.recall_vehicles, cfg)
    assert {"skidsignal", "surge_channel", "disproportionality_channel", "volume_rule_5"} <= set(report["rules"])


def test_extractive_brief_passes_guardrails_and_respects_the_as_of_date(engine, vehicle):
    brief = engine.brief(vehicle, as_of="2024-06")
    assert brief.report.passed, brief.report.issues
    assert brief.writer == "extractive" and "## 2. Statistical evidence" in brief.markdown
    dated = [i.date for i in brief.pack.items if i.date]
    assert dated and max(dated) <= "2024-06-30"


def test_guardrails_catch_each_injected_fault(engine, vehicle):
    brief = engine.brief(vehicle)
    good = compose_extractive(brief.pack)
    fake = check_narrative({**good, "summary": good["summary"] + " See also [C:00000000]."}, brief.pack, engine.cfg)
    assert not fake.passed and fake.invalid_citations == ["C:00000000"]
    number = check_narrative({**good, "context": good["context"] + " There were 98765 incidents [S]."}, brief.pack, engine.cfg)
    assert not number.passed and number.unsupported_numbers == ["98765"]
    loud = check_narrative({**good, "assessment": good["assessment"] + " This proves a defect [S]."}, brief.pack, engine.cfg)
    assert not loud.passed and loud.overstatement_hits == ["proves"]
    bare = check_narrative({**good, "summary": "The vehicle has many complaints. Owners are unhappy. It keeps happening. Nothing is fixed."}, brief.pack, engine.cfg)
    assert not bare.passed and bare.citation_coverage < 0.9


def test_number_extraction_ignores_citations_and_campaign_codes():
    assert numbers("204 of 1,122 complaints (18.2 percent) [C:11674735], campaign 23V651, as of 2026-01.") == {204, 1122, 18.2, 2026, 1}


class FakeLLM:
    name = "fake"

    def __init__(self, payloads):
        self.payloads, self.calls = list(payloads), 0

    def complete(self, system, user):
        self.calls += 1
        return self.payloads.pop(0)


def test_language_model_draft_is_used_when_it_passes(engine, vehicle):
    from skidsignal.rag.brief import generate_brief
    pack = engine.brief(vehicle).pack
    draft = compose_extractive(pack)
    brief = generate_brief(pack, engine.cfg, FakeLLM(["```json\n" + json.dumps(draft) + "\n```"]))
    assert brief.writer == "fake" and brief.report.passed


def test_failed_draft_is_repaired_once_then_replaced(engine, vehicle):
    from skidsignal.rag.brief import generate_brief
    pack = engine.brief(vehicle).pack
    bad = {**compose_extractive(pack), "summary": "This definitely proves 424242 failures [C:1]."}
    llm = FakeLLM([json.dumps(bad), json.dumps(bad)])
    brief = generate_brief(pack, engine.cfg, llm)
    assert llm.calls == 2 and brief.writer.startswith("extractive (fallback") and brief.report.passed
    broken = generate_brief(pack, engine.cfg, FakeLLM(["not json at all"]))
    assert broken.writer.startswith("extractive (fallback") and broken.report.passed


def test_ask_returns_cited_passages(engine):
    result = engine.ask("ABS warning light and module failure", sources=["complaint"])
    assert result["hits"] and result["citations"] and all(c.startswith("C:") for c in result["citations"])


def test_api_endpoints(engine, vehicle, monkeypatch):
    monkeypatch.setattr(api_module, "engine", lambda: engine)
    client = TestClient(api_module.app)
    assert client.get("/health").json()["status"] == "ok"
    assert isinstance(client.get("/signals", params={"top": 5}).json(), list)
    assert client.get("/signals", params={"as_of": "1999-01"}).status_code == 422
    ok = client.post("/brief", json={"vehicle": vehicle})
    assert ok.status_code == 200 and ok.json()["guardrails"]["passed"]
    assert client.post("/brief", json={"vehicle": "NOT A VEHICLE"}).status_code == 404
    found = client.post("/search", json={"query": "ABS module fire", "k": 3, "sources": ["recall"]}).json()
    assert found and all(hit["source"] == "recall" for hit in found)
    assert client.post("/ask", json={"question": "Which recalls mention an ABS module fire?"}).json()["answer"]
