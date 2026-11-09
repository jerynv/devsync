import * as React from "react";
import { ArrowDownUp, GitBranch, GitCommitHorizontal } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CellHead, Pill, STATUS_RANK } from "@/components/status";
import { EmptyRow, Filter, MachineSelect, Pager, SearchBox, usePaged } from "@/components/table-tools";
import { TableCard } from "@/components/panel";
import { Compare, DetailSheet, DriftNotes, SheetSection } from "@/components/compare";
import { age, exact, short } from "@/lib/format";
import { setParams } from "@/lib/router";
import type { Dashboard, Drift, Repo, RepoCell } from "@/lib/types";
import type { PageProps } from "@/routes";

const tag = (c: RepoCell, t: string) => c.issues.some((i) => i.tag === t);
const FILTERS: { value: string; label: string; test?: (c: RepoCell) => boolean }[] = [
  { value: "all", label: "All" },
  { value: "attention", label: "Needs attention", test: (c) => c.status === "warn" || c.status === "bad" },
  { value: "differs", label: "Differs" },
  { value: "behind", label: "Behind", test: (c) => tag(c, "behind") },
  { value: "unpushed", label: "Unpushed", test: (c) => tag(c, "unpushed") },
  { value: "uncommitted", label: "Uncommitted", test: (c) => tag(c, "uncommitted") },
  { value: "missing", label: "Not cloned", test: (c) => tag(c, "missing") },
  { value: "ok", label: "In sync" },
];

export function repoDrift(d: Dashboard) {
  const m = new Map<string, Drift[]>();
  for (const x of d.drift ?? []) if (x.area === "repos") m.set(x.subject, [...(m.get(x.subject) ?? []), x]);
  return m;
}

function matches(r: Repo, filter: string, machine: string, drift: Map<string, Drift[]>) {
  const cells = Object.entries(r.machines).filter(([m]) => !machine || m === machine).map(([, c]) => c);
  if (filter === "all") return !machine || cells.some((c) => c.status !== "absent");
  if (filter === "differs") return drift.has(r.path);
  if (filter === "ok") return cells.some((c) => c.status === "ok") && !cells.some((c) => c.status === "warn" || c.status === "bad") && !drift.has(r.path);
  const f = FILTERS.find((x) => x.value === filter);
  return !!f?.test && cells.some(f.test);
}

export function ReposPage({ data, params }: PageProps) {
  const machines = data.machines.map((m) => m.name);
  const q = params.get("q") ?? "";
  const filter = params.get("show") ?? "all";
  const machine = params.get("on") ?? "";
  const sort = params.get("sort") ?? "status";
  const open = params.get("open") ?? "";
  const set = (k: string, v: string) =>
    setParams("repos", { q, show: filter, on: machine, sort, open, [k]: v === "all" && k === "show" ? "" : v });
  const drift = React.useMemo(() => repoDrift(data), [data]);

  const searched = React.useMemo(() => {
    const n = q.trim().toLowerCase();
    return n ? data.repos.filter((r) => `${r.path} ${r.remote}`.toLowerCase().includes(n)) : data.repos;
  }, [data.repos, q]);
  const rows = React.useMemo(() => searched.filter((r) => matches(r, filter, machine, drift)).sort((a, b) =>
    sort === "name" ? a.path.localeCompare(b.path)
      : STATUS_RANK[a.status] - STATUS_RANK[b.status] || Number(drift.has(b.path)) - Number(drift.has(a.path)) || a.path.localeCompare(b.path)),
  [searched, filter, machine, sort, drift]);
  const paged = usePaged(rows, `${q}|${filter}|${machine}|${sort}`);
  const options = FILTERS.map((f) => ({ value: f.value, label: f.label, count: searched.filter((r) => matches(r, f.value, machine, drift)).length }));
  const current = data.repos.find((r) => r.path === open);

  return (
    <>
      <TableCard toolbar={<>
        <SearchBox value={q} onChange={(v) => set("q", v)} placeholder="Search repos" />
        <Filter value={filter} onChange={(v) => set("show", v)} options={options} label="Show" />
        <MachineSelect value={machine} onChange={(v) => set("on", v)} machines={machines} />
      </>}>
        <Table className="table-fixed">
          <colgroup><col className="w-[40%] md:w-[34%]" />{machines.map((m) => <col key={m} />)}</colgroup>
          <TableHeader className="[&_th]:sticky [&_th]:top-12 [&_th]:z-[5] [&_th]:bg-background [&_th]:shadow-[inset_0_-1px_0_var(--border)]">
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-0">
                <button type="button" className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => set("sort", sort === "name" ? "status" : "name")}
                  title={sort === "name" ? "Sorted by name. Click to sort by status." : "Sorted by status. Click to sort by name."}>
                  Repository <ArrowDownUp className="size-3 opacity-60" />
                  <span className="text-[11px] font-normal text-muted-foreground max-md:hidden">{sort === "name" ? "A–Z" : "by status"}</span>
                </button>
              </TableHead>
              {machines.map((m) => (
                <TableHead key={m} className="font-mono">{m}{m === data.me && <span className="ml-1.5 font-sans text-[11px] font-normal text-muted-foreground max-md:hidden">this machine</span>}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {paged.rows.map((r) => (
              <TableRow key={r.path} className="cursor-pointer align-top hover:bg-muted/40" onClick={() => set("open", r.path)}>
                <TableCell className="py-2 pl-0">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate font-mono text-[13px] font-medium" title={r.path}>{r.path}</span>
                    {drift.has(r.path) && <span className="shrink-0 text-[11px] text-warn" title={drift.get(r.path)!.map((d) => d.summary).join("; ")}>differs</span>}
                  </div>
                  {r.remote && <div className="truncate text-xs text-muted-foreground max-sm:hidden" title={r.url}>{r.remote}</div>}
                </TableCell>
                {machines.map((m) => <TableCell key={m} className="py-2 whitespace-normal"><RepoCellView cell={r.machines[m]} /></TableCell>)}
              </TableRow>
            ))}
            {paged.total === 0 && <EmptyRow cols={machines.length + 1}>{data.repos.length ? "No repos match." : "repos.toml lists no repos yet."}</EmptyRow>}
          </TableBody>
        </Table>
        <div className="border-t px-1 pb-3"><Pager {...paged} noun={paged.total === 1 ? "repo" : "repos"} /></div>
      </TableCard>
      <DetailSheet open={!!current} onClose={() => set("open", "")} title={current?.path} description={current?.url}>
        {current && <RepoDetail repo={current} machines={machines} drift={drift.get(current.path) ?? []} />}
      </DetailSheet>
    </>
  );
}

function RepoCellView({ cell }: { cell?: RepoCell }) {
  if (!cell) return null;
  const branch = cell.branch || (cell.head ? "detached" : "");
  return (
    <div className="min-w-0 space-y-0.5">
      <CellHead status={cell.status} label={cell.label} issues={cell.issues} />
      {cell.error && <div className="line-clamp-2 text-xs text-bad" title={cell.error}>{cell.error}</div>}
      {branch && (
        <div className="flex min-w-0 items-center gap-1 text-xs text-muted-foreground" title={`${branch}${cell.upstream ? ` → ${cell.upstream}` : ""}${cell.head ? ` @ ${cell.head}` : ""}`}>
          <GitBranch className="size-3 shrink-0" />
          <span className="truncate font-mono">{branch}</span>
          {cell.head && <span className="shrink-0 font-mono opacity-70 max-sm:hidden">{short(cell.head)}</span>}
          {cell.last_fetch ? <span className="shrink-0 whitespace-nowrap max-xl:hidden" title={exact(cell.last_fetch)}>· {age(cell.last_fetch)}</span> : null}
        </div>
      )}
    </div>
  );
}

function RepoDetail({ repo, machines, drift }: { repo: Repo; machines: string[]; drift: Drift[] }) {
  const c = (m: string) => repo.machines[m];
  const kept = machines.filter((m) => c(m) && c(m).status !== "absent");
  const num = (v?: number) => (v ? <Pill tone="warn">{v}</Pill> : <span className="text-muted-foreground">0</span>);
  const of = (f: (x: RepoCell) => React.ReactNode) => Object.fromEntries(kept.map((m) => [m, f(c(m))]));
  const key = (f: (x: RepoCell) => string | number | undefined) => Object.fromEntries(kept.map((m) => [m, f(c(m))]));
  return (
    <>
      <DriftNotes items={drift} />
      <SheetSection title="Each machine">
        {kept.length ? (
          <Compare machines={kept} rows={[
            { label: "Status", values: of((x) => <CellHead status={x.status} label={x.label} issues={x.issues} />) },
            { label: "Branch", values: of((x) => <span className="font-mono text-xs">{x.branch || "—"}</span>), keys: key((x) => x.branch) },
            { label: "Commit", values: of((x) => <span className="inline-flex items-center gap-1 font-mono text-xs" title={x.head}><GitCommitHorizontal className="size-3" />{short(x.head) || "—"}</span>), keys: key((x) => x.head) },
            { label: "Upstream", values: of((x) => <span className="font-mono text-xs">{x.upstream || "none"}</span>), keys: key((x) => x.upstream) },
            { label: "Behind", values: of((x) => num(x.behind)) },
            { label: "Unpushed", values: of((x) => num(x.ahead)) },
            { label: "Uncommitted", values: of((x) => num(x.dirty)) },
            { label: "Last fetch", values: of((x) => <span className="text-xs" title={exact(x.last_fetch)}>{age(x.last_fetch)}</span>) },
            { label: "Error", values: of((x) => x.error ? <span className="text-xs text-bad">{x.error}</span> : null) },
          ]} />
        ) : <p className="text-sm text-muted-foreground">No machine keeps this repo.</p>}
      </SheetSection>
      <p className="text-xs text-muted-foreground">
        devsync only fast-forwards clean branches. Anything else here (unpushed work, local changes, a different branch) is yours to settle on that machine.
      </p>
    </>
  );
}
