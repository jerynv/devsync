import * as React from "react";
import { ArrowDownUp, GitBranch } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CellHead, STATUS_RANK } from "@/components/status";
import { EmptyRow, Filter, MachineSelect, Pager, SearchBox, usePaged } from "@/components/table-tools";
import { TableCard } from "@/components/panel";
import { age, exact } from "@/lib/format";
import { setParams } from "@/lib/router";
import type { Repo, RepoCell } from "@/lib/types";
import type { PageProps } from "@/routes";

const FILTERS: { value: string; label: string; test: (c: RepoCell) => boolean }[] = [
  { value: "all", label: "All", test: () => true },
  { value: "attention", label: "Needs attention", test: (c) => c.status === "warn" || c.status === "bad" },
  { value: "behind", label: "Behind", test: (c) => c.issues.some((i) => i.tag === "behind") },
  { value: "unpushed", label: "Unpushed", test: (c) => c.issues.some((i) => i.tag === "unpushed") },
  { value: "uncommitted", label: "Uncommitted", test: (c) => c.issues.some((i) => i.tag === "uncommitted") },
  { value: "missing", label: "Not cloned", test: (c) => c.issues.some((i) => i.tag === "missing") },
  { value: "ok", label: "In sync", test: (c) => c.status === "ok" },
];

function matches(r: Repo, filter: string, machine: string) {
  const f = FILTERS.find((x) => x.value === filter) ?? FILTERS[0];
  const cells = Object.entries(r.machines).filter(([m]) => !machine || m === machine).map(([, c]) => c);
  if (filter === "all") return !machine || cells.some((c) => c.status !== "absent");
  if (filter === "ok") return cells.some((c) => c.status === "ok") && !cells.some((c) => c.status === "warn" || c.status === "bad");
  return cells.some(f.test);
}

export function ReposPage({ data, params }: PageProps) {
  const machines = data.machines.map((m) => m.name);
  const q = params.get("q") ?? "";
  const filter = params.get("show") ?? "all";
  const machine = params.get("on") ?? "";
  const sort = params.get("sort") ?? "status";
  const set = (k: string, v: string) => setParams("repos", { q, show: filter, on: machine, sort, [k]: v === "all" && k === "show" ? "" : v });

  const searched = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    return needle ? data.repos.filter((r) => `${r.path} ${r.remote}`.toLowerCase().includes(needle)) : data.repos;
  }, [data.repos, q]);

  const rows = React.useMemo(() => {
    const out = searched.filter((r) => matches(r, filter, machine));
    return out.sort((a, b) => sort === "name" ? a.path.localeCompare(b.path)
      : STATUS_RANK[a.status] - STATUS_RANK[b.status] || a.path.localeCompare(b.path));
  }, [searched, filter, machine, sort]);

  const paged = usePaged(rows, `${q}|${filter}|${machine}|${sort}`);
  const options = FILTERS.map((f) => ({ value: f.value, label: f.label, count: searched.filter((r) => matches(r, f.value, machine)).length }));

  return (
    <TableCard toolbar={<>
      <SearchBox value={q} onChange={(v) => set("q", v)} placeholder="Search repos" />
      <Filter value={filter} onChange={(v) => set("show", v)} options={options} label="Show" />
      <MachineSelect value={machine} onChange={(v) => set("on", v)} machines={machines} />
    </>}>
      <Table className="table-fixed">
        <colgroup>
          <col className="w-[38%] md:w-[34%]" />
          {machines.map((m) => <col key={m} />)}
        </colgroup>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead>
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
            <TableRow key={r.path} className="align-top">
              <TableCell className="py-2.5">
                <div className="truncate font-mono text-[13px] font-medium" title={r.path}>{r.path}</div>
                {r.remote && <div className="truncate text-xs text-muted-foreground max-sm:hidden" title={r.url}>{r.remote}</div>}
              </TableCell>
              {machines.map((m) => <TableCell key={m} className="py-2.5 whitespace-normal"><RepoCellView cell={r.machines[m]} /></TableCell>)}
            </TableRow>
          ))}
          {paged.total === 0 && <EmptyRow cols={machines.length + 1}>{data.repos.length ? "No repos match." : "repos.toml lists no repos yet."}</EmptyRow>}
        </TableBody>
      </Table>
      <div className="border-t px-3 pb-3"><Pager {...paged} noun={paged.total === 1 ? "repo" : "repos"} /></div>
    </TableCard>
  );
}

function RepoCellView({ cell }: { cell?: RepoCell }) {
  if (!cell) return null;
  const branch = cell.branch || (cell.status !== "absent" && cell.status !== "none" && cell.status !== "warn" ? "detached" : "");
  return (
    <div className="min-w-0 space-y-1">
      <CellHead status={cell.status} label={cell.label} issues={cell.issues} />
      {cell.error && <div className="line-clamp-2 text-xs text-bad" title={cell.error}>{cell.error}</div>}
      {branch && (
        <div className="flex min-w-0 items-center gap-1 text-xs text-muted-foreground" title={`${branch}${cell.upstream ? ` → ${cell.upstream}` : ""}`}>
          <GitBranch className="size-3 shrink-0" />
          <span className="truncate font-mono">{branch}</span>
          {cell.last_fetch ? <span className="shrink-0 whitespace-nowrap max-lg:hidden" title={exact(cell.last_fetch)}>· fetched {age(cell.last_fetch)}</span> : null}
        </div>
      )}
    </div>
  );
}
