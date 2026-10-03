"""Okapi BM25 over a sparse term matrix. Scoring a query is one sparse column sum."""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer

from skidsignal.index.text import STOP_WORDS

TOKEN_PATTERN = r"(?u)\b[a-z0-9][a-z0-9]+\b"


class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.vectorizer = CountVectorizer(lowercase=True, token_pattern=TOKEN_PATTERN, stop_words=STOP_WORDS)
        self.weights: sp.csc_matrix | None = None

    def fit(self, texts: list[str]) -> "BM25":
        tf = self.vectorizer.fit_transform(texts).astype(np.float32).tocsr()
        n_docs = tf.shape[0]
        doc_len = np.asarray(tf.sum(axis=1)).ravel()
        avg_len = max(float(doc_len.mean()), 1e-9)
        df = np.bincount(tf.indices, minlength=tf.shape[1])
        idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
        rows = np.repeat(np.arange(n_docs), np.diff(tf.indptr))
        norm = self.k1 * (1.0 - self.b + self.b * doc_len[rows] / avg_len)
        data = idf[tf.indices] * tf.data * (self.k1 + 1.0) / (tf.data + norm)
        self.weights = sp.csr_matrix((data.astype(np.float32), tf.indices, tf.indptr), shape=tf.shape).tocsc()
        self._analyzer = None
        return self

    def tokenize(self, text: str) -> list[str]:
        if getattr(self, "_analyzer", None) is None:
            self._analyzer = self.vectorizer.build_analyzer()
        return self._analyzer(text)

    def scores(self, query: str) -> np.ndarray:
        vocab = self.vectorizer.vocabulary_
        terms = sorted({vocab[t] for t in self.tokenize(query) if t in vocab})
        if not terms:
            return np.zeros(self.weights.shape[0], dtype=np.float32)
        return np.asarray(self.weights[:, terms].sum(axis=1)).ravel()

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_analyzer"] = None
        return state
