import * as React from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CellHead, STATUS_RANK } from "@/components/status";
import { EmptyRow, Filter, MachineSelect, Pager, SearchBox, usePaged } from "@/components/table-tools";
import { TableCard } from "@/components/panel";
import { Compare, DetailSheet, DriftNotes, SheetSection } from "@/components/compare";
import { bytes, isoAge } from "@/lib/format";
import { setParams } from "@/lib/router";
import type { Dashboard, Drift, Folder, FolderCell } from "@/lib/types";
import type { PageProps } from "@/routes";

const TYPES: Record<string, string> = {
  sendreceive: "send & receive", sendonly: "send only", receiveonly: "receive only", receiveencrypted: "receive encrypted",
};
const has = (c: FolderCell, tag: string) => c.issues.some((i) => i.tag === tag);
const FILTERS: { value: string; label: string; test?: (c: FolderCell) => boolean }[] = [
  { value: "all", label: "All", test: (c) => c.status !== "absent" },
  { value: "problems", label: "Problems", test: (c) => c.status === "warn" || c.status === "bad" },
  { value: "differs", label: "Differs" },
  { value: "syncing", label: "Syncing", test: (c) => c.status === "info" || (c.remote ?? []).some((r) => r.completion < 100) },
  { value: "conflicts", label: "Conflicts", test: (c) => has(c, "conflicts") },
  { value: "errors", label: "Errors", test: (c) => has(c, "errors") },
  { value: "paused", label: "Paused", test: (c) => has(c, "paused") },
];

export function folderDrift(d: Dashboard) {
  const m = new Map<string, Drift[]>();
  for (const x of d.drift ?? []) if (x.area === "folders") m.set(x.subject, [...(m.get(x.subject) ?? []), x]);
  return m;
}

function matches(f: Folder, filter: string, machine: string, drift: Map<string, Drift[]>) {
  if (filter === "differs") return drift.has(f.label);
  const t = (FILTERS.find((x) => x.value === filter) ?? FILTERS[0]).test!;
  return Object.entries(f.machines).some(([m, c]) => (!machine || m === machine) && t(c));
}

export function FoldersPage({ data, params }: PageProps) {
  const machines = data.machines.map((m) => m.name);
  const q = params.get("q") ?? "";
  const filter = params.get("show") ?? "all";
  const machine = params.get("on") ?? "";
  const open = params.get("open") ?? "";
  const set = (k: string, v: string) => setParams("folders", { q, show: filter, on: machine, open, [k]: v === "all" && k === "show" ? "" : v });
  const drift = React.useMemo(() => folderDrift(data), [data]);

  const searched = React.useMemo(() => {
    const n = q.trim().toLowerCase();
    return n ? data.folders.filter((f) => `${f.label} ${f.id} ${f.path}`.toLowerCase().includes(n)) : data.folders;
  }, [data.folders, q]);
  const rows = React.useMemo(() => searched.filter((f) => matches(f, filter, machine, drift))
    .sort((a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status] || Number(drift.has(b.label)) - Number(drift.has(a.label)) || a.label.localeCompare(b.label)),
  [searched, filter, machine, drift]);
  const paged = usePaged(rows, `${q}|${filter}|${machine}`);
  const options = FILTERS.map((f) => ({ value: f.value, label: f.label, count: searched.filter((r) => matches(r, f.value, machine, drift)).length }));
  const current = data.folders.find((f) => f.id === open);

  return (
    <>
      <TableCard toolbar={<>
        <SearchBox value={q} onChange={(v) => set("q", v)} placeholder="Search folders" />
        <Filter value={filter} onChange={(v) => set("show", v)} options={options} label="Show" />
        <MachineSelect value={machine} onChange={(v) => set("on", v)} machines={machines} />
      </>}>
        <Table className="table-fixed">
          <colgroup><col className="w-[40%] md:w-[34%]" />{machines.map((m) => <col key={m} />)}</colgroup>
          <TableHeader className="[&_th]:sticky [&_th]:top-12 [&_th]:z-[5] [&_th]:bg-background [&_th]:shadow-[inset_0_-1px_0_var(--border)]">
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-0">Folder</TableHead>
              {machines.map((m) => <TableHead key={m} className="font-mono">{m}</TableHead>)}
            </TableRow>
          </TableHeader>
          <TableBody>
            {paged.rows.map((f) => (
              <TableRow key={f.id} className="cursor-pointer align-top hover:bg-muted/40" onClick={() => set("open", f.id)}>
                <TableCell className="py-2 pl-0">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate font-medium" title={f.id}>{f.label}</span>
                    {drift.has(f.label) && <span className="shrink-0 text-[11px] text-warn" title={drift.get(f.label)!.map((d) => d.summary).join("; ")}>differs</span>}
                  </div>
                  <div className="truncate font-mono text-xs text-muted-foreground" title={f.path}>{f.path}</div>
                </TableCell>
                {machines.map((m) => <TableCell key={m} className="py-2 whitespace-normal"><FolderCellView cell={f.machines[m]} /></TableCell>)}
              </TableRow>
            ))}
            {paged.total === 0 && <EmptyRow cols={machines.length + 1}>{data.folders.length ? "No folders match." : "Syncthing reports no folders."}</EmptyRow>}
          </TableBody>
        </Table>
        <div className="border-t px-1 pb-3"><Pager {...paged} noun={paged.total === 1 ? "folder" : "folders"} /></div>
      </TableCard>
      <DetailSheet open={!!current} onClose={() => set("open", "")} title={current?.label} description={current?.path}>
        {current && <FolderDetail folder={current} machines={machines} drift={drift.get(current.label) ?? []} />}
      </DetailSheet>
    </>
  );
}

function FolderCellView({ cell: c }: { cell?: FolderCell }) {
  if (!c) return null;
  const meta: string[] = [];
  if (c.status !== "absent" && c.status !== "none") {
    if (c.local_files !== undefined && c.local_files !== null) meta.push(`${c.local_files.toLocaleString()} files`);
    if (c.local_bytes) meta.push(bytes(c.local_bytes));
    if (c.type && c.type !== "sendreceive") meta.push(TYPES[c.type] ?? c.type);
  }
  return (
    <div className="space-y-0.5">
      <CellHead status={c.status} label={c.label} issues={c.issues.filter((i) => i.tag !== "remote-behind")} />
      {c.error && <div className="line-clamp-2 text-xs text-bad" title={c.error}>{c.error}</div>}
      {meta.length > 0 && <div className="truncate text-xs text-muted-foreground">{meta.join(" · ")}</div>}
      {(c.remote ?? []).filter((r) => r.completion < 100).map((r) => (
        <div key={r.name} className="flex items-center gap-2 text-xs text-muted-foreground" title={`${r.need_items} item(s), ${bytes(r.need_bytes)} still to reach ${r.name}`}>
          <span className="h-1 w-16 overflow-hidden rounded-full bg-muted"><span className="block h-full bg-info" style={{ width: `${r.completion}%` }} /></span>
          <span className="tabular">{r.name} {r.completion}%</span>
        </div>
      ))}
    </div>
  );
}

function FolderDetail({ folder, machines, drift }: { folder: Folder; machines: string[]; drift: Drift[] }) {
  const on = machines.filter((m) => folder.machines[m] && folder.machines[m].status !== "absent" && folder.machines[m].status !== "none");
  const c = (m: string) => folder.machines[m];
  const of = (f: (x: FolderCell) => React.ReactNode) => Object.fromEntries(on.map((m) => [m, f(c(m))]));
  const key = (f: (x: FolderCell) => string | number | null | undefined) => Object.fromEntries(on.map((m) => [m, f(c(m))]));
  const conflicts = on.flatMap((m) => (c(m).conflicts ?? []).map((p) => ({ m, p })));
  const errors = on.flatMap((m) => (c(m).error_paths ?? []).map((p) => ({ m, p })));
  return (
    <>
      <DriftNotes items={drift} />
      <SheetSection title="Each machine">
        {on.length ? (
          <Compare machines={on} rows={[
            { label: "Status", values: of((x) => <CellHead status={x.status} label={x.label} issues={x.issues} />) },
            { label: "Type", values: of((x) => TYPES[x.type ?? ""] ?? x.type), keys: key((x) => x.type) },
            { label: "Paused", values: of((x) => (x.paused ? "yes" : "no")), keys: key((x) => String(!!x.paused)) },
            { label: "Files here", values: of((x) => x.local_files?.toLocaleString()), keys: key((x) => x.local_files) },
            { label: "Files in total", values: of((x) => x.global_files?.toLocaleString()), keys: key((x) => x.global_files) },
            { label: "Size here", values: of((x) => bytes(x.local_bytes)) },
            { label: "Still to fetch", values: of((x) => (x.need ? `${x.need} item(s), ${bytes(x.need_bytes)}` : "nothing")) },
            { label: "Others", values: of((x) => (x.remote?.length ? x.remote.map((r) => `${r.name} ${r.completion}%`).join(", ") : (x.devices ?? []).join(", ") || "—")) },
            { label: "Last change", values: of((x) => isoAge(x.state_changed)) },
          ]} />
        ) : <p className="text-sm text-muted-foreground">No machine reports this folder.</p>}
      </SheetSection>
      {errors.length > 0 && (
        <SheetSection title="Files that failed to sync">
          <ul className="space-y-1 font-mono text-xs">{errors.map(({ m, p }) => <li key={m + p} className="break-all"><span className="text-muted-foreground">{m}</span> {p}</li>)}</ul>
        </SheetSection>
      )}
      {conflicts.length > 0 && (
        <SheetSection title={`Conflict copies (${conflicts.length})`}>
          <p className="mb-2 text-xs text-muted-foreground">Syncthing kept both versions. Compare each copy with its original, keep one, and delete the other yourself.</p>
          <ul className="max-h-80 space-y-1 overflow-y-auto font-mono text-xs">{conflicts.map(({ m, p }) => <li key={m + p} className="break-all"><span className="text-muted-foreground">{m}</span> {p}</li>)}</ul>
        </SheetSection>
      )}
    </>
  );
}
