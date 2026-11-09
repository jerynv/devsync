import { cn } from "@/lib/utils";
import type { CellStatus, Issue, Tone } from "@/lib/types";

const DOT: Record<CellStatus, string> = {
  ok: "bg-ok", info: "bg-info", warn: "bg-warn", bad: "bg-bad", none: "bg-none", absent: "bg-transparent border border-none",
};
const PILL: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok", info: "bg-info-soft text-info", warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad",
};

export function Dot({ status, className }: { status: CellStatus; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 shrink-0 rounded-full", DOT[status], className)} />;
}

/** Healthy states stay quiet: a dot and muted text. */
export function Quiet({ status = "ok", children }: { status?: CellStatus; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
      <Dot status={status} />
      <span className="truncate">{children}</span>
    </span>
  );
}

/** Only problems get a tinted pill. */
export function Pill({ tone, children, className }: { tone: Tone; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex h-5 max-w-full items-center truncate whitespace-nowrap rounded-full px-2 text-xs font-medium", PILL[tone], className)}>
      {children}
    </span>
  );
}

/** A cell's headline: pills for problems, a quiet dot otherwise. */
export function CellHead({ status, label, issues }: { status: CellStatus; label: string; issues: Issue[] }) {
  if (status === "absent") return <span className="text-xs text-muted-foreground/70">{label}</span>;
  if (status === "none") return <Quiet status="none">{label}</Quiet>;
  // ok, or a single informational note (no upstream, syncing): stay quiet.
  if (status === "ok" || (status === "info" && issues.length <= 1)) return <Quiet status={status}>{label}</Quiet>;
  return (
    <span className="flex min-w-0 flex-wrap gap-1">
      {issues.map((i) => (
        <Pill key={i.tag + i.text} tone={i.tone}>{i.text}</Pill>
      ))}
    </span>
  );
}

export const STATUS_RANK: Record<CellStatus, number> = { bad: 0, warn: 1, info: 2, none: 3, ok: 4, absent: 5 };
