"""Hybrid retrieval index: BM25 plus dense vectors, fused with reciprocal rank fusion.

Search supports metadata filters (source, make, vehicle family, date range), which is
what lets a brief be assembled strictly from evidence that existed on the as of date,
and optional maximal marginal relevance so an evidence set is not ten copies of the
same story.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from skidsignal.config import Settings, get_logger
from skidsignal.index.bm25 import BM25
from skidsignal.index.embeddings import make_embedder

log = get_logger(__name__)


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    source: str
    title: str
    text: str
    score: float
    bm25_rank: int | None
    dense_rank: int | None
    date: str | None
    model_year: int | None

    def to_dict(self) -> dict:
        return asdict(self)


class HybridIndex:
    def __init__(self, meta: pd.DataFrame, bm25: BM25, embedder, vectors: np.ndarray, cfg: Settings):
        self.meta, self.bm25, self.embedder, self.vectors, self.cfg = meta.reset_index(drop=True), bm25, embedder, vectors, cfg
        self._source = self.meta["source"].to_numpy(dtype=object)
        self._date = self.meta["date"].to_numpy(dtype="datetime64[ns]")
        self._abs = self.meta["is_abs"].to_numpy(dtype=bool)
        self._brake = self.meta["is_brake"].to_numpy(dtype=bool)
        self._doc = self.meta["doc_id"].to_numpy(dtype=object)
        self.reranker = None

    # ---------------------------------------------------------------- build / io
    @classmethod
    def build(cls, kb: pd.DataFrame, cfg: Settings) -> "HybridIndex":
        texts = (kb["title"].fillna("") + ". " + kb["text"]).tolist()
        r = cfg.retrieval
        log.info("fitting BM25 on %d chunks", len(texts))
        bm25 = BM25(r.bm25_k1, r.bm25_b).fit(texts)
        log.info("fitting %s embeddings", r.embedding_backend)
        embedder = make_embedder(r)
        vectors = embedder.fit(texts)
        return cls(kb, bm25, embedder, vectors, cfg)

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.meta.to_parquet(directory / "meta.parquet", index=False)
        np.save(directory / "vectors.npy", self.vectors)
        joblib.dump({"bm25": self.bm25, "embedder": self.embedder}, directory / "models.joblib", compress=3)

    @classmethod
    def load(cls, directory: Path, cfg: Settings) -> "HybridIndex":
        directory = Path(directory)
        models = joblib.load(directory / "models.joblib")
        return cls(pd.read_parquet(directory / "meta.parquet"), models["bm25"], models["embedder"],
                   np.load(directory / "vectors.npy"), cfg)

    # -------------------------------------------------------------------- search
    def _mask(self, sources, make, vehicle, date_from, date_to, abs_only, brake_only, exclude_docs) -> np.ndarray:
        mask = np.ones(len(self.meta), dtype=bool)
        if sources:
            mask &= np.isin(self._source, list(sources))
        if make:
            mask &= self.meta["makes"].str.contains(f"|{make.upper()}|", regex=False).to_numpy()
        if vehicle:
            mask &= self.meta["vehicles"].str.contains(f"|{vehicle.upper()}|", regex=False).to_numpy()
        if date_from is not None:
            mask &= np.isnat(self._date) | (self._date >= np.datetime64(pd.Timestamp(date_from)))
        if date_to is not None:
            mask &= np.isnat(self._date) | (self._date <= np.datetime64(pd.Timestamp(date_to)))
        if abs_only:
            mask &= self._abs
        if brake_only:
            mask &= self._brake
        if exclude_docs:
            mask &= ~np.isin(self._doc, list(exclude_docs))
        return mask

    @staticmethod
    def _top(scores: np.ndarray, mask: np.ndarray, n: int) -> np.ndarray:
        scores = np.where(mask, scores, -np.inf)
        n = min(n, int(mask.sum()))
        if n <= 0:
            return np.empty(0, dtype=int)
        idx = np.argpartition(-scores, n - 1)[:n]
        idx = idx[np.argsort(-scores[idx], kind="stable")]
        return idx[np.isfinite(scores[idx]) & (scores[idx] > 0)]

    def search(
        self, query: str, k: int | None = None, mode: str = "hybrid", sources=None, make: str | None = None,
        vehicle: str | None = None, date_from=None, date_to=None, abs_only: bool = False, brake_only: bool = False, exclude_docs=None,
        diversify: bool = True, weights: tuple[float, float] | None = None,
    ) -> list[Hit]:
        r = self.cfg.retrieval
        k = k or r.top_k
        mask = self._mask(sources, make, vehicle, date_from, date_to, abs_only, brake_only, exclude_docs)
        if not mask.any():
            return []
        pool = max(r.candidate_k, 4 * k)
        bm25_top = self._top(self.bm25.scores(query), mask, pool) if mode in ("hybrid", "bm25") else np.empty(0, int)
        dense_top = (
            self._top(self.vectors @ self.embedder.encode([query])[0], mask, pool)
            if mode in ("hybrid", "dense") else np.empty(0, int)
        )
        bm25_rank = {int(i): rank for rank, i in enumerate(bm25_top, 1)}
        dense_rank = {int(i): rank for rank, i in enumerate(dense_top, 1)}
        w_bm25, w_dense = weights or (r.rrf_weight_bm25, r.rrf_weight_dense)
        if mode != "hybrid":  # single channel modes ignore the fusion weights
            w_bm25 = w_dense = 1.0
        fused: dict[int, float] = {}
        for ranks, weight in ((bm25_rank, w_bm25), (dense_rank, w_dense)):
            if weight <= 0:
                continue
            for i, rank in ranks.items():
                fused[i] = fused.get(i, 0.0) + weight / (r.rrf_k + rank)
        ordered = sorted(fused, key=lambda i: (-fused[i], i))

        # keep the best chunk per document
        seen, candidates = set(), []
        for i in ordered:
            if self._doc[i] not in seen:
                seen.add(self._doc[i])
                candidates.append(i)
        if self.reranker is not None and candidates:
            candidates = self.reranker.rerank(query, candidates[: 4 * k], self.meta["text"])
        chosen = self._mmr(candidates, fused, k, r.mmr_lambda) if diversify and r.mmr_lambda < 1.0 else candidates[:k]
        return [self._hit(i, fused[i], bm25_rank.get(i), dense_rank.get(i)) for i in chosen]

    def _mmr(self, candidates: list[int], fused: dict[int, float], k: int, lam: float) -> list[int]:
        candidates = candidates[: 4 * k]
        if len(candidates) <= 1:
            return candidates
        relevance = np.array([fused[i] for i in candidates])
        relevance = relevance / relevance.max()
        vectors = self.vectors[candidates]
        similarity = vectors @ vectors.T
        selected = [0]
        while len(selected) < min(k, len(candidates)):
            redundancy = similarity[:, selected].max(axis=1)
            objective = lam * relevance - (1.0 - lam) * redundancy
            objective[selected] = -np.inf
            selected.append(int(np.argmax(objective)))
        return [candidates[j] for j in selected]

    def _hit(self, i: int, score: float, bm25_rank, dense_rank) -> Hit:
        row = self.meta.iloc[i]
        date = None if pd.isna(row["date"]) else str(pd.Timestamp(row["date"]).date())
        year = None if pd.isna(row["model_year"]) else int(row["model_year"])
        return Hit(row["chunk_id"], row["doc_id"], row["source"], row["title"], row["text"], float(score),
                   bm25_rank, dense_rank, date, year)

    def get_document(self, doc_id: str) -> dict | None:
        rows = self.meta[self.meta["doc_id"] == doc_id]
        if rows.empty:
            return None
        first = rows.iloc[0]
        return {"doc_id": doc_id, "source": first["source"], "title": first["title"], "text": " ".join(rows["text"])}


class CrossEncoderReranker:
    """Optional second stage scorer. Needs the sentence_transformers extra."""

    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder  # optional dependency

        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[int], texts: pd.Series) -> list[int]:
        scores = self.model.predict([(query, texts.iloc[i]) for i in candidates])
        return [candidates[j] for j in np.argsort(-np.asarray(scores))]


def build_index(cfg: Settings) -> HybridIndex:
    kb = pd.read_parquet(cfg.path("processed") / "knowledge_base.parquet")
    index = HybridIndex.build(kb, cfg)
    index.save(cfg.path("index"))
    return index


def load_index(cfg: Settings) -> HybridIndex:
    index = HybridIndex.load(cfg.path("index"), cfg)
    if cfg.retrieval.reranker == "cross_encoder":
        index.reranker = CrossEncoderReranker(cfg.retrieval.cross_encoder_model)
    return index
