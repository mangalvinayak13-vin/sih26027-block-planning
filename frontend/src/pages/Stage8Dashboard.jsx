import { useEffect, useState } from "react";
import { api } from "../api";
import { DEPT_COLORS } from "../constants";
import { latestRunPlans } from "../utils";

// STAGE 8 — PLANNER DASHBOARD.
// This is the ONLY place in the whole app that can change a plan's
// status to APPROVED or REJECTED (enforced server-side too — see
// backend/app/api/routes.py). Every stage before this only ever produces
// PENDING plans. That boundary is the entire point of calling this a
// decision-support tool rather than an autonomous controller: the solver
// proposes, a human disposes.

function PlanRow({ plan, onDecide }) {
  const [busy, setBusy] = useState(false);
  async function decide(action) {
    setBusy(true);
    try {
      const updated = action === "approve" ? await api.approvePlan(plan.id) : await api.rejectPlan(plan.id);
      onDecide(plan.id, updated.status);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={`plan-card status-${plan.status.toLowerCase()}`}>
      <div className="plan-header">
        <div>
          <span className="plan-rank">#{plan.rank}</span>
          {plan.rank === 1 && <span className="best-tag">Recommended</span>}
        </div>
        <div className="plan-stats">
          <span>Objective: <strong>{plan.objective_value.toFixed(0)}</strong></span>
          <span>Track-time: <strong>{plan.total_track_time_returned_min} min</strong></span>
        </div>
        <span className={`status-tag ${plan.status.toLowerCase()}`}>{plan.status}</span>
      </div>
      {plan.status === "PENDING" && (
        <div className="approve-row">
          <button disabled={busy} className="approve" onClick={() => decide("approve")}>Approve</button>
          <button disabled={busy} className="reject" onClick={() => decide("reject")}>Reject</button>
        </div>
      )}
    </div>
  );
}

export default function Stage8Dashboard() {
  const [allPlans, setAllPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setAllPlans(await api.listPlans());
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  function handleDecide(planId, status) {
    setAllPlans((prev) => prev.map((p) => (p.id === planId ? { ...p, status } : p)));
  }

  const current = latestRunPlans(allPlans);
  const decidedHistory = allPlans.filter((p) => p.status !== "PENDING" && !current.some((c) => c.id === p.id));

  return (
    <div className="page">
      <div className="stage-kicker">Stage 8 of 8</div>
      <h1>Planner Dashboard</h1>
      <p className="lede">
        Review the current run's ranked plans and approve or reject — that click is the only
        thing in this entire system that confirms anything.
      </p>

      {loading ? (
        <p>Loading...</p>
      ) : current.length === 0 ? (
        <p>No plans yet — go to Stage 4 and run the solver.</p>
      ) : (
        <div className="plans-list">
          {current.map((p) => <PlanRow key={p.id} plan={p} onDecide={handleDecide} />)}
        </div>
      )}

      {decidedHistory.length > 0 && (
        <>
          <h2>Decision log (earlier runs)</h2>
          <table className="demand-table small">
            <thead><tr><th>Run</th><th>Rank</th><th>Status</th><th>Generated</th></tr></thead>
            <tbody>
              {decidedHistory.map((p) => (
                <tr key={p.id}>
                  <td>{p.run_id}</td>
                  <td>#{p.rank}</td>
                  <td><span className={`status-tag ${p.status.toLowerCase()}`}>{p.status}</span></td>
                  <td>{new Date(p.generated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h2>Legend</h2>
      <div className="legend-row">
        {Object.entries(DEPT_COLORS).map(([dept, color]) => (
          <span key={dept}><i className="dot" style={{ background: color }} /> {dept}</span>
        ))}
      </div>
    </div>
  );
}
