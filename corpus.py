"""Assemble the retrieval knowledge base from every source into one chunk table.

Every chunk carries a citation key that the generation layer must use verbatim:
C:<ODI number> for a complaint, R:<campaign> for a recall, I:<action number> for an
investigation, B:<NHTSA id> for a manufacturer communication, K:<slug> for a
reference note.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from skidsignal.processing.normalise import clean_label, clean_text, parse_date, parse_model_year

BRAKE_TEXT = r"\bBRAK|ANTI.?LOCK|\bABS\b|STABILITY CONTROL|TRACTION CONTROL|HYDRAULIC CONTROL"


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Split on sentence boundaries into windows of at most max_chars with soft overlap."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    sentences = re.split(r"(?<=[.!?;])\s+", text)
    chunks, current = [], ""
    for sentence in sentences:
        while len(sentence) > max_chars:  # pathological run on sentence
            chunks.append((current + " " + sentence[: max_chars - len(current)]).strip())
            sentence, current = sentence[max_chars - len(current):], ""
        if len(current) + len(sentence) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = current[-overlap:] if overlap else ""
        current = (current + " " + sentence).strip()
    if current:
        chunks.append(current)
    return chunks


def _year_text(years: pd.Series) -> pd.Series:
    return years.astype("Int64").astype("string").fillna("").astype(str)


def _pipe(values) -> str:
    items = sorted({str(v).strip() for v in values if str(v).strip()})
    return "|" + "|".join(items) + "|" if items else ""


def complaint_documents(brake: pd.DataFrame, min_chars: int) -> pd.DataFrame:
    df = brake[brake["narrative"].str.len() >= min_chars]
    year = _year_text(df["model_year"])
    return pd.DataFrame(
        {
            "doc_id": "C:" + df["complaint_id"].astype(str),
            "source": "complaint",
            "title": (year + " " + df["vehicle"] + " | " + df["components"].str.slice(0, 160)).str.strip(),
            "text": df["narrative"],
            "makes": "|" + df["make"] + "|",
            "vehicles": "|" + df["vehicle"] + "|",
            "model_year": df["model_year"].astype("Int64"),
            "date": df["received"],
            "is_abs": df["is_abs"],
        }
    )


def recall_documents(campaigns: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    df = campaigns
    link = vehicles[vehicles["campno"].isin(df["campno"])].groupby("campno")
    makes, models = link["make"].agg(_pipe), link["vehicle"].agg(_pipe)
    span = _year_text(df["model_year_min"]) + " to " + _year_text(df["model_year_max"])
    return pd.DataFrame(
        {
            "doc_id": "R:" + df["campno"],
            "source": "recall",
            "title": "Recall " + df["campno"] + " | " + df["makes"].str.slice(0, 80) + " | model years " + span,
            "text": df["text"],
            "makes": df["campno"].map(makes).fillna(""),
            "vehicles": df["campno"].map(models).fillna(""),
            "model_year": df["model_year_max"].astype("Int64"),
            "date": df["date"],
            "is_abs": df["is_abs"],
            "is_brake": df["is_brake_domain"],
        }
    )


def investigation_documents(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "action": clean_label(raw["ACTION_NUMBER"]),
            "make": clean_label(raw["MAKETXT"]),
            "vehicle": (clean_label(raw["MAKETXT"]) + " " + clean_label(raw["MODELTXT"])).str.strip(),
            "model_year": parse_model_year(raw["YEARTXT"]),
            "date": parse_date(raw["ODATE"]),
            "text": (clean_text(raw["SUBJECT"]) + ". " + clean_text(raw["SUMMARY"])).str.strip(),
            "component": clean_label(raw["COMPNAME"]),
        }
    )
    df = df[(df["component"] + " " + df["text"]).str.contains(BRAKE_TEXT, case=False, regex=True)]
    g = df.groupby("action")
    out = g.agg(text=("text", "first"), date=("date", "min"), model_year=("model_year", "max")).reset_index()
    out["makes"], out["vehicles"] = out["action"].map(g["make"].agg(_pipe)), out["action"].map(g["vehicle"].agg(_pipe))
    out["doc_id"], out["source"] = "I:" + out["action"], "investigation"
    out["title"] = "Investigation " + out["action"]
    out["is_abs"] = out["text"].str.contains(r"\bABS\b|ANTI.?LOCK", case=False, regex=True)
    return out.drop(columns="action")


def communication_documents(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "nid": raw["NHTSA_ID"].astype(str).str.strip(),
            "make": clean_label(raw["MAKETXT"]),
            "vehicle": (clean_label(raw["MAKETXT"]) + " " + clean_label(raw["MODELTXT"])).str.strip(),
            "model_year": parse_model_year(raw["YEARTXT"]),
            "date": parse_date(raw["COMMUNICATION_DATE"]),
            "text": clean_text(raw["SUMMARY"]),
            "component": clean_label(raw["NHTSA_COMPONENTS"]),
        }
    )
    df = df[(df["component"] + " " + df["text"]).str.contains(BRAKE_TEXT, case=False, regex=True)]
    g = df.groupby("nid")
    out = g.agg(text=("text", "first"), date=("date", "min"), model_year=("model_year", "max")).reset_index()
    out["makes"], out["vehicles"] = out["nid"].map(g["make"].agg(_pipe)), out["nid"].map(g["vehicle"].agg(_pipe))
    out["doc_id"], out["source"] = "B:" + out["nid"], "bulletin"
    out["title"] = "Manufacturer communication " + out["nid"]
    out["is_abs"] = out["text"].str.contains(r"\bABS\b|ANTI.?LOCK", case=False, regex=True)
    return out.drop(columns="nid")


def reference_documents(knowledge_dir: Path) -> pd.DataFrame:
    """Each second level heading of every markdown note becomes one citable document."""
    rows = []
    for path in sorted(Path(knowledge_dir).glob("*.md")):
        body = path.read_text(encoding="utf-8")
        for section in re.split(r"\n(?=## )", body):
            match = re.match(r"## (.+)\n", section)
            if not match:
                continue
            heading = match.group(1).strip()
            slug = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")
            rows.append(
                {
                    "doc_id": f"K:{path.stem}.{slug}", "source": "reference", "title": heading,
                    "text": re.sub(r"\s+", " ", section[match.end():]).strip(), "makes": "", "vehicles": "",
                    "model_year": pd.NA, "date": pd.NaT, "is_abs": True,
                }
            )
    return pd.DataFrame(rows)


def build_knowledge_base(parts: list[pd.DataFrame], max_chars: int, overlap: int) -> pd.DataFrame:
    """Concatenate source documents and explode them into retrieval chunks."""
    columns = ["doc_id", "source", "title", "text", "makes", "vehicles", "model_year", "date", "is_abs", "is_brake"]
    parts = [p.assign(is_brake=True) if "is_brake" not in p.columns else p for p in parts if p is not None and len(p)]
    docs = pd.concat([p[columns] for p in parts], ignore_index=True)
    docs = docs[docs["text"].str.len() > 0].drop_duplicates("doc_id").reset_index(drop=True)
    docs["chunks"] = [chunk_text(t, max_chars, overlap) for t in docs["text"]]
    kb = docs.drop(columns="text").explode("chunks").rename(columns={"chunks": "text"}).reset_index(drop=True)
    kb["chunk_id"] = kb["doc_id"] + "#" + kb.groupby("doc_id").cumcount().astype(str)
    kb["model_year"] = kb["model_year"].astype("Int64")
    kb["date"] = pd.to_datetime(kb["date"])
    kb["is_abs"] = kb["is_abs"].astype(bool)
    kb["is_brake"] = kb["is_brake"].astype(bool)
    return kb
