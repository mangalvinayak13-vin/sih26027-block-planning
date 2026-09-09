import { useEffect, useState } from "react";
import { api, formatMinutes } from "../api";

const DEPT_COLORS = {
  ENGINEERING: "#b45309",
  S_AND_T: "#1d4ed8",
  TRD: "#7c3aed",
  TRAFFIC: "#047857",
};

function DeptBadge({ department }) {
  return (
    <span className="badge" style={{ background: DEPT_COLORS[department] || "#666" }}>
      {department.replace("_AND_", "&")}
    </span>
  );
}

// One row in a plan's demand table. Shown for EVERY demand (granted or
// not) with its reason, because a planner needs to see what was rejected
// and why just as much as what was approved — that's the whole point of
// "reasoning visible" from the problem statement.
function DemandRow({ item }) {
  return (
    <tr className={item.granted ? "granted" : "rejected"}>
      <td>{item.granted ? "✅ Granted" : "❌ Not granted"}</td>
      <td><DeptBadge department={item.department} /></td>
      <td>{item.block_type}</td>
      <td>{item.section_id}</td>
      <td>
        {formatMinutes(item.start_min)} – {formatMinutes(item.end_min)}
      </td>
      <td>{item.work_description}</td>
      <td>{item.priority_score.toFixed(2)}</td>
      <td className="reason">{item.reason}</td>
    </tr>
  );
}

// A single ranked plan card. Fetches its own detail (per-demand
// reasoning) lazily on first expand, rather than the parent loading every
// plan's full detail up front — with only ~3 plans this barely matters
// for performance, but it's the right pattern once a real deployment has
// many more candidate plans per run.
function PlanCard({ planSummary, onStatusChange }) {
  const [expanded, setExpanded] = useState(planSummary.rank === 1);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (expanded && !detail) {
      api.getPlan(planSummary.id).then(setDetail);
    }
  }, [expanded, detail, planSummary.id]);

  async function act(action) {
    setBusy(true);
    try {
      const updated = action === "approve" ? await api.approvePlan(planSummary.id) : await api.rejectPlan(planSummary.id);
      onStatusChange(planSummary.id, updated.status);
      setDetail((d) => (d ? { ...d, status: updated.status } : d));
    } finally {
      setBusy(false);
    }
  }

  const grantedCount = detail ? detail.items.filter((i) => i.granted).length : null;

  return (
    <div className={`plan-card status-${planSummary.status.toLowerCase()}`}>
      <div className="plan-header" onClick={() => setExpanded((e) => !e)}>
        <div>
          <span className="plan-rank">#{planSummary.rank}</span>
          {planSummary.rank === 1 && <span className="best-tag">Recommended</span>}
        </div>
        <div className="plan-stats">
          <span>Track-time returned: <strong>{planSummary.total_track_time_returned_min} min</strong></span>
          <span>Objective score: <strong>{planSummary.objective_value.toFixed(0)}</strong></span>
          {grantedCount !== null && <span>{grantedCount} / {detail.items.length} requests granted</span>}
        </div>
        <span className={`status-tag ${planSummary.status.toLowerCase()}`}>{planSummary.status}</span>
      </div>

      {expanded && (
        <div className="plan-body">
          {!detail ? (
            <p>Loading plan detail...</p>
          ) : (
            <>
              <table className="demand-table">
                <thead>
                  <tr>
                    <th>Outcome</th><th>Dept</th><th>Block type</th><th>Section</th>
                    <th>Window</th><th>Work</th><th>Priority</th><th>Why</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.items.map((item) => <DemandRow key={item.demand_id} item={item} />)}
                </tbody>
              </table>

              {/* Human-in-the-loop control: this is the ONLY place in the
                  UI that can change a plan's status. The system never
                  auto-approves — see backend/app/api/routes.py's comment
                  on the approve/reject endpoints for the same boundary
                  enforced server-side. */}
              <div className="approve-row">
                {planSummary.status === "PENDING" ? (
                  <>
                    <button disabled={busy} className="approve" onClick={() => act("approve")}>
                      Approve this plan
                    </button>
                    <button disabled={busy} className="reject" onClick={() => act("reject")}>
                      Reject this plan
                    </button>
                  </>
                ) : (
                  <p className="muted">
                    Reviewed by {detail.reviewed_by} at {new Date(detail.reviewed_at).toLocaleString()}
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState(null);

  async function loadPlans() {
    setLoading(true);
    try {
      const all = await api.listPlans();
      setPlans(all);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlans();
  }, []);

  async function handleSolve() {
    setSolving(true);
    setError(null);
    try {
      await api.solvePlans();
      await loadPlans();
    } catch (e) {
      setError(e.message);
    } finally {
      setSolving(false);
    }
  }

  function handleStatusChange(planId, status) {
    setPlans((prev) => prev.map((p) => (p.id === planId ? { ...p, status } : p)));
  }

  // Only show the MOST RECENT solver run's plans on the dashboard —
  // older runs stay in the database (and their approve/reject decisions
  // stay recorded) but re-running the solver is how a planner asks
  // "show me fresh options", not something that should pile up forever
  // on screen.
  const latestRunId = plans[0]?.run_id;
  const latestPlans = plans.filter((p) => p.run_id === latestRunId);

  return (
    <div className="page">
      <h1>Planner Dashboard</h1>
      <p className="lede">
        Ranked candidate block plans for tonight's overnight window on the New Delhi → Kanpur
        Central corridor. Run the optimizer, review why each plan ranked where it did, then
        approve or reject — the solver only ever proposes, it never confirms a block itself.
      </p>

      <button className="solve-btn" disabled={solving} onClick={handleSolve}>
        {solving ? "Running CP-SAT solver..." : "Run Solver on Current Block Demands"}
      </button>
      {error && <p className="error">Error: {error}</p>}

      {loading ? (
        <p>Loading plans...</p>
      ) : latestPlans.length === 0 ? (
        <p>No plans yet — click "Run Solver" to generate the ranked shortlist.</p>
      ) : (
        <div className="plans-list">
          {latestPlans
            .sort((a, b) => a.rank - b.rank)
            .map((p) => (
              <PlanCard key={p.id} planSummary={p} onStatusChange={handleStatusChange} />
            ))}
        </div>
      )}
    </div>
  );
}
