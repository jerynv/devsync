import * as React from "react";
import { ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative w-full sm:w-72">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder}
        className="h-8 bg-card pl-8" />
      {value && (
        <button type="button" onClick={() => onChange("")} aria-label="Clear search"
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded text-muted-foreground hover:text-foreground">
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}

export interface FilterOption { value: string; label: string; count?: number }

/** Segmented filter on wide screens, a select on phones. */
export function Filter({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: FilterOption[]; label: string }) {
  return (
    <>
      <ToggleGroup type="single" variant="outline" size="sm" value={value} aria-label={label}
        onValueChange={(v) => v && onChange(v)} className="hidden bg-card md:flex">
        {options.map((o) => (
          <ToggleGroupItem key={o.value} value={o.value} className="gap-1.5 px-2.5 text-xs">
            {o.label}
            {o.count !== undefined && <span className="tabular text-muted-foreground">{o.count}</span>}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <div className="md:hidden">
        <Select value={value} onValueChange={onChange}>
          <SelectTrigger size="sm" className="w-44 bg-card" aria-label={label}><SelectValue /></SelectTrigger>
          <SelectContent>
            {options.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}{o.count !== undefined ? ` (${o.count})` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </>
  );
}

export function MachineSelect({ value, onChange, machines }: { value: string; onChange: (v: string) => void; machines: string[] }) {
  if (machines.length < 2) return null;
  return (
    <Select value={value || "all"} onValueChange={(v) => onChange(v === "all" ? "" : v)}>
      <SelectTrigger size="sm" className="w-40 bg-card" aria-label="Machine"><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All machines</SelectItem>
        {machines.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export const PAGE_SIZE = 50;

export function usePaged<T>(rows: T[], resetKey: string) {
  const [page, setPage] = React.useState(0);
  React.useEffect(() => setPage(0), [resetKey]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const p = Math.min(page, pages - 1);
  return { rows: rows.slice(p * PAGE_SIZE, (p + 1) * PAGE_SIZE), page: p, pages, setPage, total: rows.length };
}

export function Pager({ page, pages, total, setPage, noun }: { page: number; pages: number; total: number; setPage: (n: number) => void; noun: string }) {
  return (
    <div className="flex items-center justify-between gap-2 px-1 pt-3 text-xs text-muted-foreground">
      <span className="tabular">{total} {noun}</span>
      {pages > 1 && (
        <div className="flex items-center gap-1">
          <span className="tabular mr-2">Page {page + 1} of {pages}</span>
          <Button variant="outline" size="icon-sm" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft /></Button>
          <Button variant="outline" size="icon-sm" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight /></Button>
        </div>
      )}
    </div>
  );
}

export function EmptyRow({ cols, children }: { cols: number; children: React.ReactNode }) {
  return (
    <tr><td colSpan={cols} className="py-10 text-center text-sm text-muted-foreground">{children}</td></tr>
  );
}
