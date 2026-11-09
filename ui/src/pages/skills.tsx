import * as React from "react";
import { Check, Minus } from "lucide-react";
import { Empty, Section } from "@/components/panel";
import { Pill, Quiet } from "@/components/status";
import { Filter, SearchBox } from "@/components/table-tools";
import { DriftList } from "@/pages/drift";
import type { PageProps } from "@/routes";

export function SkillsPage({ data }: PageProps) {
  const [q, setQ] = React.useState("");
  const [show, setShow] = React.useState("all");
  const withState = data.skills.filter((s) => s.has_state);
  const machines = withState.map((s) => s.machine);
  const sets = Object.fromEntries(withState.map((s) => [s.machine, new Set(s.skills ?? [])]));
  const all = Array.from(new Set(withState.flatMap((s) => s.skills ?? []))).sort();
  const gap = (name: string) => machines.some((m) => !sets[m].has(name));
  const n = q.trim().toLowerCase();
  const searched = all.filter((s) => s.toLowerCase().includes(n));
  const rows = searched.filter((s) => show === "all" || gap(s));
  const drift = (data.drift ?? []).filter((d) => d.area === "skills");

  return (
    <div className="space-y-8">
      {drift.length > 0 && <Section title="Discrepancies"><DriftList items={drift} data={data} compact /></Section>}

      <Section title="Links" action={`${machines.length} machine${machines.length === 1 ? "" : "s"}`}>
        <div className="grid gap-x-10 lg:grid-cols-2">
          {data.skills.map((s) => (
            <div key={s.machine} className="min-w-0 py-3">
              <div className="mb-2 flex items-center gap-2 text-sm">
                <span className="font-mono font-medium">{s.machine}</span>
                {s.has_state && <span className="truncate font-mono text-xs text-muted-foreground" title={s.source}>{s.source}</span>}
                {s.has_state && !s.source_exists && <Pill tone="bad">source missing</Pill>}
              </div>
              {!s.has_state ? <p className="text-sm text-muted-foreground">No data from this machine yet.</p> : (
                <ul className="divide-y border-y">
                  {(s.targets ?? []).map((t) => (
                    <li key={t.path} className="py-1.5">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="min-w-0 flex-1 truncate font-mono text-[13px]" title={t.path}>{t.path}</span>
                        {t.problems.length ? <Pill tone="warn">{t.problems.length} to fix</Pill> : <Quiet>{t.ok}/{t.total} linked</Quiet>}
                      </div>
                      {t.problems.length > 0 && (
                        <ul className="mt-1 space-y-0.5 text-xs">{t.problems.map((p) => <li key={p.name}><span className="font-mono">{p.name}</span> <span className="text-warn">{p.status}</span></li>)}</ul>
                      )}
                    </li>
                  ))}
                  {(s.instructions ?? []).map((i) => (
                    <li key={i.path} className="flex items-center gap-2 py-1.5 text-sm">
                      <span className="min-w-0 flex-1 truncate font-mono text-[13px]" title={i.path}>{i.path}</span>
                      {i.status === "ok" ? <Quiet>linked</Quiet> : <Pill tone="warn">{i.status}</Pill>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </Section>

      <Section title="Skills" action={`${rows.length} of ${all.length}`}>
        <div className="flex flex-wrap items-center gap-2 py-3">
          <SearchBox value={q} onChange={setQ} placeholder="Search skills" />
          <Filter value={show} onChange={setShow} label="Show" options={[
            { value: "all", label: "All", count: searched.length },
            { value: "gaps", label: "Missing somewhere", count: searched.filter(gap).length },
          ]} />
        </div>
        {rows.length ? (
          <table className="w-full table-fixed text-sm">
            <thead><tr className="border-y text-left text-xs text-muted-foreground">
              <th className="py-2 font-normal">Skill</th>
              {machines.map((m) => <th key={m} className="w-28 py-2 font-mono font-medium text-foreground">{m}</th>)}
            </tr></thead>
            <tbody className="divide-y">
              {rows.map((name) => (
                <tr key={name} className={gap(name) ? "bg-warn-soft/40" : ""}>
                  <td className="truncate py-1.5 font-mono text-[13px]">{name}</td>
                  {machines.map((m) => <td key={m} className="py-1.5">{sets[m].has(name) ? <Check className="size-3.5 text-ok" aria-label="present" /> : <span className="inline-flex items-center gap-1 text-xs text-warn"><Minus className="size-3.5" />missing</span>}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty>{all.length ? "No skills match." : "The skills folder is empty."}</Empty>}
      </Section>
    </div>
  );
}
