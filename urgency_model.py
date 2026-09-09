"""
urgency_model.py
-----------------
Trains a regression model (XGBoost if available, else scikit-learn's
GradientBoostingRegressor as a drop-in fallback) that predicts a
Maintenance Urgency Score (0-100) for a track/signal/S&T asset from its
condition-monitoring features, and applies it to rank pending
maintenance jobs.

The model is trained on a larger "historical" dataset with observed
outcomes (see data_generator.generate_historical_training_data) and then
used to score the smaller set of *current* pending jobs, which do not
have a ground-truth label -- exactly like a real deployment where you
learn from past inspection/failure records to prioritize today's backlog.

Run directly to train, evaluate, and save the model:
    python urgency_model.py
"""

from __future__ import annotations

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

try:
    from xgboost import XGBRegressor

    _HAS_XGB = True
except Exception:  # pragma: no cover - fallback path (import error or native lib load failure)
    from sklearn.ensemble import GradientBoostingRegressor

    _HAS_XGB = False

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "urgency_model.joblib")

NUMERIC_FEATURES = [
    "asset_age_years",
    "past_failures",
    "current_condition_score",
    "last_maintained_days_ago",
    "traffic_load_trains_per_day",
]
CATEGORICAL_FEATURES = ["asset_type"]
FEATURE_COLS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET_COL = "observed_urgency_score"


def _build_pipeline() -> Pipeline:
    """Build the preprocessing + regressor pipeline."""
    preprocess = ColumnTransformer(
        transformers=[
            ("num", "passthrough", NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    if _HAS_XGB:
        regressor = XGBRegressor(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=42,
        )
    else:
        regressor = GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.05, random_state=42)
    return Pipeline(steps=[("preprocess", preprocess), ("regressor", regressor)])


def train_urgency_model(historical_df: pd.DataFrame, test_size: float = 0.2, seed: int = 42):
    """Train the urgency regressor on historical labeled data.

    Returns (fitted_pipeline, metrics_dict, feature_importance_df).
    """
    X = historical_df[FEATURE_COLS]
    y = historical_df[TARGET_COL]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=seed)

    pipeline = _build_pipeline()
    pipeline.fit(X_train, y_train)

    preds = pipeline.predict(X_test)
    metrics = {
        "mae": round(mean_absolute_error(y_test, preds), 3),
        "r2": round(r2_score(y_test, preds), 3),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "backend": "XGBoost" if _HAS_XGB else "GradientBoostingRegressor (sklearn fallback)",
    }

    feature_importance = _extract_feature_importance(pipeline)
    return pipeline, metrics, feature_importance


def _extract_feature_importance(pipeline: Pipeline) -> pd.DataFrame:
    """Pull out feature importances mapped back to human-readable names."""
    ohe: OneHotEncoder = pipeline.named_steps["preprocess"].named_transformers_["cat"]
    cat_names = list(ohe.get_feature_names_out(CATEGORICAL_FEATURES))
    all_names = NUMERIC_FEATURES + cat_names
    importances = pipeline.named_steps["regressor"].feature_importances_
    fi = pd.DataFrame({"feature": all_names, "importance": importances})
    return fi.sort_values("importance", ascending=False).reset_index(drop=True)


def predict_urgency(pipeline: Pipeline, jobs_df: pd.DataFrame) -> pd.DataFrame:
    """Score pending maintenance jobs / assets with the trained model.

    Adds a `predicted_urgency_score` column (0-100, higher = more urgent)
    and an `urgency_rank` column (1 = most urgent).
    """
    out = jobs_df.copy()
    preds = pipeline.predict(out[FEATURE_COLS])
    out["predicted_urgency_score"] = np.clip(preds, 0, 100).round(2)
    out["urgency_rank"] = out["predicted_urgency_score"].rank(ascending=False, method="first").astype(int)
    return out.sort_values("urgency_rank").reset_index(drop=True)


def explain_urgency(row: pd.Series) -> str:
    """Produce a short human-readable justification for a job's urgency
    score, driven by which raw features look most concerning."""
    reasons = []
    if row["current_condition_score"] < 40:
        reasons.append(f"poor condition ({row['current_condition_score']:.0f}/100)")
    if row["last_maintained_days_ago"] > 365:
        reasons.append(f"not maintained in {int(row['last_maintained_days_ago'])} days")
    if row["past_failures"] >= 4:
        reasons.append(f"{int(row['past_failures'])} past failures")
    if row["asset_age_years"] > 25:
        reasons.append(f"aging asset ({row['asset_age_years']:.0f} yrs)")
    if row["traffic_load_trains_per_day"] > 150:
        reasons.append("high traffic section")
    if not reasons:
        reasons.append("routine wear indicators")
    return f"Urgency {row['predicted_urgency_score']:.1f}/100 — " + "; ".join(reasons)


def save_model(pipeline: Pipeline, path: str = MODEL_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(pipeline, path)
    return path


def load_model(path: str = MODEL_PATH) -> Pipeline:
    return joblib.load(path)


if __name__ == "__main__":
    from data_generator import DATA_DIR

    hist_path = os.path.join(DATA_DIR, "historical.csv")
    if not os.path.exists(hist_path):
        raise SystemExit("Run `python data_generator.py` first to generate data/historical.csv")

    historical = pd.read_csv(hist_path)
    pipeline, metrics, fi = train_urgency_model(historical)
    print("Training metrics:", metrics)
    print("\nFeature importance:\n", fi.to_string(index=False))
    path = save_model(pipeline)
    print(f"\nSaved model to {path}")
