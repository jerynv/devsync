import { Check } from "lucide-react";
import { Section, Stats } from "@/components/panel";
import { Dot, Pill } from "@/components/status";
import { DriftList } from "@/pages/drift";
import { age, exact, plural, until } from "@/lib/format";
import { href } from "@/lib/router";
import type { Dashboard } from "@/lib/types";
import type { PageProps } from "@/routes";

export const attentionCount = (d: Dashboard) => d.attention.reduce((n, g) => n + Math.max(1, g.messages.length), 0);
const bad = (s: string) => s === "warn" || s === "bad";

export function OverviewPage({ data }: PageProps) {
  const drift = data.drift ?? [];
  const repoProblems = data.repos.filter((r) => bad(r.status)).length;
  const folderProblems = data.folders.filter((f) => bad(f.status)).length;
  const linkProblems = data.skills.reduce((n, s) => n + (s.targets ?? []).reduce((k, t) => k + t.problems.length, 0), 0);
  const skillCount = Math.max(0, ...data.skills.map((s) => s.skills?.length ?? 0));
  const items = attentionCount(data);
  const recent = (data.history ?? []).filter((h) => h.action_count || h.error).slice(0, 6);

  return (
    <div className="space-y-8">
      <Stats items={[
        { label: "Discrepancies", value: drift.length, tone: drift.length ? "warn" : undefined, sub: drift.length ? "machines disagree" : "all agree", href: href("drift") },
        { label: "Needs attention", value: items, tone: items ? "warn" : undefined, sub: items ? "across machines" : "all clear", href: "#attention" },
        { label: "Repositories", value: data.repos.length, sub: repoProblems ? `${repoProblems} need a look` : "all in sync", href: href("repos", repoProblems ? { show: "attention" } : undefined) },
        { label: "Synced folders", value: data.folders.length, sub: folderProblems ? `${folderProblems} with problems` : "all up to date", href: href("folders", folderProblems ? { show: "problems" } : undefined) },
        { label: "Agent skills", value: skillCount, sub: linkProblems ? `${plural(linkProblems, "link")} to fix` : "all linked", href: href("skills") },
      ]} />

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-8">
          <Section title="Discrepancies" action={drift.length > 8 ? <a href={href("drift")} className="hover:text-foreground">All {drift.length}</a> : drift.length ? `${drift.length}` : undefined}>
            {drift.length ? <DriftList items={drift.slice(0, 8)} data={data} />
              : <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Check className="size-4 text-ok" />Every machine agrees.</p>}
          </Section>
          <div id="attention" className="scroll-mt-16">
            <Section title="Needs attention" action={items ? plural(items, "item") : undefined}>
              {data.attention.length ? (
                <ul className="divide-y">
                  {data.attention.map((g) => (
                    <li key={g.machine + g.subject} className="flex gap-3 py-2">
                      <span className="mt-0.5 w-14 shrink-0 font-mono text-xs text-muted-foreground">{g.machine}</span>
                      <div className="min-w-0 flex-1">
                        <div className={g.messages.length ? "truncate font-mono text-[13px]" : "text-sm break-words"} title={g.subject}>{g.subject}</div>
                        {g.messages.length > 0 && <div className="mt-0.5 flex flex-wrap gap-1">{g.messages.map((m) => <Pill key={m} tone="warn" className="h-auto min-h-5 whitespace-normal py-0.5">{m}</Pill>)}</div>}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Check className="size-4 text-ok" />Nothing needs you right now.</p>}
            </Section>
          </div>
        </div>

        <div className="space-y-8">
          <Section title="Machines" action={<a href={href("machines")} className="hover:text-foreground">Details</a>}>
            <ul className="divide-y">
              {data.machines.map((m) => (
                <li key={m.name} className="flex items-center gap-2 py-2 text-sm">
                  <Dot status={m.me || m.reach === "ok" ? "ok" : m.reach === "bad" ? "bad" : "none"} />
                  <span className="font-mono">{m.name}</span>
                  <span className="ml-auto truncate text-xs text-muted-foreground">
                    {m.me ? "this machine" : m.reach === "bad" ? "unreachable" : m.seen ? `seen ${age(m.seen)}` : "no data yet"}
                    {m.has_state && m.cycle.finished ? ` · synced ${age(m.cycle.finished)}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Next sync">
            <div className="space-y-1.5 py-2 text-sm">
              <Row k="Last finished"><span title={exact(data.cycle.finished)}>{age(data.cycle.finished)}</span></Row>
              <Row k="Next">{!data.cycle.enabled ? "cycle off" : data.cycle.running ? "running now" : until(data.cycle.next_due) || "—"}</Row>
              <Row k="Every">{Math.round(data.interval_s / 60)} min</Row>
              {data.cycle.error && <p className="text-xs text-bad">{data.cycle.error}</p>}
            </div>
          </Section>
          <Section title="Recent changes" action={<a href={href("activity")} className="hover:text-foreground">Activity</a>}>
            {recent.length ? (
              <ul className="divide-y">
                {recent.map((h) => (
                  <li key={`${h.machine}:${h.finished}`} className="flex items-center gap-2 py-2 text-sm">
                    <Dot status={h.error ? "bad" : "info"} />
                    <span className="font-mono text-xs">{h.machine}</span>
                    <span className="truncate">{h.error ? "failed" : plural(h.action_count, "change")}</span>
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">{age(h.finished)}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="py-3 text-sm text-muted-foreground">No changes since devsync started.</p>}
          </Section>
        </div>
      </div>
    </div>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return <div className="flex justify-between gap-2"><span className="text-muted-foreground">{k}</span><span>{children}</span></div>;
}
