"""Generate a reproducible synthetic streaming dataset for local ML experiments.

The generated records are synthetic and must never be represented as production user data.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

GENRES = ["Action", "Comedy", "Drama", "Horror", "Romance", "Sci-Fi", "Documentary", "Thriller"]
TYPES = ["Movie", "Series", "Music", "Podcast"]
LANGUAGES = ["Indonesian", "English", "Korean", "Japanese", "Spanish"]
STUDIOS = ["Northstar", "Open Frame", "Atlas Studios", "A24", "Meridian", "Horizon Media"]
EVENTS = ["play", "complete", "like", "add_to_watchlist", "skip"]


def generate(output: Path, seed: int = 42, users_count: int = 500, content_count: int = 240) -> dict[str, int]:
    rng = np.random.default_rng(seed)
    output.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp("2026-11-01")

    users = []
    preferences: dict[str, str] = {}
    for i in range(1, users_count + 1):
        user_id = f"user_{i:05d}"
        preferred = str(rng.choice(GENRES))
        preferences[user_id] = preferred
        streams = int(rng.integers(8, 260))
        users.append({
            "user_id": user_id,
            "registration_date": (now - pd.Timedelta(days=int(rng.integers(30, 900)))).date().isoformat(),
            "age": int(rng.integers(18, 66)),
            "location_city": str(rng.choice(["Jakarta", "Bandung", "Surabaya", "Depok", "Yogyakarta", "Medan"])),
            "subscription_plan": str(rng.choice(["Free", "Basic", "Standard", "Premium"], p=[.35, .25, .25, .15])),
            "total_streams": streams,
            "customer_segment": "Power User" if streams >= 180 else "Regular" if streams >= 80 else "Casual",
            "preferred_genre": preferred,
        })
    users_df = pd.DataFrame(users)

    content = []
    for i in range(1, content_count + 1):
        genre = str(rng.choice(GENRES))
        kind = str(rng.choice(TYPES, p=[.38, .32, .18, .12]))
        content.append({
            "content_id": f"content_{i:05d}",
            "title": f"{genre} {kind} {i:03d}",
            "content_type": kind,
            "genre": genre,
            "language": str(rng.choice(LANGUAGES)),
            "studio": str(rng.choice(STUDIOS)),
            "duration_minutes": int(rng.integers(4, 181)),
            "avg_rating": round(float(rng.uniform(2.8, 4.9)), 2),
            "release_date": (now - pd.Timedelta(days=int(rng.integers(0, 1800)))).date().isoformat(),
        })
    content_df = pd.DataFrame(content)

    # Each user sees more content from their latent preferred genre, creating
    # learnable collaborative and content signals without pretending data is real.
    content_by_genre = {g: content_df[content_df.genre == g].content_id.to_numpy() for g in GENRES}
    all_content = content_df.content_id.to_numpy()
    interactions = []
    for user_id, preferred in preferences.items():
        count = int(rng.integers(35, 76))
        for _ in range(count):
            if rng.random() < .62:
                content_id = str(rng.choice(content_by_genre[preferred]))
            else:
                content_id = str(rng.choice(all_content))
            item_genre = content_df.loc[content_df.content_id == content_id, "genre"].iloc[0]
            affinity = .72 if item_genre == preferred else .28
            event_probs = [0.48, 0.20, 0.12, 0.08, 0.12] if affinity > .5 else [0.36, 0.12, 0.08, 0.06, 0.38]
            event = str(rng.choice(EVENTS, p=event_probs))
            ts = now - pd.Timedelta(days=int(rng.integers(0, 180)), hours=int(rng.integers(0, 24)))
            interactions.append({
                "interaction_id": f"evt_{len(interactions) + 1:07d}",
                "user_id": user_id,
                "content_id": content_id,
                "interaction_type": event,
                "timestamp": ts.isoformat(),
                "watch_duration_seconds": int(rng.integers(30, 7200)),
                "device_type": str(rng.choice(["mobile", "desktop", "smart_tv", "tablet"])),
            })
    interactions_df = pd.DataFrame(interactions).sort_values("timestamp")

    users_df.to_csv(output / "user_profiles.csv", index=False)
    content_df.to_csv(output / "content_catalog.csv", index=False)
    interactions_df.to_csv(output / "user_interactions.csv", index=False)
    summary = {
        "users": len(users_df),
        "content": len(content_df),
        "interactions": len(interactions_df),
    }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--users", type=int, default=500)
    parser.add_argument("--content", type=int, default=240)
    args = parser.parse_args()
    print(generate(args.output, args.seed, args.users, args.content))
