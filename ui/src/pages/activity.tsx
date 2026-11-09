import * as React from "react";
import { ChevronRight } from "lucide-react";
import { Dot } from "@/components/status";
import { Empty } from "@/components/panel";
import { Filter, MachineSelect, SearchBox } from "@/components/table-tools";
import { age, exact, plural } from "@/lib/format";
import { setParams } from "@/lib/router";
import type { HistoryEntry } from "@/lib/types";
import type { PageProps } from "@/routes";

const day = (ts: number) => new Date(ts * 1000).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
const time = (ts: number) => new Date(ts * 1000).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

export function ActivityPage({ data, params }: PageProps) {
  const machines = data.machines.map((m) => m.name);
  const q = params.get("q") ?? "";
  const show = params.get("show") ?? "changes";
  const on = params.get("on") ?? "";
  const set = (k: string, v: string) => setParams("activity", { q, show, on, [k]: v });
  const [openId, setOpenId] = React.useState<string>("");

  const all: HistoryEntry[] = data.history ?? [];
  const n = q.trim().toLowerCase();
  const base = all.filter((h) => (!on || h.machine === on) && (!n || h.actions.some((a) => a.toLowerCase().includes(n))));
  const rows = base.filter((h) => show === "all" || (show === "changes" ? h.action_count > 0 || h.error : !!h.error));
  const options = [
    { value: "changes", label: "With changes", count: base.filter((h) => h.action_count > 0 || h.error).length },
    { value: "all", label: "Every sync", count: base.length },
    { value: "errors", label: "Failed", count: base.filter((h) => h.error).length },
  ];

  const groups = new Map<string, HistoryEntry[]>();
  for (const h of rows) {
    const k = h.finished ? day(h.finished) : "Unknown";
    groups.set(k, [...(groups.get(k) ?? []), h]);
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <SearchBox value={q} onChange={(v) => set("q", v)} placeholder="Search changes" />
        <Filter value={show} onChange={(v) => set("show", v)} options={options} label="Show" />
        <MachineSelect value={on} onChange={(v) => set("on", v)} machines={machines} />
      </div>
      {!all.length ? <div className="border-y"><Empty>No sync has finished since devsync started. History is kept in memory, the last 50 syncs per machine.</Empty></div>
        : !rows.length ? <div className="border-y"><Empty>{show === "changes" ? "No sync changed anything recently." : "Nothing matches."}</Empty></div>
        : [...groups.entries()].map(([d, items]) => (
          <section key={d} className="mb-4">
            <h2 className="border-b py-1.5 text-xs font-medium text-muted-foreground">{d}</h2>
            <ul className="divide-y">
              {items.map((h) => {
                const id = `${h.machine}:${h.finished}`;
                const open = openId === id || (!!n && h.actions.length > 0);
                const shown = n ? h.actions.filter((a) => a.toLowerCase().includes(n)) : h.actions;
                return (
                  <li key={id}>
                    <button type="button" disabled={!h.actions.length} onClick={() => setOpenId(open ? "" : id)}
                      className="flex w-full items-center gap-3 py-2 text-left text-sm enabled:hover:bg-muted/40">
                      <span className="tabular w-12 shrink-0 text-xs text-muted-foreground" title={exact(h.finished)}>{h.finished ? time(h.finished) : "—"}</span>
                      <span className="w-14 shrink-0 font-mono text-xs">{h.machine}</span>
                      <Dot status={h.error ? "bad" : h.action_count ? "info" : "ok"} />
                      <span className="min-w-0 flex-1 truncate">
                        {h.error ? <span className="text-bad">{h.error}</span> : h.action_count ? plural(h.action_count, "change") : <span className="text-muted-foreground">no changes</span>}
                        {h.attention_count > 0 && <span className="text-muted-foreground"> · {h.attention_count} need attention</span>}
                      </span>
                      <span className="hidden text-xs text-muted-foreground sm:inline">{age(h.finished)}</span>
                      {h.actions.length > 0 && <ChevronRight className={`size-3.5 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`} />}
                    </button>
                    {open && (
                      <ul className="mb-2 ml-[8.5rem] space-y-0.5 font-mono text-xs max-sm:ml-0">
                        {shown.map((a, i) => <li key={i} className="break-words text-muted-foreground">{a}</li>)}
                        {h.action_count > h.actions.length && <li className="text-muted-foreground">… {h.action_count - h.actions.length} more</li>}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
    </div>
  );
}
