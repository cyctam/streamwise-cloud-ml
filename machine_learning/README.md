# Machine Learning Pipeline

The maintained training and evaluation implementation lives in `backend/ml/`.

## Model

Streamwise uses a hybrid recommendation ranker with two independently computed signals:

- **Content-based filtering (45%)** — TF-IDF vectors over title, genre, content type, language, and studio metadata. A user's content profile is formed from weighted positive interactions.
- **Collaborative filtering (55%)** — TruncatedSVD latent factors learned from the sparse user-item interaction matrix.

The output is a relative ranking score. It is not a calibrated probability that a user will stream a title.

## Train and evaluate

From the repository root:

```bash
python -m backend.ml.train
```

The command reads the three CSV files in `data/raw/`, performs a deterministic per-user holdout split of unique positive user-item pairs, compares the hybrid ranker with a popularity baseline, and writes:

- `artifacts/hybrid_recommender.pkl`
- `artifacts/metrics.json`

The included dataset is synthetic. Evaluation metrics are benchmark results for this generated dataset and must not be presented as production model performance.

## Reproducibility

The default random seed is `42`. Override it with `--seed` when running controlled experiments. The metrics file records the dataset SHA-256 fingerprint, training seed, training timestamp, holdout protocol, and baseline comparison.
