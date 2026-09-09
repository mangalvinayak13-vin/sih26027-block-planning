"""
data_generator.py
------------------
Synthesizes realistic sample data for the AI-Powered Automatic Block
Planning prototype (SIH26027): railway sections, running train
timetables, track/signal/S&T assets, pending maintenance jobs, and a
larger historical dataset used to train the urgency ML model.

All data is randomly generated but constrained to look like plausible
Indian Railways operational data (section names, block windows in
minutes-since-midnight, asset types, etc).

Run directly to (re)generate the CSVs used by the rest of the app:
    python data_generator.py
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

ASSET_TYPES = ["Track (Rail/Ballast)", "Signal", "OHE (Overhead Equipment)", "S&T (Points/Crossing)"]
JOB_TYPE_BY_ASSET = {
    "Track (Rail/Ballast)": "Engineering - Track Renewal/Tamping",
    "Signal": "Signal - Relay/Cable Maintenance",
    "OHE (Overhead Equipment)": "Electrical - OHE Inspection/Repair",
    "S&T (Points/Crossing)": "S&T - Point Machine Overhaul",
}
TRAIN_TYPES = ["Rajdhani/Superfast", "Mail/Express", "Passenger", "Freight/Goods", "MEMU/DEMU"]

SECTION_NAMES = [
    ("NDLS-GZB", "New Delhi - Ghaziabad", "Northern Railway"),
    ("GZB-MB", "Ghaziabad - Moradabad", "Northern Railway"),
    ("CSMT-KYN", "CSMT Mumbai - Kalyan", "Central Railway"),
    ("KYN-PUNE", "Kalyan - Pune", "Central Railway"),
    ("HWH-BWN", "Howrah - Barddhaman", "Eastern Railway"),
    ("MAS-AJJ", "Chennai Central - Arakkonam", "Southern Railway"),
    ("SBC-JTJ", "Bengaluru - Jolarpettai", "South Western Railway"),
    ("BPL-ET", "Bhopal - Itarsi", "West Central Railway"),
]

DAY_MINUTES = 24 * 60


def generate_sections(num_sections: int = 6, seed: int = 42) -> pd.DataFrame:
    """Generate a table of railway sections (a section = a stretch of line
    between two stations managed as one maintenance/traffic unit)."""
    rng = np.random.default_rng(seed)
    chosen = SECTION_NAMES[:num_sections]
    rows = []
    for i, (code, name, zone) in enumerate(chosen):
        rows.append(
            {
                "section_id": f"SEC{i+1:02d}",
                "section_code": code,
                "section_name": name,
                "zone": zone,
                "num_tracks": int(rng.choice([1, 2, 2, 2, 3])),
                "length_km": int(rng.integers(25, 140)),
            }
        )
    return pd.DataFrame(rows)


def generate_trains(sections_df: pd.DataFrame, trains_per_section=(14, 26), seed: int = 42) -> pd.DataFrame:
    """Generate a same-day running timetable per section.

    Trains are laid out as sequential, non-overlapping occupancy windows
    on the section (a simplifying assumption of an effectively single
    "line capacity" resource per section that a maintenance block also
    contends for), each with a small randomized gap before the next.
    Times are stored as minutes-since-midnight (0-1440).
    """
    rng = np.random.default_rng(seed + 1)
    rows = []
    train_counter = 12000
    for _, sec in sections_df.iterrows():
        n_trains = int(rng.integers(*trains_per_section))
        t = int(rng.integers(0, 45))  # start slightly after midnight
        for _ in range(n_trains):
            gap = int(rng.integers(5, 55))
            t += gap
            if t >= DAY_MINUTES - 10:
                break
            train_type = rng.choice(TRAIN_TYPES, p=[0.12, 0.28, 0.2, 0.3, 0.1])
            duration = {
                "Rajdhani/Superfast": (4, 9),
                "Mail/Express": (5, 12),
                "Passenger": (6, 14),
                "Freight/Goods": (10, 25),
                "MEMU/DEMU": (4, 10),
            }[train_type]
            dur = int(rng.integers(*duration))
            dep = t
            arr = min(t + dur, DAY_MINUTES - 1)
            train_counter += 1
            rows.append(
                {
                    "train_id": f"T{train_counter}",
                    "train_no": train_counter,
                    "section_id": sec["section_id"],
                    "train_type": train_type,
                    "dep_min": dep,
                    "arr_min": arr,
                    "duration_min": arr - dep,
                }
            )
            t = arr
    return pd.DataFrame(rows).sort_values(["section_id", "dep_min"]).reset_index(drop=True)


def _feature_frame(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Draw a batch of raw asset-condition features shared by both the
    historical training set and the current live asset table."""
    return pd.DataFrame(
        {
            "asset_age_years": rng.uniform(0.5, 40, n).round(1),
            "past_failures": rng.poisson(2.2, n),
            "current_condition_score": rng.uniform(10, 100, n).round(1),  # higher = better health
            "last_maintained_days_ago": rng.integers(5, 730, n),
            "traffic_load_trains_per_day": rng.integers(15, 220, n),
        }
    )


def generate_assets(sections_df: pd.DataFrame, assets_per_section=(8, 16), seed: int = 42) -> pd.DataFrame:
    """Generate the current live track/signal/S&T asset register with
    condition-monitoring features used as ML inputs."""
    rng = np.random.default_rng(seed + 2)
    rows = []
    asset_counter = 0
    for _, sec in sections_df.iterrows():
        n_assets = int(rng.integers(*assets_per_section))
        feats = _feature_frame(n_assets, rng)
        asset_types = rng.choice(ASSET_TYPES, n_assets)
        for i in range(n_assets):
            asset_counter += 1
            row = {
                "asset_id": f"AST{asset_counter:04d}",
                "section_id": sec["section_id"],
                "asset_type": asset_types[i],
            }
            row.update(feats.iloc[i].to_dict())
            rows.append(row)
    return pd.DataFrame(rows)


def generate_maintenance_jobs(assets_df: pd.DataFrame, fraction_pending=0.55, seed: int = 42) -> pd.DataFrame:
    """Turn a subset of assets (those due for attention) into pending
    maintenance jobs that the CP-SAT scheduler must try to fit into
    track-possession windows."""
    rng = np.random.default_rng(seed + 3)
    n_pending = max(1, int(len(assets_df) * fraction_pending))
    # bias selection towards worse-condition / longer-neglected assets, like a real backlog would
    weight = (100 - assets_df["current_condition_score"]) + assets_df["last_maintained_days_ago"] / 10
    prob = (weight / weight.sum()).to_numpy()
    idx = rng.choice(assets_df.index.to_numpy(), size=n_pending, replace=False, p=prob)
    picked = assets_df.loc[idx]

    rows = []
    for j, (_, a) in enumerate(picked.iterrows(), start=1):
        job_type = JOB_TYPE_BY_ASSET[a["asset_type"]]
        duration = {
            "Track (Rail/Ballast)": (60, 180),
            "Signal": (45, 120),
            "OHE (Overhead Equipment)": (45, 150),
            "S&T (Points/Crossing)": (30, 90),
        }[a["asset_type"]]
        est_duration = int(rng.integers(*duration))
        rows.append(
            {
                "job_id": f"JOB{j:04d}",
                "asset_id": a["asset_id"],
                "section_id": a["section_id"],
                "asset_type": a["asset_type"],
                "job_type": job_type,
                "estimated_duration_min": est_duration,
                "block_type": "Line Block" if a["asset_type"] != "OHE (Overhead Equipment)" else "Power Block",
                "asset_age_years": a["asset_age_years"],
                "past_failures": a["past_failures"],
                "current_condition_score": a["current_condition_score"],
                "last_maintained_days_ago": a["last_maintained_days_ago"],
                "traffic_load_trains_per_day": a["traffic_load_trains_per_day"],
            }
        )
    return pd.DataFrame(rows)


def true_urgency_formula(df: pd.DataFrame, rng: np.random.Generator | None = None, noise_std: float = 6.0) -> np.ndarray:
    """Ground-truth (hidden, real-world) urgency-generating process used
    ONLY to label historical training data. The production pipeline never
    calls this on live pending jobs -- that is the ML model's job to
    approximate from features alone, the way a real system would learn
    from historical inspection/failure outcomes.
    """
    def norm(s, lo, hi):
        return ((s - lo) / (hi - lo)).clip(0, 1)

    score = (
        0.35 * (100 - df["current_condition_score"])
        + 0.20 * norm(df["past_failures"], 0, 15) * 100
        + 0.15 * norm(df["asset_age_years"], 0, 40) * 100
        + 0.20 * norm(df["last_maintained_days_ago"], 0, 730) * 100
        + 0.10 * norm(df["traffic_load_trains_per_day"], 15, 220) * 100
    )
    if rng is not None:
        score = score + rng.normal(0, noise_std, len(df))
    return np.clip(score, 0, 100).round(2)


def generate_historical_training_data(n: int = 2500, seed: int = 7) -> pd.DataFrame:
    """Simulate n past inspection/maintenance records with an observed
    urgency/severity outcome, for training the XGBoost urgency model."""
    rng = np.random.default_rng(seed)
    feats = _feature_frame(n, rng)
    feats["asset_type"] = rng.choice(ASSET_TYPES, n)
    feats["observed_urgency_score"] = true_urgency_formula(feats, rng=rng)
    return feats


def generate_all(num_sections: int = 6, seed: int = 42, use_real_trains: bool = True) -> dict[str, pd.DataFrame]:
    """Generate the full consistent set of tables used across the app.

    When `use_real_trains` is True (default) and the real Indian
    Railways timetable dataset is available (see real_data_loader.py),
    `sections` and `trains` are built from REAL train numbers, station
    names, and scheduled times instead of synthetic ones -- only the
    asset condition / maintenance job layer remains synthetic, since no
    public dataset exists for that. Falls back to fully synthetic data
    if the real dataset hasn't been downloaded.
    """
    used_real = False
    if use_real_trains:
        try:
            from real_data_loader import load_real_sections_and_trains

            sections, trains = load_real_sections_and_trains(num_sections=num_sections, seed=seed)
            if len(sections) >= max(2, num_sections // 2):
                used_real = True
        except Exception:
            used_real = False

    if not used_real:
        sections = generate_sections(num_sections, seed)
        trains = generate_trains(sections, seed=seed)

    assets = generate_assets(sections, seed=seed)
    jobs = generate_maintenance_jobs(assets, seed=seed)
    historical = generate_historical_training_data(seed=seed + 100)
    return {
        "sections": sections,
        "trains": trains,
        "assets": assets,
        "jobs": jobs,
        "historical": historical,
        "used_real_trains": used_real,
    }


def save_all(out_dir: str = DATA_DIR, **kwargs) -> dict[str, str]:
    """Generate all tables and persist them as CSVs. Returns a dict of
    table name -> file path written."""
    os.makedirs(out_dir, exist_ok=True)
    tables = generate_all(**kwargs)
    paths = {}
    for name, df in tables.items():
        if not isinstance(df, pd.DataFrame):
            continue
        path = os.path.join(out_dir, f"{name}.csv")
        df.to_csv(path, index=False)
        paths[name] = path
    return paths


if __name__ == "__main__":
    paths = save_all()
    for name, path in paths.items():
        print(f"wrote {name}: {path}")
