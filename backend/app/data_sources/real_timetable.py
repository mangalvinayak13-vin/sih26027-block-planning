# STAGE 1 — DATA SOURCES (real data)
#
# This module reads the REAL Indian Railways timetable dataset and turns
# it into "which section is occupied by a real train, and when" — this is
# the thing the optimizer later checks block requests against, because a
# block can never be granted on a section a train is scheduled to run
# through.
#
# Dataset: "Indian Railways Train Time Table", data.gov.in
#   https://www.data.gov.in/catalog/indian-railways-train-time-table
# It lists, for ~2810 real trains, every station they stop at with real
# arrival/departure times and cumulative distance. It does NOT contain
# block-section occupancy directly (Indian Railways doesn't publish that
# internal signalling detail) — so we DERIVE section-occupancy windows by
# looking at consecutive stops on our chosen corridor: if a real train
# departs station A at time t1 and arrives at station B at time t2, then
# the section between A and B is "occupied by that train" during [t1, t2].
# That derived window is still built entirely from real timetable numbers.

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from app.data_sources.corridor import CORRIDOR_STATION_CODES, SECTIONS

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "real", "Train_details_22122017.csv")


@dataclass
class RealTrainWindow:
    train_no: str
    train_name: str
    section_id: str
    start_min: int   # minutes from midnight of the demo day (0..1439, or >1439 if it runs past midnight)
    end_min: int
    data_source: str = "real"


def _time_to_minutes(t: str) -> int | None:
    """Convert 'HH:MM:SS' to minutes-from-midnight. Returns None if unparseable
    (a handful of rows in the raw file have blank/garbled times for terminating
    stations — we treat those as missing rather than guessing)."""
    if not isinstance(t, str) or t.strip() == "" or t.strip().upper() == "NONE":
        return None
    parts = t.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        return h * 60 + m
    except ValueError:
        return None


def load_real_train_windows() -> list[RealTrainWindow]:
    """Derive real section-occupancy windows for the demo corridor.

    We only use trains that stop at BOTH ends of one of our five corridor
    sections in the correct order (this is a simplification: an express
    that skips one of our six stations but still runs through that
    physical section isn't captured here — acceptable for a prototype,
    called out in the README).
    """
    # dtype=str + low_memory=False because the raw government CSV mixes
    # numeric-looking and text columns inconsistently across its ~186k
    # rows; parsing everything as text first and converting explicitly
    # avoids pandas silently mis-typing a column.
    df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False)
    df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce")
    df["SEQ"] = pd.to_numeric(df["SEQ"], errors="coerce")

    corridor_df = df[df["Station Code"].isin(CORRIDOR_STATION_CODES)].dropna(subset=["SEQ"])

    section_by_pair = {(s.from_station, s.to_station): s.id for s in SECTIONS}
    windows: list[RealTrainWindow] = []

    for train_no, g in corridor_df.groupby("Train No"):
        g = g.sort_values("SEQ")
        rows = g.to_dict("records")
        for i in range(len(rows) - 1):
            a, b = rows[i], rows[i + 1]
            pair = (a["Station Code"], b["Station Code"])
            section_id = section_by_pair.get(pair)
            if section_id is None:
                continue  # not a direct hop between two of our six stations

            dep = _time_to_minutes(a.get("Departure Time"))
            arr = _time_to_minutes(b.get("Arrival time"))
            if dep is None or arr is None:
                continue

            end_min = arr if arr >= dep else arr + 24 * 60  # train runs past midnight
            windows.append(
                RealTrainWindow(
                    train_no=str(a["Train No"]),
                    train_name=str(a.get("Train Name", "")).strip(),
                    section_id=section_id,
                    start_min=dep,
                    end_min=end_min,
                )
            )

    return windows
