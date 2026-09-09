import { useEffect, useState } from "react";
import { api, formatMinutes } from "../api";

// Shows the raw inputs to the pipeline (Stage 1: Data Sources) before any
// solving happens — the real corridor, the real trains derived from the
// timetable, and the synthetic block demands competing for track time.
// Letting evaluators see this RAW, before the optimizer touches it, is
// what makes the later ranked-plan output believable rather than a black
// box.

export default function Corridor() {
  const [corridor, setCorridor] = useState(null);
  const [demands, setDemands] = useState([]);
  const [trains, setTrains] = useState([]);
  const [gangs, setGangs] = useState([]);

  useEffect(() => {
    api.getCorridor().then(setCorridor);
    api.getDemands().then(setDemands);
    api.getTrains().then(setTrains);
    api.getGangs().then(setGangs);
  }, []);

  return (
    <div className="page">
      <h1>Corridor & Block Demands</h1>

      <h2>Corridor: New Delhi → Kanpur Central</h2>
      <p className="muted">Real stations and real (derived) section lengths — see Data Sources tab.</p>
      {corridor && (
        <div className="corridor-line">
          {corridor.stations.map((s, i) => (
            <span key={s.code} className="corridor-stop">
              <span className="station">{s.name}</span>
              {i < corridor.stations.length - 1 && (
                <span className="section-arrow">
                  {corridor.sections[i].id} ({corridor.sections[i].length_km} km) →
                </span>
              )}
            </span>
          ))}
        </div>
      )}

      <h2>Gang / resource roster <span className="badge synthetic">synthetic</span></h2>
      <table className="demand-table small">
        <thead><tr><th>ID</th><th>Name</th><th>Department</th><th>Specialisation</th></tr></thead>
        <tbody>
          {gangs.map((g) => (
            <tr key={g.id}><td>{g.id}</td><td>{g.name}</td><td>{g.department}</td><td>{g.gang_type}</td></tr>
          ))}
        </tbody>
      </table>

      <h2>
        Pending block demands ({demands.length}) <span className="badge synthetic">synthetic</span>
      </h2>
      <p className="muted">
        This is the demo scenario: overnight requests from Engineering, S&T, TRD and Traffic on
        the same corridor, several deliberately overlapping — this is what the solver resolves.
      </p>
      <table className="demand-table">
        <thead>
          <tr><th>ID</th><th>Dept</th><th>Block type</th><th>Section</th><th>Window</th><th>Work</th><th>Gang</th></tr>
        </thead>
        <tbody>
          {demands.map((d) => (
            <tr key={d.id}>
              <td>{d.id}</td><td>{d.department}</td><td>{d.block_type}</td><td>{d.section_id}</td>
              <td>{formatMinutes(d.start_min)} – {formatMinutes(d.end_min)}</td>
              <td>{d.work_description}</td><td>{d.assigned_gang_id}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>
        Real scheduled trains on this corridor overnight ({trains.length}) <span className="badge real">real</span>
      </h2>
      <p className="muted">
        Derived from the data.gov.in Indian Railways timetable — these are the windows block
        demands are checked against for the timetable-protection constraint.
      </p>
      <table className="demand-table small">
        <thead><tr><th>Train No.</th><th>Name</th><th>Section</th><th>Window</th></tr></thead>
        <tbody>
          {trains
            .filter((t) => t.start_min >= 1260 || t.end_min <= 480)
            .slice(0, 25)
            .map((t, i) => (
              <tr key={i}>
                <td>{t.train_no}</td><td>{t.train_name}</td><td>{t.section_id}</td>
                <td>{formatMinutes(t.start_min)} – {formatMinutes(t.end_min)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
