/** "just now", "4 min ago", "3 h ago", "2 d ago"; "never" for missing times. */
export function age(ts: number | null | undefined, now = Date.now() / 1000): string {
  if (!ts) return "never";
  const s = Math.max(0, now - ts);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

/** "in 4 min" for a future time, "due" once it has passed. */
export function until(ts: number | null | undefined, now = Date.now() / 1000): string {
  if (!ts) return "";
  const s = ts - now;
  if (s <= 30) return "due";
  if (s < 3600) return `in ${Math.round(s / 60)} min`;
  return `in ${Math.round(s / 3600)} h`;
}

export function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}

export function exact(ts: number | null | undefined) {
  return ts ? new Date(ts * 1000).toLocaleString() : "";
}
