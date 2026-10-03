"""Download the official NHTSA flat files listed in the settings.

Files are streamed to disk, unzipped, and recorded in a manifest with size and
SHA 256 so that every downstream number can be traced to an exact snapshot.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from skidsignal.config import Settings, get_logger

log = get_logger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download_file(url: str, dest: Path, timeout: int = 120) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for block in resp.iter_content(chunk_size=1 << 20):
                fh.write(block)
    return dest


def download_all(cfg: Settings, groups: list[str] | None = None) -> list[dict]:
    """Fetch every archive in the requested source groups and unzip it into data/raw."""
    raw = cfg.path("raw")
    groups = groups or ["complaints", "recall_documents", "recalls_flat", "investigations", "communications"]
    manifest = []
    for group in groups:
        for rel in cfg["sources"].get(group, []):
            url = f"{cfg['sources']['base_url']}/{rel}"
            archive = raw / Path(rel).name
            log.info("downloading %s", url)
            download_file(url, archive)
            with zipfile.ZipFile(archive) as zf:
                members = zf.namelist()
                zf.extractall(raw)
            manifest.append(
                {
                    "group": group,
                    "url": url,
                    "archive": archive.name,
                    "bytes": archive.stat().st_size,
                    "sha256": _sha256(archive),
                    "members": members,
                    "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            archive.unlink()
    (raw / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("downloaded %d archives", len(manifest))
    return manifest
