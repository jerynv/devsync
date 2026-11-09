import * as React from "react";
import { Check, Link2, Sparkles } from "lucide-react";
import { Empty, Panel } from "@/components/panel";
import { Pill, Quiet } from "@/components/status";
import { SearchBox } from "@/components/table-tools";
import { plural } from "@/lib/format";
import type { PageProps } from "@/routes";

export function SkillsPage({ data }: PageProps) {
  const [q, setQ] = React.useState("");
  const all = Array.from(new Set(data.skills.flatMap((s) => s.skills ?? []))).sort();
  const shown = all.filter((s) => s.toLowerCase().includes(q.trim().toLowerCase()));

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {data.skills.map((s) => (
        <Panel key={s.machine} title={<span className="font-mono">{s.machine}</span>} icon={Link2}
          action={s.has_state ? plural(s.skills?.length ?? 0, "skill") : undefined}>
          {!s.has_state ? <Empty>No data from this machine yet.</Empty> : (
            <div className="space-y-4 text-sm">
              <div>
                <div className="mb-1 text-xs text-muted-foreground">Source</div>
                <div className="flex items-center gap-2">
                  <span className="truncate font-mono text-[13px]" title={s.source}>{s.source}</span>
                  {!s.source_exists && <Pill tone="bad">missing</Pill>}
                </div>
              </div>
              <div>
                <div className="mb-1.5 text-xs text-muted-foreground">Links</div>
                <ul className="divide-y rounded-lg border">
                  {(s.targets ?? []).map((t) => (
                    <li key={t.path} className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className="min-w-0 flex-1 truncate font-mono text-[13px]" title={t.path}>{t.path}</span>
                        {t.problems.length ? <Pill tone="warn">{t.problems.length} to fix</Pill>
                          : <Quiet>{t.ok}/{t.total} linked</Quiet>}
                      </div>
                      {t.problems.length > 0 && (
                        <ul className="mt-1.5 space-y-0.5 text-xs">
                          {t.problems.map((p) => (
                            <li key={p.name} className="flex gap-2"><span className="font-mono">{p.name}</span><span className="text-warn">{p.status}</span></li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                  {!(s.targets ?? []).length && <li className="px-3 py-2 text-muted-foreground">No link targets configured.</li>}
                </ul>
              </div>
              {!!s.instructions?.length && (
                <div>
                  <div className="mb-1.5 text-xs text-muted-foreground">Instruction files</div>
                  <ul className="space-y-1">
                    {s.instructions.map((i) => (
                      <li key={i.path} className="flex items-center gap-2">
                        <span className="min-w-0 flex-1 truncate font-mono text-[13px]" title={i.path}>{i.path}</span>
                        {i.status === "ok" ? <Quiet>linked</Quiet> : <Pill tone="warn">{i.status}</Pill>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Panel>
      ))}
      <Panel title="Skills" icon={Sparkles} className="lg:col-span-2" action={`${shown.length} of ${all.length}`}>
        <div className="mb-3"><SearchBox value={q} onChange={setQ} placeholder="Search skills" /></div>
        {shown.length ? (
          <ul className="grid gap-x-4 gap-y-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {shown.map((name) => {
              const on = data.skills.filter((s) => s.has_state && !(s.skills ?? []).includes(name)).map((s) => s.machine);
              return (
                <li key={name} className="flex min-w-0 items-center gap-2 py-1 text-sm">
                  <Check className={`size-3.5 shrink-0 ${on.length ? "text-warn" : "text-ok"}`} />
                  <span className="truncate font-mono text-[13px]">{name}</span>
                  {on.length > 0 && <span className="shrink-0 text-xs text-warn">not on {on.join(", ")}</span>}
                </li>
              );
            })}
          </ul>
        ) : <Empty>{all.length ? "No skills match." : "The skills folder is empty."}</Empty>}
      </Panel>
    </div>
  );
}
