import { History } from "lucide-react";
import { Empty, Panel } from "@/components/panel";
import { age, exact, plural } from "@/lib/format";
import type { PageProps } from "@/routes";

export function ActivityPage({ data }: PageProps) {
  if (!data.activity.length) return <Empty>No machine has finished a sync yet.</Empty>;
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {data.activity.map((a) => (
        <Panel key={a.machine} icon={History} title={<span className="font-mono">{a.machine}</span>}
          action={<span title={exact(a.finished)}>{a.finished ? `finished ${age(a.finished)}` : "not run yet"}{a.dry_run ? " · dry run" : ""}</span>}>
          {a.actions.length ? (
            <>
              <p className="mb-2 text-xs text-muted-foreground">{plural(a.actions.length, "change")}</p>
              <ul className="space-y-1">
                {a.actions.map((x, i) => <li key={i} className="rounded-md bg-muted/60 px-2.5 py-1.5 font-mono text-xs break-words">{x}</li>)}
              </ul>
            </>
          ) : <Empty>The last sync changed nothing.</Empty>}
        </Panel>
      ))}
    </div>
  );
}
