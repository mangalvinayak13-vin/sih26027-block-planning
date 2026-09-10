export function overlaps(aStart, aEnd, bStart, bEnd) {
  return aStart < bEnd && bStart < aEnd;
}

export function groupBy(list, keyFn) {
  const out = {};
  for (const item of list) {
    const key = keyFn(item);
    (out[key] ??= []).push(item);
  }
  return out;
}

// From a full /api/plans list (all runs, newest run first), pick out
// just the plans belonging to the most recent solver run — that's what
// every stage-6/7/8 page means by "the current candidate plans".
export function latestRunPlans(allPlans) {
  if (allPlans.length === 0) return [];
  const latestRunId = allPlans[0].run_id;
  return allPlans.filter((p) => p.run_id === latestRunId).sort((a, b) => a.rank - b.rank);
}
