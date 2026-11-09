import * as React from "react";
import { Boxes } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Empty, Panel } from "@/components/panel";
import { SearchBox } from "@/components/table-tools";
import type { PageProps } from "@/routes";

const KINDS = [
  { key: "unlisted", label: "Unlisted repos", hint: "Git repos on disk that repos.toml doesn't mention. Add them to the manifest or ignore them." },
  { key: "naming", label: "Naming", hint: "Folders that don't follow the naming rule. devsync only reports these." },
  { key: "config_conflicts", label: "Config conflicts", hint: "Syncthing conflict copies of devsync's own config. Merge and delete them by hand." },
] as const;

export function HousekeepingPage({ data }: PageProps) {
  const [q, setQ] = React.useState("");
  const n = q.trim().toLowerCase();
  if (!data.housekeeping.length) return <Empty>No data yet.</Empty>;
  return (
    <Tabs defaultValue="unlisted" className="gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <TabsList>
          {KINDS.map((k) => (
            <TabsTrigger key={k.key} value={k.key} className="gap-1.5">
              {k.label}<span className="tabular text-xs text-muted-foreground">{data.housekeeping.reduce((s, h) => s + h[k.key].length, 0)}</span>
            </TabsTrigger>
          ))}
        </TabsList>
        <SearchBox value={q} onChange={setQ} placeholder="Filter paths" />
      </div>
      {KINDS.map((k) => (
        <TabsContent key={k.key} value={k.key} className="space-y-3">
          <p className="text-sm text-muted-foreground">{k.hint}</p>
          <div className="grid gap-3 lg:grid-cols-2">
            {data.housekeeping.map((h) => {
              const list = h[k.key].filter((p) => p.toLowerCase().includes(n));
              return (
                <Panel key={h.machine} icon={Boxes} title={<span className="font-mono">{h.machine}</span>} action={`${list.length}`}>
                  {list.length ? (
                    <ul className="max-h-[480px] space-y-0.5 overflow-y-auto">
                      {list.map((p) => <li key={p} className="truncate rounded px-1.5 py-1 font-mono text-xs hover:bg-muted" title={p}>{p}</li>)}
                    </ul>
                  ) : <Empty>{h[k.key].length ? "Nothing matches." : "Nothing here."}</Empty>}
                </Panel>
              );
            })}
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}
