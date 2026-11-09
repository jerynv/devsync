import * as React from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CellHead, STATUS_RANK } from "@/components/status";
import { EmptyRow, Filter, MachineSelect, Pager, SearchBox, usePaged } from "@/components/table-tools";
import { TableCard } from "@/components/panel";
import { setParams } from "@/lib/router";
import type { Folder, FolderCell } from "@/lib/types";
import type { PageProps } from "@/routes";

const TYPES: Record<string, string> = {
  sendreceive: "send & receive", sendonly: "send only", receiveonly: "receive only", receiveencrypted: "receive encrypted",
};
const has = (c: FolderCell, tag: string) => c.issues.some((i) => i.tag === tag);
const FILTERS: { value: string; label: string; test: (c: FolderCell) => boolean }[] = [
  { value: "all", label: "All", test: (c) => c.status !== "absent" },
  { value: "problems", label: "Problems", test: (c) => c.status === "warn" || c.status === "bad" },
  { value: "conflicts", label: "Conflicts", test: (c) => has(c, "conflicts") },
  { value: "errors", label: "Errors", test: (c) => has(c, "errors") },
  { value: "paused", label: "Paused", test: (c) => has(c, "paused") },
  { value: "syncing", label: "Syncing", test: (c) => c.status === "info" },
];

function matches(f: Folder, filter: string, machine: string) {
  const t = (FILTERS.find((x) => x.value === filter) ?? FILTERS[0]).test;
  return Object.entries(f.machines).some(([m, c]) => (!machine || m === machine) && t(c));
}

export function FoldersPage({ data, params }: PageProps) {
  const machines = data.machines.map((m) => m.name);
  const q = params.get("q") ?? "";
  const filter = params.get("show") ?? "all";
  const machine = params.get("on") ?? "";
  const set = (k: string, v: string) => setParams("folders", { q, show: filter, on: machine, [k]: v === "all" && k === "show" ? "" : v });
  const [conflicts, setConflicts] = React.useState<{ folder: string; machine: string; paths: string[] } | null>(null);

  const searched = React.useMemo(() => {
    const n = q.trim().toLowerCase();
    return n ? data.folders.filter((f) => `${f.label} ${f.id} ${f.path}`.toLowerCase().includes(n)) : data.folders;
  }, [data.folders, q]);
  const rows = React.useMemo(() => searched.filter((f) => matches(f, filter, machine))
    .sort((a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status] || a.label.localeCompare(b.label)), [searched, filter, machine]);
  const paged = usePaged(rows, `${q}|${filter}|${machine}`);
  const options = FILTERS.map((f) => ({ value: f.value, label: f.label, count: searched.filter((r) => matches(r, f.value, machine)).length }));

  return (
    <>
      <TableCard toolbar={<>
        <SearchBox value={q} onChange={(v) => set("q", v)} placeholder="Search folders" />
        <Filter value={filter} onChange={(v) => set("show", v)} options={options} label="Show" />
        <MachineSelect value={machine} onChange={(v) => set("on", v)} machines={machines} />
      </>}>
        <Table className="table-fixed">
          <colgroup><col className="w-[38%] md:w-[34%]" />{machines.map((m) => <col key={m} />)}</colgroup>
          <TableHeader className="bg-muted/50">
            <TableRow>
              <TableHead>Folder</TableHead>
              {machines.map((m) => <TableHead key={m} className="font-mono">{m}</TableHead>)}
            </TableRow>
          </TableHeader>
          <TableBody>
            {paged.rows.map((f) => (
              <TableRow key={f.id} className="align-top">
                <TableCell className="py-2.5">
                  <div className="truncate font-medium" title={f.id}>{f.label}</div>
                  <div className="truncate font-mono text-xs text-muted-foreground" title={f.path}>{f.path}</div>
                </TableCell>
                {machines.map((m) => {
                  const c = f.machines[m];
                  return (
                    <TableCell key={m} className="py-2.5 whitespace-normal">
                      {c && (
                        <div className="space-y-1">
                          <CellHead status={c.status} label={c.label} issues={c.issues} />
                          {c.error && <div className="line-clamp-2 text-xs text-bad" title={c.error}>{c.error}</div>}
                          {c.type && c.type !== "sendreceive" && c.status !== "absent" && c.status !== "none" && (
                            <div className="text-xs text-muted-foreground">{TYPES[c.type] ?? c.type}</div>
                          )}
                          {!!c.conflicts?.length && (
                            <button type="button" className="text-xs text-bad underline-offset-2 hover:underline"
                              onClick={() => setConflicts({ folder: f.label, machine: m, paths: c.conflicts! })}>
                              Show conflict copies
                            </button>
                          )}
                        </div>
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
            {paged.total === 0 && <EmptyRow cols={machines.length + 1}>{data.folders.length ? "No folders match." : "Syncthing reports no folders."}</EmptyRow>}
          </TableBody>
        </Table>
        <div className="border-t px-3 pb-3"><Pager {...paged} noun={paged.total === 1 ? "folder" : "folders"} /></div>
      </TableCard>
      <Dialog open={!!conflicts} onOpenChange={(o) => !o && setConflicts(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Conflict copies in {conflicts?.folder}</DialogTitle>
            <DialogDescription>
              Found on {conflicts?.machine}. Syncthing keeps both versions; compare each copy with its original, keep one, and delete the other yourself.
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh]">
            <ul className="space-y-1 pr-3 font-mono text-xs">
              {conflicts?.paths.map((p) => <li key={p} className="break-all rounded bg-muted px-2 py-1">{p}</li>)}
            </ul>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </>
  );
}
