import * as React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Empty } from "@/components/panel";
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
        <TabsContent key={k.key} value={k.key}>
          <p className="mb-3 text-sm text-muted-foreground">{k.hint}</p>
          <div className="grid gap-x-10 lg:grid-cols-2">
            {data.housekeeping.map((h) => {
              const list = h[k.key].filter((p) => p.toLowerCase().includes(n));
              return (
                <section key={h.machine} className="min-w-0">
                  <div className="flex h-9 items-center border-b text-sm"><span className="font-mono font-medium">{h.machine}</span><span className="ml-auto text-xs text-muted-foreground">{list.length}</span></div>
                  {list.length ? (
                    <ul className="max-h-[520px] divide-y overflow-y-auto">
                      {list.map((p) => <li key={p} className="truncate py-1.5 font-mono text-xs" title={p}>{p}</li>)}
                    </ul>
                  ) : <Empty>{h[k.key].length ? "Nothing matches." : "Nothing here."}</Empty>}
                </section>
              );
            })}
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}
