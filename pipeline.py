"""Raw files to processed parquet tables and the knowledge base."""
from __future__ import annotations

import json

import pandas as pd

from skidsignal.config import Settings, get_logger
from skidsignal.ingestion import parsers
from skidsignal.processing import corpus
from skidsignal.processing.normalise import build_complaints, build_recalls
from skidsignal.processing.taxonomy import Taxonomy

log = get_logger(__name__)

SIGNAL_COLUMNS = [
    "complaint_id", "make", "model", "vehicle", "model_year", "prod_type", "received", "month",
    "crash", "fire", "injured", "deaths", "is_abs", "is_brake_domain", "severe",
]


def prepare(cfg: Settings) -> dict:
    raw_dir, out_dir = cfg.path("raw"), cfg.path("processed")
    taxonomy = Taxonomy(cfg.path("taxonomy"))
    files = parsers.discover(raw_dir)
    if not files["complaints"]:
        raise FileNotFoundError(f"no complaint flat files found in {raw_dir}; run the download step first")

    raw = pd.concat([parsers.read_complaints(p) for p in files["complaints"]], ignore_index=True)
    log.info("read %d complaint component rows from %d files", len(raw), len(files["complaints"]))
    complaints = build_complaints(raw, taxonomy)
    raw_rows = len(raw)
    del raw
    brake = complaints[complaints["is_brake_domain"]].reset_index(drop=True)
    complaints[SIGNAL_COLUMNS].to_parquet(out_dir / "complaints.parquet", index=False)
    brake.to_parquet(out_dir / "brake_complaints.parquet", index=False)

    parts = [corpus.complaint_documents(brake, cfg.corpus.min_narrative_chars)]
    campaigns = vehicles = None
    if files["recall_documents"]:
        docs = pd.concat([parsers.read_recall_documents(p) for p in files["recall_documents"]], ignore_index=True)
        flat = (
            pd.concat([parsers.read_recalls_flat(p) for p in files["recalls_flat"]], ignore_index=True)
            if files["recalls_flat"] else None
        )
        campaigns, vehicles = build_recalls(
            docs, taxonomy, cfg.corpus.recall_summaries_per_campaign, cfg.corpus.abs_recall_min_share, flat
        )
        campaigns.to_parquet(out_dir / "recall_campaigns.parquet", index=False)
        vehicles.to_parquet(out_dir / "recall_vehicles.parquet", index=False)
        parts.append(corpus.recall_documents(campaigns, vehicles))
    if files["investigations"]:
        inv = pd.concat([parsers.read_investigations(p) for p in files["investigations"]], ignore_index=True)
        parts.append(corpus.investigation_documents(inv))
    if files["communications"]:
        com = pd.concat([parsers.read_communications(p) for p in files["communications"]], ignore_index=True)
        parts.append(corpus.communication_documents(com))
    parts.append(corpus.reference_documents(cfg.path("knowledge")))

    kb = corpus.build_knowledge_base(parts, cfg.corpus.chunk_chars, cfg.corpus.chunk_overlap)
    kb.to_parquet(out_dir / "knowledge_base.parquet", index=False)

    vehicle_rows = complaints[complaints["prod_type"] == "V"]
    profile = {
        "raw_component_rows": int(raw_rows),
        "complaints": int(len(complaints)),
        "vehicle_complaints": int(len(vehicle_rows)),
        "received_min": str(complaints["received"].min().date()),
        "received_max": str(complaints["received"].max().date()),
        "abs_complaints": int(vehicle_rows["is_abs"].sum()),
        "abs_by_component_only": int((vehicle_rows["abs_component"] & ~vehicle_rows["abs_text"]).sum()),
        "brake_domain_complaints": int(vehicle_rows["is_brake_domain"].sum()),
        "distinct_vehicles": int(vehicle_rows["vehicle"].nunique()),
        "abs_severe": int((vehicle_rows["is_abs"] & vehicle_rows["severe"]).sum()),
        "recall_document_rows": int(len(docs)) if campaigns is not None else 0,
        "recall_campaigns": int(len(campaigns)) if campaigns is not None else 0,
        "abs_recall_campaigns": int(campaigns["is_abs"].sum()) if campaigns is not None else 0,
        "recall_dates_exact": bool(campaigns["date_is_exact"].all()) if campaigns is not None else False,
        "kb_documents": int(kb["doc_id"].nunique()),
        "kb_chunks": int(len(kb)),
        "kb_by_source": {k: int(v) for k, v in kb.drop_duplicates("doc_id")["source"].value_counts().items()},
        "files": {g: [p.name for p in ps] for g, ps in files.items() if ps},
    }
    (out_dir / "data_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    log.info("prepared: %s", json.dumps({k: v for k, v in profile.items() if k != "files"}))
    return profile
