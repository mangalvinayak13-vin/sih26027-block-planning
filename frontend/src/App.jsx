import { useState } from "react";
import Stage1DataSources from "./pages/Stage1DataSources";
import Stage2Preprocessing from "./pages/Stage2Preprocessing";
import Stage3Constraints from "./pages/Stage3Constraints";
import Stage4Optimization from "./pages/Stage4Optimization";
import Stage5Conflicts from "./pages/Stage5Conflicts";
import Stage6Candidates from "./pages/Stage6Candidates";
import Stage7Ranked from "./pages/Stage7Ranked";
import Stage8Dashboard from "./pages/Stage8Dashboard";

// One page per pipeline stage, in pipeline order — the navigation IS the
// pipeline diagram. Plain state-based tabs (no router) since there's no
// deep-linking need for an 8-screen demo prototype.
const STAGES = [
  { key: 1, short: "Data Sources", Component: Stage1DataSources },
  { key: 2, short: "Preprocessing", Component: Stage2Preprocessing },
  { key: 3, short: "Constraints", Component: Stage3Constraints },
  { key: 4, short: "Optimization", Component: Stage4Optimization },
  { key: 5, short: "Conflicts & Priority", Component: Stage5Conflicts },
  { key: 6, short: "Candidate Plans", Component: Stage6Candidates },
  { key: 7, short: "Ranked Plan", Component: Stage7Ranked },
  { key: 8, short: "Planner Dashboard", Component: Stage8Dashboard },
];

export default function App() {
  const [active, setActive] = useState(1);
  const ActiveComponent = STAGES.find((s) => s.key === active).Component;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="title">
          <strong>SIH26027</strong> — AI-Powered Automatic Block Planning
        </div>
      </header>
      <nav className="stage-nav">
        {STAGES.map((s) => (
          <button key={s.key} className={s.key === active ? "active" : ""} onClick={() => setActive(s.key)}>
            <span className="stage-nav-number">{s.key}</span>
            <span className="stage-nav-label">{s.short}</span>
          </button>
        ))}
      </nav>
      <main>
        <ActiveComponent />
      </main>
    </div>
  );
}
