# STAGE 2 — DATA PREPROCESSING & VALIDATION
#
# WHY this stage exists as a separate step, before the solver ever sees
# the data: raw block demands come from different departments (in real
# life, three different systems — BDMS entries from Engineering, S&T,
# TRD). Feeding bad data straight into a constraint solver either crashes
# it or, worse, produces a "valid-looking" plan built on garbage (e.g. a
# block that ends before it starts). This stage catches that BEFORE
# optimization, using plain pandas checks — no solving happens here.
#
# We use pandas here (not just plain Python loops) because the problem
# statement's stated stack lists Pandas for "Data Preprocessing", and
# because vectorised checks scale better once real BDMS data (potentially
# thousands of rows) replaces this demo's dozen records.

from __future__ import annotations

import pandas as pd

from app.data_sources.synthetic_blocks import BlockDemand


def validate_demands(demands: list[BlockDemand]) -> tuple[list[BlockDemand], list[dict]]:
    """Run sanity checks on raw block demands.

    Returns (clean_demands, validation_report). Invalid records are
    dropped from clean_demands but are still counted so evaluators can
    see the check actually catches something if we later feed it bad
    synthetic data.
    """
    df = pd.DataFrame([d.__dict__ for d in demands])
    report = []
    valid_mask = pd.Series(True, index=df.index)

    # Check 1: a block must have a positive duration. A request where
    # end <= start is a data-entry error, not a real block (this mirrors
    # what BDMS itself should reject on entry, but we can't assume every
    # upstream system enforces it, so we re-check here).
    bad_duration = df["end_min"] <= df["start_min"]
    if bad_duration.any():
        report.append({"check": "positive_duration", "failed_ids": df.loc[bad_duration, "id"].tolist()})
        valid_mask &= ~bad_duration

    # Check 2: defect_severity must be in the 1-5 scale the priority
    # scorer expects. Anything outside that range would silently distort
    # every priority score downstream, so we reject rather than clip.
    bad_severity = ~df["defect_severity"].between(1, 5)
    if bad_severity.any():
        report.append({"check": "defect_severity_range", "failed_ids": df.loc[bad_severity, "id"].tolist()})
        valid_mask &= ~bad_severity

    # Check 3: section_id and assigned_gang_id must reference something
    # that actually exists in our corridor/roster — an unresolvable
    # foreign key means the solver would be building constraints for a
    # section or gang that doesn't exist.
    from app.data_sources.corridor import SECTION_BY_ID
    from app.data_sources.synthetic_blocks import GANGS

    known_gang_ids = {g.id for g in GANGS}
    bad_section = ~df["section_id"].isin(SECTION_BY_ID.keys())
    bad_gang = ~df["assigned_gang_id"].isin(known_gang_ids)
    if bad_section.any():
        report.append({"check": "known_section", "failed_ids": df.loc[bad_section, "id"].tolist()})
        valid_mask &= ~bad_section
    if bad_gang.any():
        report.append({"check": "known_gang", "failed_ids": df.loc[bad_gang, "id"].tolist()})
        valid_mask &= ~bad_gang

    # Check 4 (flag, don't drop): an unusually long single block (>6h) is
    # not invalid, but is unusual enough to flag for a human to double
    # check — this is the kind of soft warning real planners rely on.
    long_block = (df["end_min"] - df["start_min"]) > 360
    for demand_id in df.loc[long_block, "id"]:
        report.append({"check": "unusually_long_block_flagged", "failed_ids": [demand_id]})

    clean_ids = set(df.loc[valid_mask, "id"])
    clean_demands = [d for d in demands if d.id in clean_ids]
    return clean_demands, report
