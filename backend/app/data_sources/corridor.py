# STAGE 1 — DATA SOURCES
#
# This file defines the physical railway corridor our demo runs on.
#
# WHY a real corridor and not a made-up one: block planning is only
# convincing if evaluators recognise the geography. We use a real stretch
# of the Delhi-Howrah main line (New Delhi -> Kanpur Central) because it is
# one of India's busiest mixed passenger+freight corridors, so clashes
# between departments wanting the same track at the same time are a real,
# everyday problem here — not something we had to invent.
#
# The STATION names/codes are real. The SECTION lengths below are not
# guessed — they were computed from the actual data.gov.in timetable file
# (real_data/Train_details_22122017.csv) by taking, for many real trains
# that stop at both ends of a section, the difference in the timetable's
# cumulative "Distance" column. See scripts note in README for how these
# numbers were derived. That makes the corridor "real data", even though
# no public dataset tells us which department has a maintenance block on
# which day (that part is necessarily synthetic — see synthetic_blocks.py).

from dataclasses import dataclass


@dataclass(frozen=True)
class Station:
    code: str          # official IR station code, e.g. "NDLS"
    name: str           # human-readable name
    km_from_start: float  # distance from New Delhi along the corridor


@dataclass(frozen=True)
class Section:
    id: str             # short id used everywhere else in the code/DB
    from_station: str   # station code
    to_station: str      # station code
    length_km: float


# Real stations, real order, real (derived) cumulative distance.
STATIONS = [
    Station("NDLS", "New Delhi", 0.0),
    Station("GZB", "Ghaziabad Jn.", 25.0),
    Station("ALJN", "Aligarh Jn.", 25.0 + 106.0),
    Station("TDL", "Tundla Jn.", 25.0 + 106.0 + 78.0),
    Station("ETW", "Etawah", 25.0 + 106.0 + 78.0 + 87.0),
    Station("CNB", "Kanpur Central", 25.0 + 106.0 + 78.0 + 87.0 + 135.0),
]

# A "block section" is the unit of track a block is granted over: the
# stretch of line between two consecutive stations. This matches how IR
# actually grants blocks — never over a single point, always over a
# defined section, because that's the piece of track that gets physically
# closed to traffic.
SECTIONS = [
    Section("SEC-1", "NDLS", "GZB", 25.0),
    Section("SEC-2", "GZB", "ALJN", 106.0),
    Section("SEC-3", "ALJN", "TDL", 78.0),
    Section("SEC-4", "TDL", "ETW", 87.0),
    Section("SEC-5", "ETW", "CNB", 135.0),
]

STATION_BY_CODE = {s.code: s for s in STATIONS}
SECTION_BY_ID = {s.id: s for s in SECTIONS}
CORRIDOR_STATION_CODES = [s.code for s in STATIONS]
