import * as React from "react";
import { Check } from "lucide-react";
import { Dot } from "@/components/status";
import { Filter, SearchBox } from "@/components/table-tools";
import { href, setParams } from "@/lib/router";
import type { Drift } from "@/lib/types";
import type { PageProps } from "@/routes";

const AREAS = [
  { value: "all", label: "All" },
  { value: "repos", label: "Repos" },
  { value: "folders", label: "Folders" },
  { value: "skills", label: "Skills" },
  { value: "machines", label: "Machines" },
];

/** Where a discrepancy's subject lives, so a click lands on the full comparison. */
export function driftLink(d: Drift, data: PageProps["data"]) {
  if (d.area === "repos") return href("repos", { open: d.subject });
  if (d.area === "folders") {
    const f = data.folders.find((x) => x.label === d.subject);
    return href("folders", f ? { open: f.id } : { q: d.subject });
  }
  if (d.area === "skills") return href("skills");
  return href("machines");
}

export function DriftList({ items, data, compact = false }: { items: Drift[]; data: PageProps["data"]; compact?: boolean }) {
  return (
    <ul className="divide-y">
      {items.map((d) => (
        <li key={d.id}>
          <a href={driftLink(d, data)} className="flex gap-3 py-2.5 hover:bg-muted/40">
            <Dot status={d.tone} className="mt-1.5" />
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 items-baseline gap-2">
                <span className="truncate font-mono text-[13px] font-medium">{d.subject}</span>
                {!compact && <span className="shrink-0 text-[11px] text-muted-foreground">{d.area}</span>}
              </div>
              <div className="text-sm text-muted-foreground">{d.summary}</div>
              {Object.keys(d.machines).length > 0 && (
                <div className="mt-1 grid gap-x-6 gap-y-0.5 text-xs sm:grid-cols-2">
                  {Object.entries(d.machines).map(([m, v]) => (
                    <div key={m} className="min-w-0 truncate" title={`${m}: ${v}`}>
                      <span className="font-mono">{m}</span> <span className="text-muted-foreground">{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </a>
        </li>
      ))}
    </ul>
  );
}

export function DriftPage({ data, params }: PageProps) {
  const all = data.drift ?? [];
  const q = params.get("q") ?? "";
  const area = params.get("area") ?? "all";
  const set = (k: string, v: string) => setParams("drift", { q, area, [k]: v === "all" ? "" : v });
  const searched = React.useMemo(() => {
    const n = q.trim().toLowerCase();
    return n ? all.filter((d) => `${d.subject} ${d.summary} ${Object.values(d.machines).join(" ")}`.toLowerCase().includes(n)) : all;
  }, [all, q]);
  const rows = searched.filter((d) => area === "all" || d.area === area);
  const options = AREAS.map((a) => ({ ...a, count: a.value === "all" ? searched.length : searched.filter((d) => d.area === a.value).length }));

  if (!all.length) {
    return <div className="flex items-center gap-2 border-y py-10 text-sm text-muted-foreground"><Check className="size-4 text-ok" />Every machine agrees.</div>;
  }
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <SearchBox value={q} onChange={(v) => set("q", v)} placeholder="Search discrepancies" />
        <Filter value={area} onChange={(v) => set("area", v)} options={options} label="Area" />
      </div>
      <div className="border-y">
        {rows.length ? <DriftList items={rows} data={data} /> : <p className="py-8 text-center text-sm text-muted-foreground">Nothing matches.</p>}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        These compare what each machine reports. devsync settles nothing here on its own: a different commit or branch, a folder shared on one side only, or skills missing on a machine are yours to resolve.
      </p>
    </div>
  );
}
