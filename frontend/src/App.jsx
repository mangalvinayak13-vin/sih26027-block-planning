import { useState } from "react";
import Dashboard from "./pages/Dashboard";
import WhatIsABlock from "./pages/WhatIsABlock";
import Corridor from "./pages/Corridor";
import DataSources from "./pages/DataSources";

// Plain state-based tabs instead of a router library — there are only
// four screens and no deep-linking need for a prototype, so a router
// would be one more dependency to explain for no real benefit here.
const TABS = [
  { key: "block", label: "What is a Block?", Component: WhatIsABlock },
  { key: "corridor", label: "Corridor & Demands", Component: Corridor },
  { key: "dashboard", label: "Planner Dashboard", Component: Dashboard },
  { key: "sources", label: "Data Sources", Component: DataSources },
];

export default function App() {
  const [active, setActive] = useState("block");
  const ActiveComponent = TABS.find((t) => t.key === active).Component;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="title">
          <strong>SIH26027</strong> — AI-Powered Automatic Block Planning (Prototype)
        </div>
        <nav>
          {TABS.map((t) => (
            <button
              key={t.key}
              className={t.key === active ? "active" : ""}
              onClick={() => setActive(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        <ActiveComponent />
      </main>
    </div>
  );
}
