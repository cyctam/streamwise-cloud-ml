from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler

POSITIVE_WEIGHTS = {"play": 1.0, "complete": 2.0, "like": 3.0, "add_to_watchlist": 1.5}


@dataclass
class HybridRecommender:
    """Hybrid content/collaborative ranker. Scores are relative, not probabilities."""

    content_weight: float = 0.45
    collaborative_weight: float = 0.55
    random_state: int = 42

    def __post_init__(self) -> None:
        if not np.isclose(self.content_weight + self.collaborative_weight, 1.0):
            raise ValueError("content_weight and collaborative_weight must sum to 1")

    def fit(self, users: pd.DataFrame, content: pd.DataFrame, interactions: pd.DataFrame) -> "HybridRecommender":
        required_users = {"user_id", "preferred_genre"}
        required_content = {"content_id", "title", "genre", "content_type", "language", "studio"}
        required_interactions = {"user_id", "content_id", "interaction_type"}
        for frame, required, label in (
            (users, required_users, "users"),
            (content, required_content, "content"),
            (interactions, required_interactions, "interactions"),
        ):
            missing = required - set(frame.columns)
            if missing:
                raise ValueError(f"{label} dataset is missing required columns: {sorted(missing)}")

        self.users = users.copy().reset_index(drop=True)
        self.content = content.copy().reset_index(drop=True)
        self.interactions = interactions.copy()
        self.user_ids = self.users.user_id.astype(str).tolist()
        self.content_ids = self.content.content_id.astype(str).tolist()
        if len(set(self.user_ids)) != len(self.user_ids) or len(set(self.content_ids)) != len(self.content_ids):
            raise ValueError("user_id and content_id values must be unique in their dimension tables")
        self.user_index = {value: index for index, value in enumerate(self.user_ids)}
        self.content_index = {value: index for index, value in enumerate(self.content_ids)}
        self.user_genres = dict(zip(self.users.user_id.astype(str), self.users.preferred_genre.fillna("").astype(str)))

        text_fields = ("title", "genre", "content_type", "language", "studio")
        self.content_text = self.content[list(text_fields)].fillna("").astype(str).agg(" ".join, axis=1)
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        self.content_matrix = self.vectorizer.fit_transform(self.content_text)

        positive = self.interactions[self.interactions.interaction_type.isin(POSITIVE_WEIGHTS)].copy()
        positive["weight"] = (
            pd.to_numeric(positive["interaction_weight"], errors="coerce").fillna(0.0)
            if "interaction_weight" in positive.columns
            else positive.interaction_type.map(POSITIVE_WEIGHTS).astype(float)
        )
        positive["user_id"] = positive.user_id.astype(str)
        positive["content_id"] = positive.content_id.astype(str)
        positive = positive.groupby(["user_id", "content_id"], as_index=False).weight.sum()
        rows = positive.user_id.map(self.user_index)
        cols = positive.content_id.map(self.content_index)
        valid = rows.notna() & cols.notna()
        self.user_item = csr_matrix(
            (
                np.log1p(positive.loc[valid, "weight"].to_numpy(dtype=float)),
                (rows.loc[valid].to_numpy(dtype=int), cols.loc[valid].to_numpy(dtype=int)),
            ),
            shape=(len(self.user_ids), len(self.content_ids)),
        )
        self.user_item.sum_duplicates()

        max_components = min(self.user_item.shape) - 1
        self.svd = None
        self.collaborative_scores = np.zeros(self.user_item.shape, dtype=float)
        if max_components >= 2 and self.user_item.nnz:
            self.svd = TruncatedSVD(n_components=min(32, max_components), random_state=self.random_state)
            user_factors = self.svd.fit_transform(self.user_item)
            self.collaborative_scores = user_factors @ self.svd.components_
        self.collaborative_scaler = MinMaxScaler()
        self.collaborative_scores = self.collaborative_scaler.fit_transform(self.collaborative_scores)
        self.popularity = self._scale(np.asarray(self.user_item.sum(axis=0)).ravel())
        self.user_genre_affinity = self._build_genre_affinity(positive)
        self.seen_by_user = {
            str(user_id): set(group.content_id.astype(str))
            for user_id, group in self.interactions.groupby("user_id")
        }
        self.is_fitted = True
        return self

    @staticmethod
    def _scale(values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        if values.size == 0:
            return values
        low, high = float(np.min(values)), float(np.max(values))
        if high <= low:
            return np.zeros_like(values)
        return (values - low) / (high - low)

    def _build_genre_affinity(self, positive: pd.DataFrame) -> dict[str, dict[str, float]]:
        merged = positive.merge(self.content[["content_id", "genre"]], on="content_id", how="inner")
        result: dict[str, dict[str, float]] = {}
        for user_id, group in merged.groupby("user_id"):
            weighted = group.groupby("genre").weight.sum()
            total = float(weighted.sum()) or 1.0
            result[str(user_id)] = (weighted / total).to_dict()
        return result

    def _content_scores(self, user_id: str) -> np.ndarray:
        index = self.user_index.get(user_id)
        if index is None:
            return self.popularity.copy()
        row = self.user_item.getrow(index)
        if row.nnz:
            profile = row @ self.content_matrix
            scores = (profile @ self.content_matrix.T).toarray().ravel()
            return self._scale(scores)

        preferred_genre = self.user_genres.get(user_id, "")
        if preferred_genre:
            genre_match = self.content.genre.astype(str).eq(preferred_genre).to_numpy(dtype=float)
            return self._scale(genre_match + self.popularity * 0.05)
        return self.popularity.copy()

    def _collaborative_scores(self, user_id: str) -> np.ndarray:
        index = self.user_index.get(user_id)
        if index is None:
            return self.popularity.copy()
        if self.user_item.getrow(index).nnz == 0:
            return self.popularity.copy()
        return self.collaborative_scores[index].copy()

    def score(self, user_id: str, content_id: str) -> dict[str, Any]:
        if not getattr(self, "is_fitted", False):
            raise RuntimeError("Model has not been trained")
        if user_id not in self.user_index:
            raise KeyError(f"Unknown user_id: {user_id}")
        if content_id not in self.content_index:
            raise KeyError(f"Unknown content_id: {content_id}")
        item_index = self.content_index[content_id]
        content_score = float(self._content_scores(user_id)[item_index])
        collaborative_score = float(self._collaborative_scores(user_id)[item_index])
        hybrid_score = self.content_weight * content_score + self.collaborative_weight * collaborative_score
        item = self.content.iloc[item_index]
        affinity = self.user_genre_affinity.get(user_id, {})
        reasons = []
        if affinity.get(str(item.genre), 0) > 0:
            reasons.append(f"Genre affinity: {item.genre}")
        if collaborative_score >= 0.65:
            reasons.append("Strong collaborative interaction signal")
        if content_score >= 0.65:
            reasons.append("High similarity to previously engaged content")
        if not reasons:
            reasons.append("Combined ranking from available profile and interaction signals")
        return {
            "user_id": user_id,
            "content_id": content_id,
            "title": str(item.title),
            "genre": str(item.genre),
            "content_type": str(item.content_type),
            "hybrid_score": round(float(hybrid_score), 4),
            "content_score": round(content_score, 4),
            "collaborative_score": round(collaborative_score, 4),
            "score_type": "relative_ranking_score_not_probability",
            "reasons": reasons,
        }

    def recommend(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        if not getattr(self, "is_fitted", False):
            raise RuntimeError("Model has not been trained")
        if user_id not in self.user_index:
            raise KeyError(f"Unknown user_id: {user_id}")
        content_scores = self._content_scores(user_id)
        collaborative_scores = self._collaborative_scores(user_id)
        scores = self.content_weight * content_scores + self.collaborative_weight * collaborative_scores
        for content_id in self.seen_by_user.get(user_id, set()):
            index = self.content_index.get(content_id)
            if index is not None:
                scores[index] = -1.0
        order = np.argsort(scores)[::-1]
        results = []
        for index in order:
            if scores[index] < 0 or len(results) >= limit:
                break
            result = self.score(user_id, self.content_ids[int(index)])
            result["rank"] = len(results) + 1
            results.append(result)
        return results

    def metrics(self) -> dict[str, Any]:
        return {
            "algorithm": "Hybrid TF-IDF + TruncatedSVD",
            "content_weight": self.content_weight,
            "collaborative_weight": self.collaborative_weight,
            "users": len(self.user_ids),
            "items": len(self.content_ids),
            "positive_user_item_pairs": int(self.user_item.nnz),
            "latent_factors": int(self.svd.n_components) if self.svd is not None else 0,
            "score_semantics": "Relative ranking score; not a calibrated probability.",
        }
