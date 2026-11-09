import { ExternalLink, Monitor } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/panel";
import { Dot, Pill, Quiet } from "@/components/status";
import { age, exact, until } from "@/lib/format";
import type { PageProps } from "@/routes";

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span className="text-muted-foreground">{k}</span>
      <span className="min-w-0 truncate text-right">{children}</span>
    </div>
  );
}

export function MachinesPage({ data }: PageProps) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {data.machines.map((m) => {
        const c = m.cycle;
        return (
          <Panel key={m.name} icon={Monitor}
            title={<span className="flex items-center gap-2"><span className="font-mono">{m.name}</span>{m.me && <span className="text-xs font-normal text-muted-foreground">this machine</span>}</span>}
            action={!m.me && m.url ? <Button asChild variant="ghost" size="xs"><a href={m.url} target="_blank" rel="noreferrer">Open<ExternalLink /></a></Button> : undefined}>
            <div className="divide-y">
              <Row k="devsync">
                {m.me ? <Quiet>running{m.version ? ` · v${m.version}` : ""}</Quiet>
                  : m.reach === "bad" ? <Pill tone="bad">unreachable</Pill>
                  : m.reach === "none" ? <Quiet status="none">not polled yet</Quiet>
                  : <Quiet>seen {age(m.seen)}{m.version ? ` · v${m.version}` : ""}</Quiet>}
              </Row>
              {m.error && <p className="py-1.5 text-xs break-words text-bad">{m.error}</p>}
              {m.has_state && <>
                <Row k="Sync cycle">{!c.enabled ? <Quiet status="none">off</Quiet> : c.running ? <Quiet status="info">running</Quiet> : <Quiet>every {Math.round(data.interval_s / 60)} min</Quiet>}</Row>
                <Row k="Last finished"><span title={exact(c.finished)}>{age(c.finished)}</span></Row>
                {c.enabled && !c.running && c.next_due && <Row k="Next">{until(c.next_due)}</Row>}
                {c.error && <p className="py-1.5 text-xs break-words text-bad">{c.error}</p>}
                <Row k="Syncthing">
                  {m.syncthing.reachable ? <Quiet>reachable</Quiet> : <Pill tone="bad">{m.syncthing.error || "unreachable"}</Pill>}
                </Row>
                {m.syncthing.connected.map((p) => (
                  <Row key={p.name} k={`→ ${p.name}`}>
                    <span className="inline-flex items-center gap-1.5 text-muted-foreground"><Dot status={p.connected ? "ok" : "warn"} />{p.connected ? "connected" : "disconnected"}</span>
                  </Row>
                ))}
              </>}
            </div>
          </Panel>
        );
      })}
    </div>
  );
}
