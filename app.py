"""REST API. Start with `uvicorn skidsignal.api.app:app` after the pipeline has run."""
from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from skidsignal import __version__
from skidsignal.engine import Engine

app = FastAPI(title="SkidSignal AI", version=__version__,
              description="Emerging antilock brake defect surveillance with grounded analyst briefs.")

SIGNAL_FIELDS = ["rank", "vehicle", "as_of", "tier", "score", "abs_complaints", "all_complaints", "prr", "prr_lo",
                 "prr_hi", "ic025", "recent_abs", "expected_recent", "rate_ratio", "surge_q", "severe", "fire", "crash"]


@lru_cache(maxsize=1)
def engine() -> Engine:
    return Engine()


class SearchRequest(BaseModel):
    query: str = Field(min_length=3)
    k: int = Field(default=8, ge=1, le=50)
    sources: list[str] | None = None
    make: str | None = None
    vehicle: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    abs_only: bool = False


class BriefRequest(BaseModel):
    vehicle: str
    as_of: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class AskRequest(BaseModel):
    question: str = Field(min_length=5)
    make: str | None = None
    vehicle: str | None = None
    sources: list[str] | None = None


def _month(as_of: str | None) -> str | None:
    if as_of is not None and as_of not in set(engine().panel.months):
        raise HTTPException(status_code=422, detail=f"as_of must be a month between {engine().panel.months[0]} and {engine().panel.months[-1]}")
    return as_of


@app.get("/health")
def health() -> dict:
    e = engine()
    return {"status": "ok", "version": __version__, "chunks": int(len(e.index.meta)),
            "latest_complete_month": str(e.panel.months[e.panel.last_complete]), "writer": e.cfg.llm.provider}


@app.get("/signals")
def signals(as_of: str | None = Query(default=None), top: int = Query(default=25, ge=1, le=500)) -> list[dict]:
    table = engine().signals(_month(as_of))[SIGNAL_FIELDS].head(top)
    return table.round(4).to_dict("records")


@app.post("/search")
def search(req: SearchRequest) -> list[dict]:
    params = req.model_dump(exclude={"query", "k"}, exclude_none=True)
    return [h.to_dict() for h in engine().index.search(req.query, k=req.k, **params)]


@app.post("/brief")
def brief(req: BriefRequest) -> dict:
    try:
        result = engine().brief(req.vehicle, _month(req.as_of))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.to_dict()


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    return engine().ask(req.question, **req.model_dump(exclude={"question"}, exclude_none=True))
