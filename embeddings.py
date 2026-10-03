"""Dense embedding backends behind one small interface.

`lsa` fits TF IDF plus truncated SVD on the corpus itself. It needs no network and
no GPU, which keeps the reference run and the test suite fully reproducible offline.
`sentence_transformers` swaps in a pretrained transformer encoder when the optional
dependency and model weights are available.
"""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from skidsignal.index.text import STOP_WORDS


class LSAEmbedder:
    name = "lsa"

    def __init__(self, dim: int = 256, random_state: int = 7):
        self.dim = dim
        self.tfidf = TfidfVectorizer(
            sublinear_tf=True, min_df=3, max_df=0.6, max_features=150_000,
            stop_words=STOP_WORDS, dtype=np.float32,
        )
        self.svd = TruncatedSVD(n_components=dim, n_iter=5, random_state=random_state)

    def fit(self, texts: list[str]) -> np.ndarray:
        if len(texts) < 200:  # tiny corpora (tests, demos) cannot afford frequency pruning
            self.tfidf.set_params(min_df=1, max_df=1.0)
        matrix = self.tfidf.fit_transform(texts)
        self.svd.n_components = max(2, min(self.dim, matrix.shape[1] - 1, matrix.shape[0] - 1))
        return self._finish(self.svd.fit_transform(matrix))

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._finish(self.svd.transform(self.tfidf.transform(texts)))

    @staticmethod
    def _finish(dense: np.ndarray) -> np.ndarray:
        return normalize(dense).astype(np.float32)


class SentenceTransformerEmbedder:
    name = "sentence_transformers"

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # optional dependency

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def fit(self, texts: list[str]) -> np.ndarray:
        return self.encode(texts)

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)

    def __getstate__(self):  # the model is reloaded by name, never pickled
        return {"model_name": self.model_name}

    def __setstate__(self, state):
        self.__init__(state["model_name"])


def make_embedder(retrieval_cfg) -> LSAEmbedder | SentenceTransformerEmbedder:
    if retrieval_cfg.embedding_backend == "sentence_transformers":
        return SentenceTransformerEmbedder(retrieval_cfg.sentence_transformer_model)
    return LSAEmbedder(dim=retrieval_cfg.lsa_dim)
