import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import CorridorMap from "../components/CorridorMap";
import Timeline from "../components/Timeline";
import { DEPT_COLORS, REAL_TRAIN_COLOR } from "../constants";
import { overlaps } from "../utils";

// STAGE 3 — CONSTRAINT MODELLING.
// This page makes the hard rules (backend/app/constraints/builder.py)
// VISIBLE as timelines instead of asking you to trust a list of
// constraints in code. Pick a section: every block demand AND every real
// train on that section is drawn on one shared clock. Anything drawn with
// a red outline overlaps something else in time on the same resource —
// that's exactly what CP-SAT's NoOverlap constraint (or, for real trains,
// the "force granted=0" rule) forbids from both being present at once.

const VIEW_RANGE = [1200, 1860]; // 20:00 -> 07:00 next day, covers the whole overnight demo window

export default function Stage3Constraints() {
  const [corridor, setCorridor] = useState(null);
  const [demands, setDemands] = useState([]);
  const [trains, setTrains] = useState([]);
  const [gangs, setGangs] = useState([]);
  const [viewMode, setViewMode] = useState("section"); // "section" | "gang"
  const [selectedSection, setSelectedSection] = useState("SEC-2");
  const [selectedGang, setSelectedGang] = useState(null);

  useEffect(() => {
    api.getCorridor().then(setCorridor);
    api.getDemands().then(setDemands);
    api.getTrains().then(setTrains);
    api.getGangs().then((g) => {
      setGangs(g);
      setSelectedGang(g[0]?.id ?? null);
    });
  }, []);

  const sectionRows = useMemo(() => {
    if (viewMode !== "section") return [];
    const sectionDemands = demands.filter((d) => d.section_id === selectedSection);
    const sectionTrains = trains.filter(
      (t) => t.section_id === selectedSection && t.start_min < VIEW_RANGE[1] && t.end_min > VIEW_RANGE[0]
    );
    const rows = [
      ...sectionTrains.map((t) => ({
        id: `train-${t.train_no}`,
        label: `🚆 ${t.train_no}`,
        sublabel: t.train_name,
        start: t.start_min,
        end: t.end_min,
        color: REAL_TRAIN_COLOR,
      })),
      ...sectionDemands.map((d) => ({
        id: d.id,
        label: `${d.id} (${d.department})`,
        sublabel: d.work_description,
        start: d.start_min,
        end: d.end_min,
        color: DEPT_COLORS[d.department],
      })),
    ];
    // Mark conflicts: anything whose window overlaps another row's window.
    return rows.map((r) => ({
      ...r,
      conflict: rows.some((other) => other.id !== r.id && overlaps(r.start, r.end, other.start, other.end)),
    }));
  }, [viewMode, selectedSection, demands, trains]);

  const gangRows = useMemo(() => {
    if (viewMode !== "gang" || !selectedGang) return [];
    const gangDemands = demands.filter((d) => d.assigned_gang_id === selectedGang);
    const rows = gangDemands.map((d) => ({
      id: d.id,
      label: `${d.id} · ${d.section_id}`,
      sublabel: d.work_description,
      start: d.start_min,
      end: d.end_min,
      color: DEPT_COLORS[d.department],
    }));
    return rows.map((r) => ({
      ...r,
      conflict: rows.some((other) => other.id !== r.id && overlaps(r.start, r.end, other.start, other.end)),
    }));
  }, [viewMode, selectedGang, demands]);

  const trainCountBySection = {};
  for (const t of trains) trainCountBySection[t.section_id] = (trainCountBySection[t.section_id] || 0) + 1;

  return (
    <div className="page">
      <div className="stage-kicker">Stage 3 of 8</div>
      <h1>Constraint Modelling</h1>
      <p className="lede">
        Three hard rules get built here, and none of them are ever relaxed for the sake of the
        objective: a section can't be double-booked (<strong>safety/interlocking</strong>), a
        block can't be granted while a real train is due through (<strong>timetable
        protection</strong>), and a gang can't be in two places at once (<strong>resource
        availability</strong>). Pick a section or a gang below to see it for real.
      </p>

      <div className="view-toggle">
        <button className={viewMode === "section" ? "active" : ""} onClick={() => setViewMode("section")}>
          View by section
        </button>
        <button className={viewMode === "gang" ? "active" : ""} onClick={() => setViewMode("gang")}>
          View by gang
        </button>
      </div>

      {viewMode === "section" && (
        <>
          <CorridorMap
            corridor={corridor}
            selectedSectionId={selectedSection}
            onSelectSection={setSelectedSection}
            sectionBadge={(id) => `${trainCountBySection[id] || 0} trains`}
          />
          <h2>
            {selectedSection}: blocks & real trains sharing this section{" "}
            {sectionRows.some((r) => r.conflict) && <span className="warn-tag">overlaps detected</span>}
          </h2>
          <Timeline rows={sectionRows} rangeStart={VIEW_RANGE[0]} rangeEnd={VIEW_RANGE[1]} />
        </>
      )}

      {viewMode === "gang" && (
        <>
          <div className="gang-picker">
            {gangs.map((g) => (
              <button key={g.id} className={g.id === selectedGang ? "active" : ""} onClick={() => setSelectedGang(g.id)}>
                {g.name}
              </button>
            ))}
          </div>
          <h2>
            {gangs.find((g) => g.id === selectedGang)?.name}: assigned block requests, any section
            {gangRows.some((r) => r.conflict) && <span className="warn-tag">double-booked</span>}
          </h2>
          <Timeline rows={gangRows} rangeStart={VIEW_RANGE[0]} rangeEnd={VIEW_RANGE[1]} />
        </>
      )}

      <div className="legend-row">
        <span><i className="dot" style={{ background: REAL_TRAIN_COLOR }} /> Real scheduled train</span>
        {Object.entries(DEPT_COLORS).map(([dept, color]) => (
          <span key={dept}><i className="dot" style={{ background: color }} /> {dept}</span>
        ))}
        <span><i className="dot outline" /> Red outline = overlaps something else (would violate a hard constraint if both were granted)</span>
      </div>
    </div>
  );
}
