import { ExternalLink } from "lucide-react";
import { Section } from "@/components/panel";
import { Compare } from "@/components/compare";
import { Dot, Pill, Quiet } from "@/components/status";
import { DriftList } from "@/pages/drift";
import { age, exact, isoAge, until } from "@/lib/format";
import type { PageProps } from "@/routes";

export function MachinesPage({ data }: PageProps) {
  const names = data.machines.map((m) => m.name);
  const by = Object.fromEntries(data.machines.map((m) => [m.name, m]));
  const of = (f: (m: (typeof data.machines)[number]) => React.ReactNode) => Object.fromEntries(names.map((n) => [n, f(by[n])]));
  const drift = (data.drift ?? []).filter((d) => d.area === "machines");
  const peers = Array.from(new Set(data.machines.flatMap((m) => m.syncthing.connected.map((c) => c.name))));

  return (
    <div className="space-y-8">
      {drift.length > 0 && <Section title="Discrepancies"><DriftList items={drift} data={data} compact /></Section>}
      <Section title="Side by side">
        <Compare machines={names} rows={[
          { label: "devsync", values: of((m) => m.me ? <Quiet>this machine</Quiet> : m.reach === "bad" ? <Pill tone="bad">unreachable</Pill>
              : m.reach === "none" ? <Quiet status="none">not polled yet</Quiet> : <Quiet>seen {age(m.seen)}</Quiet>) },
          { label: "Open", values: of((m) => !m.me && m.url ? <a href={m.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs underline-offset-2 hover:underline">{m.url.replace(/^https?:\/\//, "")}<ExternalLink className="size-3" /></a> : null) },
          { label: "Version", values: of((m) => m.version ? <span className="font-mono text-xs">{m.version}</span> : null), keys: of((m) => m.version) as Record<string, string> },
          { label: "Data from", values: of((m) => m.has_state ? <span title={exact(m.generated)}>{age(m.generated)}</span> : null) },
          { label: "Sync cycle", values: of((m) => !m.has_state ? null : !m.cycle.enabled ? <Quiet status="none">off</Quiet> : m.cycle.running ? <Quiet status="info">running</Quiet> : <Quiet>on</Quiet>) },
          { label: "Last sync", values: of((m) => m.has_state ? <span title={exact(m.cycle.finished)}>{age(m.cycle.finished)}</span> : null) },
          { label: "Next sync", values: of((m) => m.has_state && m.cycle.enabled && !m.cycle.running ? until(m.cycle.next_due) : null) },
          { label: "Cycle error", values: of((m) => m.cycle.error ? <span className="text-xs text-bad">{m.cycle.error}</span> : null) },
          { label: "Syncthing", values: of((m) => !m.has_state ? null : m.syncthing.reachable ? <Quiet>reachable</Quiet> : <Pill tone="bad">{m.syncthing.error || "unreachable"}</Pill>) },
          ...peers.map((p) => ({
            label: `→ ${p}`,
            values: of((m) => {
              const c = m.syncthing.connected.find((x) => x.name === p);
              if (!c) return null;
              return <span className="inline-flex items-center gap-1.5 text-muted-foreground"><Dot status={c.connected ? "ok" : "warn"} />{c.connected ? "connected" : `last seen ${isoAge(c.last_seen)}`}</span>;
            }),
          })),
        ]} />
      </Section>
    </div>
  );
}
