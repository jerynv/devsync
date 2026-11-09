import { AlertTriangle, ArrowRight, Check, FolderSync, GitBranch, History, Monitor, Sparkles } from "lucide-react";
import { Panel } from "@/components/panel";
import { Dot, Pill, Quiet } from "@/components/status";
import { age, exact, plural, until } from "@/lib/format";
import { href } from "@/lib/router";
import type { Dashboard } from "@/lib/types";
import type { PageProps } from "@/routes";

export const attentionCount = (d: Dashboard) => d.attention.reduce((n, g) => n + Math.max(1, g.messages.length), 0);
const bad = (s: string) => s === "warn" || s === "bad";

function Tile({ label, value, sub, icon: Icon, tone, to }: {
  label: string; value: number | string; sub: string; icon: React.ComponentType<{ className?: string }>; tone?: "warn" | "ok"; to: string;
}) {
  return (
    <a href={to} className="group flex flex-col gap-3 rounded-xl border bg-card p-4 transition-colors hover:border-ring/60">
      <div className="flex items-center justify-between text-[13px] text-muted-foreground">
        <span className="flex items-center gap-2"><Icon className="size-4" />{label}</span>
        <ArrowRight className="size-3.5 opacity-0 transition-opacity group-hover:opacity-60" />
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`tabular text-3xl font-semibold tracking-tight ${tone === "warn" ? "text-warn" : ""}`}>{value}</span>
        <span className="truncate text-xs text-muted-foreground">{sub}</span>
      </div>
    </a>
  );
}

export function OverviewPage({ data }: PageProps) {
  const repoProblems = data.repos.filter((r) => bad(r.status)).length;
  const folderProblems = data.folders.filter((f) => bad(f.status)).length;
  const linkProblems = data.skills.reduce((n, s) => n + (s.targets ?? []).reduce((k, t) => k + t.problems.length, 0), 0);
  const skillCount = Math.max(0, ...data.skills.map((s) => s.skills?.length ?? 0));
  const items = attentionCount(data);

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <Tile label="Needs attention" icon={AlertTriangle} to={href("overview")} value={items}
        tone={items ? "warn" : undefined} sub={items ? `across ${plural(new Set(data.attention.map((g) => g.machine)).size, "machine")}` : "all clear"} />
      <Tile label="Repositories" icon={GitBranch} to={href("repos", repoProblems ? { show: "attention" } : undefined)} value={data.repos.length}
        sub={repoProblems ? `${repoProblems} need a look` : "all in sync"} />
      <Tile label="Synced folders" icon={FolderSync} to={href("folders", folderProblems ? { show: "problems" } : undefined)} value={data.folders.length}
        sub={folderProblems ? `${folderProblems} with problems` : "all up to date"} />
      <Tile label="Agent skills" icon={Sparkles} to={href("skills")} value={skillCount}
        sub={linkProblems ? `${plural(linkProblems, "link")} to fix` : "all linked"} />

      <Panel title="Needs attention" icon={AlertTriangle} className="md:col-span-2 xl:col-span-3 xl:row-span-2"
        action={items ? plural(items, "item") : undefined} bodyClass="px-0 pb-0">
        <Attention data={data} />
      </Panel>
      <Panel title="Machines" icon={Monitor} action={<a href={href("machines")} className="hover:text-foreground">Details</a>}>
        <ul className="space-y-2.5">
          {data.machines.map((m) => (
            <li key={m.name} className="flex items-center gap-2 text-sm">
              <Dot status={m.me || m.reach === "ok" ? "ok" : m.reach === "bad" ? "bad" : "none"} />
              <span className="font-mono">{m.name}</span>
              <span className="ml-auto truncate text-xs text-muted-foreground">
                {m.me ? "this machine" : m.reach === "bad" ? <Pill tone="bad">unreachable</Pill> : m.seen ? `seen ${age(m.seen)}` : "no data yet"}
              </span>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Last sync" icon={History} action={<a href={href("activity")} className="hover:text-foreground">Activity</a>}>
        <LastSync data={data} />
      </Panel>
    </div>
  );
}

function Attention({ data }: { data: Dashboard }) {
  if (!data.attention.length) {
    return <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"><Check className="size-4 text-ok" />Nothing needs you right now.</div>;
  }
  return (
    <div className="fade-bottom max-h-[440px] overflow-y-auto">
      <ul className="divide-y border-t">
        {data.attention.map((g) => (
          <li key={g.machine + g.subject} className="flex gap-3 px-4 py-2.5">
            <span className="mt-0.5 w-14 shrink-0 font-mono text-xs text-muted-foreground">{g.machine}</span>
            <div className="min-w-0 flex-1">
              <div className={g.messages.length ? "truncate font-mono text-[13px] font-medium" : "text-sm break-words"} title={g.subject}>{g.subject}</div>
              {g.messages.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {g.messages.map((m) => <Pill key={m} tone="warn" className="h-auto min-h-5 py-0.5 whitespace-normal">{m}</Pill>)}
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LastSync({ data }: { data: Dashboard }) {
  const c = data.cycle;
  const mine = data.activity.find((a) => a.machine === data.me);
  return (
    <div className="space-y-2 text-sm">
      <div className="flex justify-between gap-2"><span className="text-muted-foreground">Finished</span><span title={exact(c.finished)}>{age(c.finished)}</span></div>
      <div className="flex justify-between gap-2"><span className="text-muted-foreground">Next</span><span>{!c.enabled ? "cycle off" : c.running ? "running now" : until(c.next_due) || "—"}</span></div>
      <div className="flex justify-between gap-2"><span className="text-muted-foreground">Changes</span>
        <span>{mine?.actions.length ? plural(mine.actions.length, "action") : "none"}{mine?.dry_run ? " (dry run)" : ""}</span></div>
      {c.error && <Quiet status="bad">{c.error}</Quiet>}
    </div>
  );
}
