"""Turn raw flat file rows into clean, analysis ready tables.

Complaints arrive one row per (complaint, component). Surveillance statistics need
one row per complaint, otherwise a narrative filed against five components would be
counted five times. Recall documents arrive one row per (campaign, document, vehicle)
and are rolled up to one row per campaign plus a campaign to vehicle link table.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from skidsignal.config import get_logger
from skidsignal.processing.taxonomy import Taxonomy

log = get_logger(__name__)


def clean_label(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.upper().str.replace(r"\s+", " ", regex=True).str.strip()


def clean_text(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str).str.replace(r"\\r\\n|\\n|\\r", " ", regex=True)
    return s.str.replace(r"\s+", " ", regex=True).str.strip()


def parse_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str).str.strip(), format="%Y%m%d", errors="coerce")


def parse_model_year(s: pd.Series) -> pd.Series:
    year = pd.to_numeric(s, errors="coerce")
    return year.where((year >= 1950) & (year <= 2030)).astype("Int64")


def build_complaints(raw: pd.DataFrame, taxonomy: Taxonomy) -> pd.DataFrame:
    """Collapse component rows to one record per complaint and attach ABS flags."""
    df = raw.copy()
    df["make"] = clean_label(df["MAKETXT"])
    df["model"] = clean_label(df["MODELTXT"])
    df["component"] = clean_label(df["COMPDESC"])
    key = ["ODINO", "make", "model", "YEARTXT"]

    components = (
        df.drop_duplicates(key + ["component"]).groupby(key, sort=False)["component"].agg(" | ".join).rename("components")
    )
    base = df.drop_duplicates(key).merge(components, left_on=key, right_index=True, how="left")
    dup = base.groupby("ODINO").cumcount()
    base["complaint_id"] = base["ODINO"].astype(str).where(dup == 0, base["ODINO"].astype(str) + "_" + dup.astype(str))

    out = pd.DataFrame(
        {
            "complaint_id": base["complaint_id"].to_numpy(),
            "odino": base["ODINO"].astype(str).to_numpy(),
            "manufacturer": base["MFR_NAME"].astype(str).str.strip().to_numpy(),
            "make": base["make"].to_numpy(),
            "model": base["model"].to_numpy(),
            "model_year": parse_model_year(base["YEARTXT"]).to_numpy(),
            "prod_type": base["PROD_TYPE"].astype(str).str.strip().to_numpy(),
            "received": parse_date(base["LDATE"]).to_numpy(),
            "incident": parse_date(base["FAILDATE"]).to_numpy(),
            "crash": (base["CRASH"].astype(str).str.upper() == "Y").to_numpy(),
            "fire": (base["FIRE"].astype(str).str.upper() == "Y").to_numpy(),
            "injured": pd.to_numeric(base["INJURED"], errors="coerce").fillna(0).astype(int).to_numpy(),
            "deaths": pd.to_numeric(base["DEATHS"], errors="coerce").fillna(0).astype(int).to_numpy(),
            "miles": pd.to_numeric(base["MILES"], errors="coerce").to_numpy(),
            "source_type": base["CMPL_TYPE"].astype(str).str.strip().to_numpy(),
            "components": base["components"].to_numpy(),
            "narrative": clean_text(base["CDESCR"]).to_numpy(),
        }
    )
    out["vehicle"] = (out["make"] + " " + out["model"]).str.strip()
    out = out[out["received"].notna() & (out["make"] != "")].reset_index(drop=True)

    # Exact duplicate submissions (same vehicle, same narrative) are counted once.
    long_text = out["narrative"].str.len() >= 40
    is_dup = long_text & out.duplicated(["vehicle", "model_year", "narrative"], keep="first")
    log.info("dropping %d exact duplicate narratives", int(is_dup.sum()))
    out = out[~is_dup].reset_index(drop=True)

    out["month"] = out["received"].dt.to_period("M").astype(str)
    out["abs_component"] = taxonomy.is_abs_component(out["components"])
    out["abs_text"] = taxonomy.is_abs_text(out["narrative"])
    out["is_abs"] = out["abs_component"] | out["abs_text"]
    out["is_brake_domain"] = out["is_abs"] | taxonomy.is_brake_component(out["components"])

    tags = pd.DataFrame(False, index=out.index, columns=taxonomy.fm_columns)
    domain = out["is_brake_domain"]
    tagged = taxonomy.tag_failure_modes(out.loc[domain, "narrative"])
    tagged.index = out.index[domain]
    tags.loc[domain, :] = tagged
    out = pd.concat([out, tags.astype(bool)], axis=1)
    out["severe"] = out["crash"] | out["fire"] | (out["injured"] > 0) | (out["deaths"] > 0)
    return out


def _campaign_parts(campno: pd.Series) -> pd.DataFrame:
    parts = campno.str.extract(r"^(?P<yy>\d{2})(?P<rtype>[A-Z])(?P<seq>\d{3})")
    yy = pd.to_numeric(parts["yy"], errors="coerce")
    year = (2000 + yy).where(yy < 60, 1900 + yy)
    return pd.DataFrame({"year": year, "rtype": parts["rtype"], "seq": pd.to_numeric(parts["seq"], errors="coerce")})


def estimate_campaign_dates(campaigns: pd.DataFrame) -> pd.Series:
    """Approximate the filing date from the campaign number.

    NHTSA numbers campaigns sequentially within a calendar year and recall type, so
    campaign 23V651 of roughly 905 vehicle campaigns that year falls about 72 percent
    of the way through 2023. This is only used when the recall flat file (which holds
    the exact report received date) has not been downloaded.
    """
    max_seq = campaigns.groupby(["year", "rtype"])["seq"].transform("max").clip(lower=1)
    fraction = (campaigns["seq"] / (max_seq + 1)).clip(0, 1)
    start = pd.to_datetime(campaigns["year"].astype("Int64").astype(str) + "-01-01", errors="coerce")
    return (start + pd.to_timedelta((fraction * 364).round(), unit="D")).dt.normalize()


def build_recalls(
    docs: pd.DataFrame, taxonomy: Taxonomy, per_campaign: int = 3, abs_min_share: float = 0.25,
    flat: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Roll recall documents up to campaigns and build the campaign to vehicle table."""
    df = pd.DataFrame(
        {
            "campno": clean_label(docs["CAMPNO"]),
            "make": clean_label(docs["MAKETXT"]),
            "model": clean_label(docs["MODELTXT"]),
            "model_year": parse_model_year(docs["YEARTXT"]),
            "summary": clean_text(docs["SUMMARY"]),
        }
    )
    df = df[df["campno"].str.match(r"^\d{2}[A-Z]\d{3}$")]

    vehicles = df[["campno", "make", "model", "model_year"]].drop_duplicates().reset_index(drop=True)
    vehicles["vehicle"] = (vehicles["make"] + " " + vehicles["model"]).str.strip()

    texts = df[df["summary"].str.len() > 0][["campno", "summary"]].drop_duplicates()
    texts["abs_hit"] = taxonomy.is_abs_text(texts["summary"])
    texts["length"] = texts["summary"].str.len()
    texts = texts.sort_values(["campno", "abs_hit", "length"], ascending=[True, False, False])
    top = texts.groupby("campno").head(per_campaign)

    campaigns = pd.DataFrame(
        {
            "text": top.groupby("campno")["summary"].agg(" ".join),
            "abs_share": texts.groupby("campno")["abs_hit"].mean(),
            "n_summaries": texts.groupby("campno")["summary"].size(),
        }
    )
    veh = vehicles.groupby("campno")
    campaigns["makes"] = veh["make"].agg(lambda s: " | ".join(sorted(set(s))))
    campaigns["n_models"] = veh["vehicle"].nunique()
    campaigns["model_year_min"] = veh["model_year"].min()
    campaigns["model_year_max"] = veh["model_year"].max()
    campaigns["n_documents"] = df.groupby("campno").size()
    campaigns = campaigns.reset_index().rename(columns={"index": "campno"})
    campaigns = pd.concat([campaigns, _campaign_parts(campaigns["campno"])], axis=1)
    campaigns["date"] = estimate_campaign_dates(campaigns)
    campaigns["date_is_exact"] = False

    if flat is not None and len(flat):
        exact = parse_date(flat["RCDATE"]).groupby(clean_label(flat["CAMPNO"]).str[:6]).min()
        matched = campaigns["campno"].map(exact)
        campaigns["date_is_exact"] = matched.notna()
        campaigns["date"] = matched.fillna(campaigns["date"])

    campaigns["abs_share"] = campaigns["abs_share"].fillna(0.0)
    campaigns["is_abs"] = campaigns["abs_share"] >= abs_min_share
    campaigns["is_brake_domain"] = campaigns["is_abs"] | campaigns["text"].fillna("").str.contains(
        r"\bBRAK|STABILITY CONTROL|TRACTION CONTROL", case=False, regex=True
    )
    campaigns["text"] = campaigns["text"].fillna("")
    return campaigns, vehicles


def monthly_index(start: str, end: str) -> np.ndarray:
    return pd.period_range(start, end, freq="M").astype(str).to_numpy()
