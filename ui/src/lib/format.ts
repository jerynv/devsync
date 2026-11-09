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

export function bytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return i === 0 ? `${v} B` : `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
}

export const short = (sha?: string) => (sha ? sha.slice(0, 7) : "");

export function isoAge(iso?: string): string {
  if (!iso) return "never";
  const t = Date.parse(iso);
  return Number.isNaN(t) || t < 86400_000 ? "never" : age(t / 1000);
}
