import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dot } from "@/components/status";
import type { Drift } from "@/lib/types";

export interface CompareRow {
  label: string;
  values: Record<string, React.ReactNode>;
  /** Plain values used to decide whether machines disagree; omit to never flag the row. */
  keys?: Record<string, string | number | null | undefined>;
}

/** Fields down the side, machines across the top. Rows where machines disagree are marked. */
export function Compare({ machines, rows }: { machines: string[]; rows: CompareRow[] }) {
  return (
    <table className="w-full table-fixed text-sm">
      <thead>
        <tr className="border-b text-left text-xs text-muted-foreground">
          <th className="w-32 py-2 font-normal" />
          {machines.map((m) => <th key={m} className="py-2 font-mono font-medium text-foreground">{m}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const vals = r.keys ? machines.map((m) => r.keys![m]).filter((v) => v !== undefined && v !== null && v !== "") : [];
          const differs = vals.length > 1 && new Set(vals.map(String)).size > 1;
          return (
            <tr key={r.label} className={cn("border-b align-top last:border-0", differs && "bg-warn-soft/50")}>
              <td className="py-2 pr-2 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">{differs && <Dot status="warn" />}{r.label}</span>
              </td>
              {machines.map((m) => <td key={m} className="min-w-0 py-2 pr-2 break-words">{r.values[m] ?? <span className="text-muted-foreground">—</span>}</td>)}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function DriftNotes({ items }: { items: Drift[] }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-2">
      {items.map((d) => (
        <li key={d.id} className={cn("border-l-2 pl-3 text-sm", d.tone === "bad" ? "border-bad" : d.tone === "warn" ? "border-warn" : "border-info")}>
          <div>{d.summary}</div>
          {Object.entries(d.machines).map(([m, v]) => (
            <div key={m} className="text-xs text-muted-foreground"><span className="font-mono text-foreground">{m}</span> {v}</div>
          ))}
        </li>
      ))}
    </ul>
  );
}

export function DetailSheet({ open, onClose, title, description, children }: {
  open: boolean; onClose: () => void; title: React.ReactNode; description?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-xl">
        <SheetHeader className="border-b">
          <SheetTitle className="font-mono text-sm break-all">{title}</SheetTitle>
          {description && <SheetDescription className="break-all">{description}</SheetDescription>}
        </SheetHeader>
        <div className="space-y-6 p-4">{children}</div>
      </SheetContent>
    </Sheet>
  );
}

export function SheetSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}
