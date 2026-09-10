import { useEffect, useState } from "react";
import { api, formatMinutes } from "../api";
import BarChart from "../components/BarChart";

// STAGE 2 — PREPROCESSING & VALIDATION.
// Before any of this touches the solver, every raw block demand is run
// through pandas sanity checks (backend/app/preprocessing/validate.py).
// This page deliberately includes one BROKEN demo record (end time before
// start time) so you can see a check actually catch something, instead of
// staring at an "all clear" screen and having to take our word for it.

export default function Stage2Preprocessing() {
  const [data, setData] = useState(null);
  const [filterFailedOnly, setFilterFailedOnly] = useState(false);

  useEffect(() => {
    api.getPreprocessingDemo().then(setData);
  }, []);

  if (!data) return <div className="page">Loading...</div>;

  const failedIds = new Set(data.report.flatMap((r) => r.failed_ids));
  const visibleDemands = filterFailedOnly ? data.demands.filter((d) => failedIds.has(d.id)) : data.demands;

  const funnelChart = [
    { id: "raw", label: "Raw demands received", value: data.raw_count, color: "#9ca3af" },
    { id: "clean", label: "Passed validation", value: data.clean_count, color: "#047857" },
  ];

  return (
    <div className="page">
      <div className="stage-kicker">Stage 2 of 8</div>
      <h1>Preprocessing & Validation</h1>
      <p className="lede">
        Raw block demands can come from data-entry mistakes as much as from real requests — a
        block whose end time is before its start time isn't a real request, it's a bug. This
        stage uses pandas to catch that class of problem <strong>before</strong> the solver ever
        sees it, since feeding garbage into a constraint solver either crashes it or produces a
        "valid-looking" plan built on nonsense.
      </p>

      <h2>Funnel: raw → clean</h2>
      <BarChart items={funnelChart} maxValue={data.raw_count} />

      <h2>Checks run</h2>
      <div className="chip-row">
        {data.checks_run.map((check) => {
          const failing = data.report.filter((r) => r.check === check);
          const failCount = failing.reduce((s, r) => s + r.failed_ids.length, 0);
          return (
            <div key={check} className={`chip ${failCount > 0 ? "chip-fail" : "chip-pass"}`}>
              {failCount > 0 ? "❌" : "✅"} {check.replace(/_/g, " ")}
              {failCount > 0 && <span className="chip-count">{failCount}</span>}
            </div>
          );
        })}
      </div>

      <div className="row-between">
        <h2>Every raw record</h2>
        <label className="checkbox-label">
          <input type="checkbox" checked={filterFailedOnly} onChange={(e) => setFilterFailedOnly(e.target.checked)} />
          Show only flagged records
        </label>
      </div>
      <table className="demand-table">
        <thead>
          <tr><th>Outcome</th><th>ID</th><th>Dept</th><th>Section</th><th>Window</th><th>Description</th></tr>
        </thead>
        <tbody>
          {visibleDemands.map((d) => (
            <tr key={d.id} className={d.passed_validation ? "granted" : "rejected"}>
              <td>{d.passed_validation ? "✅ Valid" : "❌ Rejected"}</td>
              <td>{d.id}</td>
              <td>{d.department}</td>
              <td>{d.section_id}</td>
              <td>{formatMinutes(d.start_min)} – {formatMinutes(d.end_min)}</td>
              <td>{d.work_description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
