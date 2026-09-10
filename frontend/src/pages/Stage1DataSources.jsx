import { useEffect, useState } from "react";
import { api } from "../api";
import CorridorMap from "../components/CorridorMap";
import BarChart from "../components/BarChart";
import { groupBy } from "../utils";

// STAGE 1 — DATA SOURCES.
// This page is the honest starting point of the whole pipeline: what did
// we actually feed the solver, and where did it come from? Everything
// downstream (constraints, optimization, ranking) is only as trustworthy
// as what's shown here, so this page leads with the real corridor map and
// a real-vs-synthetic breakdown rather than a text explanation of it.

export default function Stage1DataSources() {
  const [corridor, setCorridor] = useState(null);
  const [sources, setSources] = useState(null);
  const [trains, setTrains] = useState([]);
  const [demands, setDemands] = useState([]);

  useEffect(() => {
    api.getCorridor().then(setCorridor);
    api.getDataSources().then(setSources);
    api.getTrains().then(setTrains);
    api.getDemands().then(setDemands);
  }, []);

  const trainsBySection = groupBy(trains, (t) => t.section_id);
  const demandsBySection = groupBy(demands, (d) => d.section_id);

  const trainCountChart = corridor
    ? corridor.sections.map((s) => ({
        id: s.id,
        label: s.id,
        sublabel: `${s.from_station}→${s.to_station}`,
        value: (trainsBySection[s.id] || []).length,
        color: "#4b5563",
      }))
    : [];

  return (
    <div className="page">
      <div className="stage-kicker">Stage 1 of 8</div>
      <h1>Data Sources</h1>
      <p className="lede">
        A <strong>block</strong> is a time-bound closure of a track section for maintenance. This
        pipeline's job is to plan those closures without ever letting one clash with a scheduled
        train, another department's block, or an unavailable gang. Everything below is what goes
        IN to that process — real where real data exists, clearly-flagged synthetic where it
        doesn't (Indian Railways' internal BDMS/TMS/SMMS/TDMS data isn't public).
      </p>

      <h2>The corridor</h2>
      <p className="muted">
        New Delhi → Kanpur Central, part of the Delhi-Howrah main line. Real stations, real
        (derived) section lengths.
      </p>
      <CorridorMap corridor={corridor} sectionBadge={(id) => `${(trainsBySection[id] || []).length} trains`} />

      <div className="two-col">
        <div>
          <h2>Real trains per section, overnight</h2>
          <p className="muted">Derived from the real data.gov.in timetable — the busier the bar, the less free track-time exists for a block.</p>
          <BarChart items={trainCountChart} />
        </div>
        <div>
          <h2>What's real vs synthetic here</h2>
          <div className="legend-stack">
            <div className="stat-tile">
              <div className="stat-number">{trains.length}</div>
              <div className="stat-label"><span className="badge real">real</span> derived train windows</div>
            </div>
            <div className="stat-tile">
              <div className="stat-number">{demands.length}</div>
              <div className="stat-label"><span className="badge synthetic">synthetic</span> block demands</div>
            </div>
          </div>
        </div>
      </div>

      {sources && (
        <>
          <h2><span className="badge real">Real</span> sources</h2>
          <div className="cards">
            {sources.real.map((d) => (
              <div className="card" key={d.name}>
                <h3>{d.name}</h3>
                <p className="muted">
                  <a href={d.url} target="_blank" rel="noreferrer">{d.source}</a>
                </p>
                <p>{d.used_for}</p>
              </div>
            ))}
          </div>

          <h2><span className="badge synthetic">Synthetic</span> sources</h2>
          <div className="cards">
            {sources.synthetic.map((d) => (
              <div className="card" key={d.name}>
                <h3>{d.name}</h3>
                <p className="muted">Why synthetic: {d.reason_not_public}</p>
                <p>{d.used_for}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
