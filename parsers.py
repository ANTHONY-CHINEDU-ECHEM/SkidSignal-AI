"""Parsers for the NHTSA Office of Defects Investigation flat files.

Layouts follow the published data dictionaries (CMPL.txt, RCL.txt, INV.txt,
TSBS.txt). NHTSA appends fields over time (complaints grew from 49 to 51 fields
in April 2026), so every parser assigns names by position and tolerates extra or
missing trailing columns.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

COMPLAINT_COLUMNS = [
    "CMPLID", "ODINO", "MFR_NAME", "MAKETXT", "MODELTXT", "YEARTXT", "CRASH", "FAILDATE", "FIRE",
    "INJURED", "DEATHS", "COMPDESC", "CITY", "STATE", "VIN", "DATEA", "LDATE", "MILES", "OCCURENCES",
    "CDESCR", "CMPL_TYPE", "POLICE_RPT_YN", "PURCH_DT", "ORIG_OWNER_YN", "ANTI_BRAKES_YN",
    "CRUISE_CONT_YN", "NUM_CYLS", "DRIVE_TRAIN", "FUEL_SYS", "FUEL_TYPE", "TRANS_TYPE", "VEH_SPEED",
    "DOT", "TIRE_SIZE", "LOC_OF_TIRE", "TIRE_FAIL_TYPE", "ORIG_EQUIP_YN", "MANUF_DT", "SEAT_TYPE",
    "RESTRAINT_TYPE", "DEALER_NAME", "DEALER_TEL", "DEALER_CITY", "DEALER_STATE", "DEALER_ZIP",
    "PROD_TYPE", "REPAIRED_YN", "MEDICAL_ATTN", "VEHICLES_TOWED_YN", "STATE_OF_INCIDENT",
    "VEHICLE_OPERATOR",
]

# Data minimisation: location, VIN stub, dealer and operator fields are never loaded.
COMPLAINT_KEEP = [
    "CMPLID", "ODINO", "MFR_NAME", "MAKETXT", "MODELTXT", "YEARTXT", "CRASH", "FAILDATE", "FIRE",
    "INJURED", "DEATHS", "COMPDESC", "LDATE", "MILES", "CDESCR", "CMPL_TYPE", "VEH_SPEED", "PROD_TYPE",
]

RECALL_FLAT_COLUMNS = [
    "RECORD_ID", "CAMPNO", "MAKETXT", "MODELTXT", "YEARTXT", "MFGCAMPNO", "COMPNAME", "MFGNAME",
    "BGMAN", "ENDMAN", "RCLTYPECD", "POTAFF", "ODATE", "INFLUENCED_BY", "MFGTXT", "RCDATE", "DATEA",
    "RPNO", "FMVSS", "DESC_DEFECT", "CONEQUENCE_DEFECT", "CORRECTIVE_ACTION", "NOTES", "RCL_CMPT_ID",
    "MFR_COMP_NAME", "MFR_COMP_DESC", "MFR_COMP_PTNO",
]

RECALL_DOCUMENT_COLUMNS = ["CAMPNO", "DOCUMENT", "MAKETXT", "MODELTXT", "YEARTXT", "SUMMARY"]

INVESTIGATION_COLUMNS = [
    "ACTION_NUMBER", "MAKETXT", "MODELTXT", "YEARTXT", "COMPNAME", "MFR_NAME", "ODATE", "CDATE",
    "CAMPNO", "SUBJECT", "SUMMARY",
]

COMMUNICATION_COLUMNS = [
    "NHTSA_ID", "REPLACEMENT_BULLETIN", "DATE_ADDED", "DOCUMENT_ID", "COMMUNICATION_DATE",
    "MFR_CAMPAIGN_ID", "COMMUNICATION_TYPE", "MAKETXT", "MODELTXT", "YEARTXT", "NHTSA_COMPONENTS",
    "MFR_COMPONENT_SYSTEM", "MFR_COMPONENT_SUBSYSTEM", "SUMMARY",
]


def _read_tab(path: Path, columns: list[str], keep: list[str] | None = None) -> pd.DataFrame:
    """Read a tab delimited flat file with no header and no quoting."""
    df = pd.read_csv(
        path, sep="\t", header=None, dtype=str, quoting=csv.QUOTE_NONE, encoding="utf-8",
        encoding_errors="replace", on_bad_lines="skip", keep_default_na=False,
    )
    n = min(df.shape[1], len(columns))
    df = df.iloc[:, :n]
    df.columns = columns[:n]
    for missing in columns[n:]:
        df[missing] = ""
    return df[keep] if keep else df


def read_complaints(path: str | Path) -> pd.DataFrame:
    return _read_tab(Path(path), COMPLAINT_COLUMNS, COMPLAINT_KEEP)


def read_recalls_flat(path: str | Path) -> pd.DataFrame:
    return _read_tab(Path(path), RECALL_FLAT_COLUMNS)


def read_investigations(path: str | Path) -> pd.DataFrame:
    return _read_tab(Path(path), INVESTIGATION_COLUMNS)


def read_communications(path: str | Path) -> pd.DataFrame:
    return _read_tab(Path(path), COMMUNICATION_COLUMNS)


def read_recall_documents(path: str | Path) -> pd.DataFrame:
    """Recall communication index (quoted CSV with a header and multi line summaries)."""
    df = pd.read_csv(path, dtype=str, encoding="utf-8", encoding_errors="replace", keep_default_na=False)
    df = df.iloc[:, : len(RECALL_DOCUMENT_COLUMNS)]
    df.columns = RECALL_DOCUMENT_COLUMNS
    return df


def discover(raw_dir: Path) -> dict[str, list[Path]]:
    """Map every recognised file in data/raw to its parser group by file name."""
    groups: dict[str, list[Path]] = {
        "complaints": [], "recall_documents": [], "recalls_flat": [], "investigations": [], "communications": [],
    }
    for p in sorted(raw_dir.iterdir()):
        name = p.name.upper()
        if name.startswith(("COMPLAINTS_RECEIVED", "FLAT_CMPL")) and p.suffix.lower() == ".txt":
            groups["complaints"].append(p)
        elif name.startswith("RCL_FROM") and p.suffix.lower() == ".csv":
            groups["recall_documents"].append(p)
        elif name.startswith("FLAT_RCL_P") or name == "FLAT_RCL.TXT":
            groups["recalls_flat"].append(p)
        elif name.startswith("FLAT_INV"):
            groups["investigations"].append(p)
        elif name.startswith("TSBS_RECEIVED") and p.suffix.lower() == ".txt":
            groups["communications"].append(p)
    return groups
