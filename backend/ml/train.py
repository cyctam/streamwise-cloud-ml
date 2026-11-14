from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.ml.hybrid import HybridRecommender, POSITIVE_WEIGHTS

ROOT = Path(__file__).resolve().parents[2]


def load_data(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = ("user_profiles.csv", "content_catalog.csv", "user_interactions.csv")
    missing = [name for name in required if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required dataset files in {data_dir}: {', '.join(missing)}")
    users, content, interactions = (pd.read_csv(data_dir / name) for name in required)
    return users, content, interactions


def _pair_events(interactions: pd.DataFrame) -> pd.DataFrame:
    positive = interactions[interactions.interaction_type.isin(POSITIVE_WEIGHTS)].copy()
    positive["weight"] = positive.interaction_type.map(POSITIVE_WEIGHTS).astype(float)
    return positive.groupby(["user_id", "content_id"], as_index=False).weight.sum()


def _per_user_holdout(pairs: pd.DataFrame, test_fraction: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    train_parts, test_parts = [], []
    for _, group in pairs.groupby("user_id", sort=True):
        group = group.sample(frac=1, random_state=int(rng.integers(0, 2**31 - 1)))
        if len(group) < 2:
            train_parts.append(group)
            continue
        test_count = max(1, int(round(len(group) * test_fraction)))
        test_count = min(test_count, len(group) - 1)
        test_parts.append(group.iloc[:test_count])
        train_parts.append(group.iloc[test_count:])
    train = pd.concat(train_parts, ignore_index=True) if train_parts else pairs.iloc[0:0]
    test = pd.concat(test_parts, ignore_index=True) if test_parts else pairs.iloc[0:0]
    return train, test


def _ranking_metrics(recommended: list[str], relevant: set[str], k: int) -> dict[str, float]:
    top = recommended[:k]
    hits = [1 if item in relevant else 0 for item in top]
    hit_count = sum(hits)
    dcg = sum(hit / np.log2(rank + 2) for rank, hit in enumerate(hits))
    ideal = sum(1 / np.log2(rank + 2) for rank in range(min(len(relevant), k)))
    return {
        "precision": hit_count / k,
        "recall": hit_count / max(len(relevant), 1),
        "ndcg": dcg / ideal if ideal else 0.0,
    }


def evaluate(users: pd.DataFrame, content: pd.DataFrame, interactions: pd.DataFrame, k: int = 10, seed: int = 42) -> dict[str, Any]:
    pairs = _pair_events(interactions)
    train_pairs, test_pairs = _per_user_holdout(pairs, test_fraction=0.2, seed=seed)
    train_interactions = train_pairs.rename(columns={"weight": "interaction_weight"}).copy()
    train_interactions["interaction_type"] = "play"
    model = HybridRecommender().fit(users, content, train_interactions)

    relevant_by_user = {
        str(user_id): set(group.content_id.astype(str))
        for user_id, group in test_pairs.groupby("user_id")
    }
    popularity_order = [
        content_id for content_id, _ in sorted(
            model.content_index.items(),
            key=lambda pair: model.popularity[pair[1]],
            reverse=True,
        )
    ]
    model_rows, baseline_rows = [], []
    catalog = set(content.content_id.astype(str))
    for user_id, relevant in relevant_by_user.items():
        if not relevant:
            continue
        hybrid = [row["content_id"] for row in model.recommend(user_id, k)]
        seen = model.seen_by_user.get(user_id, set())
        baseline = [item for item in popularity_order if item not in seen][:k]
        model_rows.append(_ranking_metrics(hybrid, relevant, k))
        baseline_rows.append(_ranking_metrics(baseline, relevant, k))

    def average(rows: list[dict[str, float]], key: str) -> float | None:
        return round(float(np.mean([row[key] for row in rows])), 4) if rows else None

    return {
        "evaluation_protocol": "Per-user holdout of unique positive user-item pairs; 80/20 split where possible.",
        "k": k,
        "seed": seed,
        "evaluated_users": len(model_rows),
        "train_positive_pairs": len(train_pairs),
        "holdout_positive_pairs": len(test_pairs),
        "catalog_items": len(catalog),
        "hybrid": {
            "precision_at_k": average(model_rows, "precision"),
            "recall_at_k": average(model_rows, "recall"),
            "ndcg_at_k": average(model_rows, "ndcg"),
        },
        "popularity_baseline": {
            "precision_at_k": average(baseline_rows, "precision"),
            "recall_at_k": average(baseline_rows, "recall"),
            "ndcg_at_k": average(baseline_rows, "ndcg"),
        },
    }


def _fingerprint(data_dir: Path) -> str:
    digest = hashlib.sha256()
    for name in ("user_profiles.csv", "content_catalog.csv", "user_interactions.csv"):
        digest.update((data_dir / name).read_bytes())
    return digest.hexdigest()


def train(data_dir: Path, artifact_dir: Path, seed: int = 42) -> dict[str, Any]:
    users, content, interactions = load_data(data_dir)
    evaluation = evaluate(users, content, interactions, k=10, seed=seed)
    model = HybridRecommender().fit(users, content, interactions)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with (artifact_dir / "hybrid_recommender.pkl").open("wb") as stream:
        pickle.dump(model, stream, protocol=pickle.HIGHEST_PROTOCOL)
    report = {
        **model.metrics(),
        **evaluation,
        "dataset_label": "synthetic benchmark",
        "dataset_fingerprint_sha256": _fingerprint(data_dir),
        "trained_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "training_seed": seed,
    }
    (artifact_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and evaluate the Streamwise hybrid recommender.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(train(args.data_dir, args.artifact_dir, args.seed), indent=2))
