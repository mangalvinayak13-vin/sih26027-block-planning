// Every function here just calls the FastAPI backend and returns JSON.
// Keeping all fetch() calls in one file (instead of scattered inside
// components) means there's exactly one place to change if the backend
// URL or an endpoint path ever changes.

const BASE_URL = "http://localhost:8000/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export const api = {
  getCorridor: () => request("/corridor"),
  getDataSources: () => request("/data-sources"),
  getDemands: () => request("/demands"),
  getGangs: () => request("/gangs"),
  getTrains: () => request("/trains"),
  getHistorical: () => request("/historical"),
  getPreprocessingDemo: () => request("/pipeline/preprocessing"),
  solvePlans: () => request("/plans/solve", { method: "POST" }),
  listPlans: () => request("/plans"),
  getPlan: (id) => request(`/plans/${id}`),
  approvePlan: (id) => request(`/plans/${id}/approve`, { method: "POST" }),
  rejectPlan: (id) => request(`/plans/${id}/reject`, { method: "POST" }),
};

// Block-request times are stored as "minutes from midnight of the demo
// day" (see backend/app/data_sources/real_timetable.py for why) because
// that is much easier for the solver to do arithmetic on than a real
// date/time. This converts one back into a clock string for display,
// e.g. 1500 -> "01:00 (+1d)".
export function formatMinutes(totalMinutes) {
  const dayOffset = Math.floor(totalMinutes / 1440);
  const minutesIntoDay = totalMinutes % 1440;
  const h = Math.floor(minutesIntoDay / 60)
    .toString()
    .padStart(2, "0");
  const m = (minutesIntoDay % 60).toString().padStart(2, "0");
  return dayOffset > 0 ? `${h}:${m} (+${dayOffset}d)` : `${h}:${m}`;
}
