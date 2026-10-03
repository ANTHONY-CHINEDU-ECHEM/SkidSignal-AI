"""Command line interface. Run `python -m skidsignal.cli <command>` or use the Makefile."""
from __future__ import annotations

import argparse
import json
import re

import yaml

from skidsignal.config import get_logger, load_settings

log = get_logger("skidsignal")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def cmd_download(cfg, args):
    from skidsignal.ingestion.download import download_all
    download_all(cfg, args.groups)


def cmd_prepare(cfg, args):
    from skidsignal.processing.pipeline import prepare
    prepare(cfg)


def cmd_index(cfg, args):
    from skidsignal.index.store import build_index
    index = build_index(cfg)
    log.info("indexed %d chunks", len(index.meta))


def cmd_signals(cfg, args):
    from skidsignal.engine import Engine
    table = Engine(cfg).signals(args.as_of)
    table.to_csv(cfg.path("reports") / "signals_latest.csv", index=False)
    cols = ["rank", "vehicle", "tier", "score", "abs_complaints", "all_complaints", "prr", "ic025", "recent_abs", "surge_q"]
    print(table[cols].head(args.top).round(2).to_string(index=False))


def cmd_backtest(cfg, args):
    from skidsignal.engine import Engine
    from skidsignal.signals.backtest import run_backtest
    e = Engine(cfg)
    print(json.dumps(run_backtest(e.panel, e.campaigns, e.recall_vehicles, cfg), indent=2))


def cmd_cluster(cfg, args):
    from skidsignal.analysis.failure_modes import cluster_narratives
    from skidsignal.engine import Engine
    e = Engine(cfg)
    table, info = cluster_narratives(e.index, e.brake, cfg)
    (cfg.path("reports") / "failure_clusters.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(json.dumps(info), "\n", table[["cluster", "size", "top_terms"]].to_string(index=False))


def cmd_evaluate(cfg, args):
    from skidsignal.engine import Engine
    from skidsignal.evaluation.guardrail_eval import evaluate_guardrails
    from skidsignal.evaluation.retrieval_eval import evaluate_retrieval
    e = Engine(cfg)
    print(json.dumps({"retrieval": evaluate_retrieval(e.index, cfg), "guardrails": evaluate_guardrails(e)}, indent=2))


def _write_brief(cfg, brief):
    out = cfg.path("reports") / "briefs"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(brief.vehicle)}_{brief.as_of.replace('-', '_')}"
    (out / f"{stem}.md").write_text(brief.markdown, encoding="utf-8")
    (out / f"{stem}.json").write_text(json.dumps(brief.to_dict(), indent=2, default=str), encoding="utf-8")
    return out / f"{stem}.md"


def cmd_brief(cfg, args):
    from skidsignal.engine import Engine
    e = Engine(cfg)
    vehicles = [args.vehicle] if args.vehicle else e.signals(args.as_of)["vehicle"].head(args.top).tolist()
    for vehicle in vehicles:
        brief = e.brief(vehicle, args.as_of)
        log.info("%s -> %s (%s, guardrails %s)", vehicle, _write_brief(cfg, brief), brief.writer,
                 "passed" if brief.report.passed else "FAILED")


def cmd_ask(cfg, args):
    from skidsignal.engine import Engine
    filters = {k: v for k, v in {"vehicle": args.vehicle, "make": args.make}.items() if v}
    if args.source:
        filters["sources"] = [args.source]
    result = Engine(cfg).ask(args.question, **filters)
    print(result["answer"], f"\n\nwriter: {result['writer']}")


def cmd_figures(cfg, args):
    from skidsignal.viz.figures import make_all
    make_all(cfg)


def cmd_all(cfg, args):
    for step in (cmd_prepare, cmd_index, cmd_signals, cmd_backtest, cmd_cluster, cmd_evaluate, cmd_brief, cmd_figures):
        log.info("=== %s", step.__name__[4:])
        step(cfg, args)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="skidsignal", description="SkidSignal AI pipeline")
    parser.add_argument("--config", default=None, help="path to a settings file")
    parser.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE",
                        help="override one setting, for example --set paths.raw=data/sample")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, fn, help_text):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(fn=fn, as_of=None, top=10, vehicle=None, groups=None)
        return p

    add("download", cmd_download, "fetch the official NHTSA flat files").add_argument("--groups", nargs="*")
    add("prepare", cmd_prepare, "parse raw files and build the knowledge base")
    add("index", cmd_index, "build the retrieval index")
    p = add("signals", cmd_signals, "compute the signal table")
    p.add_argument("--as-of", dest="as_of"); p.add_argument("--top", type=int, default=25)
    add("backtest", cmd_backtest, "replay history and compare alerts with recalls")
    add("cluster", cmd_cluster, "cluster ABS narratives into failure themes")
    add("evaluate", cmd_evaluate, "run the retrieval benchmark and guardrail mutation tests")
    p = add("brief", cmd_brief, "write analyst briefs")
    p.add_argument("--vehicle"); p.add_argument("--as-of", dest="as_of"); p.add_argument("--top", type=int, default=10)
    p = add("ask", cmd_ask, "ask a grounded question")
    p.add_argument("question"); p.add_argument("--vehicle"); p.add_argument("--make"); p.add_argument("--source")
    add("figures", cmd_figures, "render the figures used in the documentation")
    add("all", cmd_all, "run the whole pipeline after download")

    args = parser.parse_args(argv)
    overrides = {k: yaml.safe_load(v) for k, v in (item.split("=", 1) for item in args.overrides)}
    args.fn(load_settings(args.config, overrides), args)


if __name__ == "__main__":
    main()
