"""
real_data_loader.py
--------------------
Loads REAL Indian Railways train timetable data (published on the
official Open Government Data platform, data.gov.in, under "Indian
Railways Train Time Table") and converts it into the `sections` and
`trains` tables the rest of the pipeline expects, replacing the
synthetic versions produced by `data_generator.py`.

Source dataset
--------------
"Train_details_22122017.csv" — station-wise arrival/departure times
for ~11,000 real trains across ~8,000 real stations, as published by
Indian Railways / data.gov.in and mirrored at:
    https://raw.githubusercontent.com/itzmeanjan/indian-railway/master/data/Train_details_22122017.csv
(itself sourced from data.gov.in: https://www.data.gov.in/catalog/indian-railways-train-time-table)

What is real vs. synthetic in this project after using this loader
--------------------------------------------------------------------
- REAL: train numbers, train names, station codes/names, and
  scheduled arrival/departure times -> the entire `sections` and
  `trains` tables.
- STILL SYNTHETIC: per-asset condition/maintenance data (asset age,
  failure history, condition score) and the pending maintenance jobs
  derived from them. Indian Railways does not publish granular track/
  signal/asset condition data publicly, so `data_generator.py` keeps
  generating this layer synthetically, grounded in a hand-specified
  urgency formula (see `data_generator.true_urgency_formula`).

Approach
--------
A "section" here is modeled as the real track between two consecutive
stops of at least one real train (i.e. an actual block section), with
"up" and "down" direction trains on that same station pair pooled into
one shared scheduling resource (matching the scheduler's existing
single-resource-per-section simplification -- see scheduler.py).
Sections are ranked by how many real trains actually run over them, so
the busiest, most realistic corridors are chosen by default (e.g. the
Mumbai suburban Kurla-Dadar-Matunga corridor or the Kolkata Sealdah-
Bidhannagar corridor turn out to be the busiest in the raw data).

Run directly to preview the top real sections found in the dataset:
    python real_data_loader.py
"""

from __future__ import annotations

import os
import re

import numpy as np
import pandas as pd

REAL_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_data")
RAW_CSV_PATH = os.path.join(REAL_DATA_DIR, "Train_details_22122017.csv")
RAW_CSV_URL = "https://raw.githubusercontent.com/itzmeanjan/indian-railway/master/data/Train_details_22122017.csv"

MAX_STOP_GAP_MIN = 300  # ignore station-pairs implying >5h nonstop running (likely bad/placeholder data)


def raw_data_available(path: str = RAW_CSV_PATH) -> bool:
    """Whether the real dataset CSV has already been downloaded locally."""
    return os.path.exists(path)


def download_raw_data(path: str = RAW_CSV_PATH, url: str = RAW_CSV_URL) -> str:
    """Download the real Indian Railways timetable CSV if not already present."""
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    import urllib.request

    urllib.request.urlretrieve(url, path)
    return path


def _time_to_minutes(t: str):
    """Parse an 'HH:MM:SS' string into minutes-since-midnight, or None if unparseable."""
    if not isinstance(t, str):
        return None
    parts = t.split(":")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def _classify_train_type(name: str) -> str:
    """Bucket a real train name into the same coarse categories the rest
    of the app (Gantt legend, duration priors) already expects."""
    n = (name or "").upper()
    if any(k in n for k in ["RAJDHANI", "SHATABDI", "DURONTO", "VANDE"]):
        return "Rajdhani/Superfast"
    if any(k in n for k in ["MEMU", "DEMU"]):
        return "MEMU/DEMU"
    if any(k in n for k in ["PASS", "LOCAL", "SUB"]):
        return "Passenger"
    if any(k in n for k in ["GOODS", "FRIEGHT", "FREIGHT", "PARCEL"]):
        return "Freight/Goods"
    return "Mail/Express"


def load_raw_timetable(path: str = RAW_CSV_PATH) -> pd.DataFrame:
    """Load and lightly clean the raw real timetable CSV."""
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    df["SEQ"] = pd.to_numeric(df["SEQ"], errors="coerce")
    df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce")
    df = df.dropna(subset=["SEQ", "Train No", "Station Code"])
    df["dep_min_raw"] = df["Departure Time"].apply(_time_to_minutes)
    df["arr_min_raw"] = df["Arrival time"].apply(_time_to_minutes)
    return df


def build_directed_segments(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn the per-stop timetable into per-block-section occupancy
    windows: for each train, each consecutive (stop_i -> stop_i+1) pair
    becomes one row using stop_i's real departure time and stop_i+1's
    real arrival time (both are always genuine scheduled times, never
    the '00:00:00' placeholders railways use for a train's very first
    arrival / very last departure)."""
    raw = raw.sort_values(["Train No", "SEQ"])
    rows = []
    for train_no, g in raw.groupby("Train No", sort=False):
        g = g.sort_values("SEQ")
        codes = g["Station Code"].tolist()
        names = g["Station Name"].tolist()
        dists = g["Distance"].tolist()
        deps = g["dep_min_raw"].tolist()
        arrs = g["arr_min_raw"].tolist()
        train_name = g["Train Name"].iloc[0] if "Train Name" in g else ""
        for i in range(len(g) - 1):
            d, a = deps[i], arrs[i + 1]
            if pd.isna(d) or pd.isna(a) or a <= d or (a - d) > MAX_STOP_GAP_MIN:
                continue  # skip missing times / overnight wraps / bad data for this simple day-horizon model
            rows.append(
                {
                    "train_no": train_no,
                    "train_name": train_name,
                    "from_code": codes[i],
                    "to_code": codes[i + 1],
                    "from_name": names[i].strip() if isinstance(names[i], str) else names[i],
                    "to_name": names[i + 1].strip() if isinstance(names[i + 1], str) else names[i + 1],
                    "dep_min": int(d),
                    "arr_min": int(a),
                    "distance_km": abs((dists[i + 1] or 0) - (dists[i] or 0)) if dists[i] is not None and dists[i + 1] is not None else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _undirected_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def select_top_sections(
    segments: pd.DataFrame,
    num_sections: int = 6,
    max_trains_per_section: int = 30,
    min_trains_per_section: int = 10,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pick the busiest real block sections (station pairs, both
    directions pooled as one shared track resource) and build the
    `sections` / `trains` tables the scheduler/app expect.
    """
    rng = np.random.default_rng(seed)
    segments = segments.copy()
    segments["pair_key"] = segments.apply(lambda r: _undirected_key(r["from_code"], r["to_code"]), axis=1)

    counts = segments.groupby("pair_key").size().sort_values(ascending=False)
    counts = counts[counts >= min_trains_per_section]
    top_keys = list(counts.head(num_sections).index)

    section_rows = []
    train_rows = []
    train_counter = 0
    for i, key in enumerate(top_keys, start=1):
        sec_segments = segments[segments["pair_key"] == key]
        code_a, code_b = key
        # use whichever direction's names/labels appear first for a human-readable section name
        sample = sec_segments.iloc[0]
        name_a = sample["from_name"] if sample["from_code"] == code_a else sample["to_name"]
        name_b = sample["to_name"] if sample["from_code"] == code_a else sample["from_name"]

        section_id = f"SEC{i:02d}"
        avg_distance = sec_segments["distance_km"].dropna().mean()
        section_rows.append(
            {
                "section_id": section_id,
                "section_code": f"{code_a}-{code_b}",
                "section_name": f"{name_a} - {name_b}",
                "zone": "N/A (derived from real timetable)",
                "num_tracks": 2,
                "length_km": int(avg_distance) if pd.notna(avg_distance) and avg_distance > 0 else 5,
            }
        )

        n_take = min(max_trains_per_section, len(sec_segments))
        picked = sec_segments.sample(n=n_take, random_state=int(rng.integers(0, 1_000_000)))
        for _, seg in picked.iterrows():
            train_counter += 1
            train_rows.append(
                {
                    "train_id": f"RT{train_counter:05d}",
                    "train_no": seg["train_no"],
                    "train_name": seg["train_name"],
                    "section_id": section_id,
                    "train_type": _classify_train_type(seg["train_name"]),
                    "dep_min": seg["dep_min"],
                    "arr_min": seg["arr_min"],
                    "duration_min": seg["arr_min"] - seg["dep_min"],
                }
            )

    sections_df = pd.DataFrame(section_rows)
    trains_df = pd.DataFrame(train_rows).sort_values(["section_id", "dep_min"]).reset_index(drop=True)
    return sections_df, trains_df


def load_real_sections_and_trains(
    num_sections: int = 6,
    max_trains_per_section: int = 30,
    seed: int = 42,
    csv_path: str = RAW_CSV_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One-call entry point used by data_generator.py: load the real
    dataset (downloading it first if needed) and return real
    (sections_df, trains_df) tables."""
    if not raw_data_available(csv_path):
        download_raw_data(csv_path)
    raw = load_raw_timetable(csv_path)
    segments = build_directed_segments(raw)
    return select_top_sections(segments, num_sections=num_sections, max_trains_per_section=max_trains_per_section, seed=seed)


if __name__ == "__main__":
    if not raw_data_available():
        print(f"Downloading real dataset to {RAW_CSV_PATH} ...")
        download_raw_data()
    raw = load_raw_timetable()
    print(f"Loaded {len(raw)} real timetable rows, {raw['Train No'].nunique()} unique trains.")
    segments = build_directed_segments(raw)
    print(f"Built {len(segments)} usable real block-section occupancy records.")
    sections_df, trains_df = select_top_sections(segments)
    print("\nTop real sections selected:")
    print(sections_df.to_string(index=False))
    print(f"\n{len(trains_df)} real train occupancy records across these sections.")
    print(trains_df.head(10).to_string(index=False))
