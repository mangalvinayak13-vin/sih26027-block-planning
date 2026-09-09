# STAGE 3 (part of) — turning "how urgent is this maintenance?" into a number.
#
# WHY this exists as its own small module instead of being buried inside
# the solver: the problem statement explicitly allows a small ML/heuristic
# helper to score maintenance criticality, AS LONG AS it only produces a
# number that feeds the solver — it must never decide the plan itself.
# Keeping it in its own file makes that boundary obvious: this file reads
# a BlockDemand and returns a float. It never looks at other demands, never
# knows about sections clashing, never touches the solver's variables.
#
# We start with a hand-written formula (transparent, explainable to a
# non-technical evaluator) rather than a trained classifier. The interface
# (`priority_score(demand) -> float in [0, 1]`) is exactly what a trained
# model would expose too, so swapping this for a scikit-learn model later
# is a one-function change, not a redesign.

from __future__ import annotations

# Indian Railways-style "how long is too long since this asset type was
# last maintained" thresholds. These are illustrative/synthetic — real
# thresholds live in IR engineering manuals we don't have access to — but
# the STRUCTURE (each department has its own maintenance cycle) is real.
RECOMMENDED_MAINTENANCE_CYCLE_DAYS = {
    "ENGINEERING": 180,
    "S_AND_T": 120,
    "TRD": 150,
    "TRAFFIC": 90,
}


def priority_score(
    department: str,
    days_since_last_maintenance: int,
    defect_severity: int,
    safety_risk: bool,
) -> float:
    """Return a criticality/urgency score in [0, 1].

    Higher = more urgent = should win a conflict over a lower-scored
    request on the same section. Three ingredients, each with a plain-
    English justification:

    1. Overdue-ness (40%): how far past this department's normal
       maintenance cycle this request already is. A job that is barely
       overdue is less urgent than one that's been waiting months.
    2. Defect severity (35%): a 1-5 rating of how bad the reported
       problem is (1 = cosmetic, 5 = could cause a failure/accident).
    3. Safety risk flag (25%): a hard flag for "this isn't just wear and
       tear, this is a safety-relevant defect" (e.g. a cracked rail vs. a
       faded platform sign) — weighted heavily on purpose, because safety
       work should rarely lose a scheduling fight to routine upkeep.
    """
    cycle = RECOMMENDED_MAINTENANCE_CYCLE_DAYS.get(department, 150)
    overdue_days = max(0, days_since_last_maintenance - cycle)
    # Cap at 2x the cycle so one absurdly-overdue outlier doesn't dominate
    # every other factor — a normalisation choice, not a real IR rule.
    overdue_component = min(1.0, overdue_days / cycle)

    severity_component = max(0, min(5, defect_severity)) / 5.0

    safety_component = 1.0 if safety_risk else 0.0

    score = 0.40 * overdue_component + 0.35 * severity_component + 0.25 * safety_component
    return round(score, 4)
