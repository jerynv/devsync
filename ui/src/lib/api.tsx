import * as React from "react";
import type { Dashboard } from "./types";

const POLL_MS = 15_000;

interface DashboardState {
  data: Dashboard | null;
  error: string;
  loading: boolean;
  refresh: () => void;
}

const Ctx = React.createContext<DashboardState | null>(null);

/** Polls /api/dashboard while the tab is visible. The server only reads cached state. */
export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = React.useState<Dashboard | null>(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    if (document.visibilityState !== "visible") return;
    try {
      const r = await fetch("/api/dashboard", { cache: "no-store" });
      if (!r.ok) throw new Error(`The server answered ${r.status}.`);
      setData(await r.json());
      setError("");
    } catch (e) {
      setError(e instanceof Error && e.message.startsWith("The server") ? e.message : "Can't reach the server.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [refresh]);

  return <Ctx.Provider value={{ data, error, loading, refresh }}>{children}</Ctx.Provider>;
}

export function useDashboard() {
  const v = React.useContext(Ctx);
  if (!v) throw new Error("useDashboard needs DashboardProvider");
  return v;
}

const SYNC_MESSAGES: Record<string, string> = {
  queued: "Sync queued. It starts in a moment.",
  running: "A sync is already running.",
  disabled: "The sync cycle is off on this server.",
};

/** Asks this machine to run its cycle now. The work happens on the server's cycle thread. */
export async function requestSync(): Promise<{ ok: boolean; started: boolean; message: string }> {
  try {
    const r = await fetch("/api/sync", { method: "POST", headers: { "X-Devsync": "1" } });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) return { ok: false, started: false, message: `Refused (${r.status}${body.error ? `: ${body.error}` : ""}).` };
    return { ok: true, started: body.status === "queued", message: SYNC_MESSAGES[body.status] ?? SYNC_MESSAGES.queued };
  } catch {
    return { ok: false, started: false, message: "Can't reach the server." };
  }
}
