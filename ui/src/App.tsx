import * as React from "react";
import { Laptop, Loader2, Moon, RefreshCw, Search, Sun, WifiOff } from "lucide-react";
import { toast } from "sonner";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Toaster } from "@/components/ui/sonner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { AppSidebar } from "@/components/app-sidebar";
import { CommandMenu } from "@/components/command-menu";
import { DashboardProvider, requestSync, useDashboard } from "@/lib/api";
import { ThemeProvider, useTheme } from "@/lib/theme";
import { useLocation } from "@/lib/router";
import { age, until } from "@/lib/format";
import { routeById } from "@/routes";

export function App() {
  return (
    <ThemeProvider>
      <DashboardProvider>
        <Shell />
        <Toaster position="bottom-right" />
      </DashboardProvider>
    </ThemeProvider>
  );
}

const THEME_ICON = { system: Laptop, light: Sun, dark: Moon };
const THEME_TITLE = { system: "Theme: follows the system", light: "Theme: light", dark: "Theme: dark" };

function Shell() {
  const { data, error, loading, refresh } = useDashboard();
  const { page, params } = useLocation();
  const theme = useTheme();
  const [menu, setMenu] = React.useState(false);
  const [syncing, setSyncing] = React.useState(false);
  const route = routeById(page);

  React.useEffect(() => {
    document.title = data ? `${route.title} · devsync · ${data.me}` : "devsync";
  }, [route, data]);

  const sync = React.useCallback(async () => {
    setSyncing(true);
    const r = await requestSync();
    (r.started ? toast.success : r.ok ? toast.info : toast.error)(r.message);
    if (!r.started) {
      setSyncing(false);
      return;
    }
    setTimeout(refresh, 1500);
    setTimeout(() => { refresh(); setSyncing(false); }, 6000);
  }, [refresh]);

  const cycleTheme = () => {
    theme.cycle();
  };

  const running = syncing || !!data?.cycle.running || !!data?.cycle.queued;
  const ThemeIcon = THEME_ICON[theme.pref];

  return (
    <SidebarProvider>
      <AppSidebar page={route.id} data={data} />
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 rounded-t-xl border-b bg-background/85 px-3 backdrop-blur md:px-5">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-4" />
          <h1 className="truncate text-sm font-medium">{route.title}</h1>
          <div className="ml-auto flex items-center gap-1.5">
            {data && <CycleLine data={data} />}
            <Button variant="outline" size="sm" className="hidden w-52 justify-start bg-card text-muted-foreground lg:flex" onClick={() => setMenu(true)}>
              <Search />Search…<kbd className="ml-auto rounded border bg-muted px-1.5 font-mono text-[10px]">Ctrl K</kbd>
            </Button>
            <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setMenu(true)} aria-label="Search"><Search /></Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={cycleTheme} aria-label={THEME_TITLE[theme.pref]}><ThemeIcon /></Button>
              </TooltipTrigger>
              <TooltipContent>{THEME_TITLE[theme.pref]}</TooltipContent>
            </Tooltip>
            <Button size="sm" onClick={sync} disabled={running || data?.cycle.enabled === false}
              title={data?.cycle.enabled === false ? "The sync cycle is off on this server" : `Fetch, fast-forward and relink on ${data?.me ?? "this machine"}`}>
              {running ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              <span className="hidden sm:inline">{running ? "Syncing" : "Sync now"}</span>
            </Button>
          </div>
        </header>
        <div className="mx-auto w-full max-w-[1400px] flex-1 p-3 md:p-6">
          {error && (
            <div role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-bad/30 bg-bad-soft px-3 py-2 text-sm text-bad">
              <WifiOff className="size-4" />{error}{data && <span className="text-bad/80">Showing what was last loaded.</span>}
            </div>
          )}
          <div className="mb-5">
            <p className="text-sm text-muted-foreground">{route.description}</p>
          </div>
          {data ? <route.component data={data} params={params} /> : loading ? <Loading /> : null}
        </div>
      </SidebarInset>
      <CommandMenu open={menu} setOpen={setMenu} data={data} onSync={sync} onTheme={cycleTheme} />
    </SidebarProvider>
  );
}

function CycleLine({ data }: { data: NonNullable<ReturnType<typeof useDashboard>["data"]> }) {
  const c = data.cycle;
  let text: string;
  if (!c.enabled) text = "cycle off";
  else if (c.running) text = "syncing…";
  else text = `synced ${age(c.finished)}${c.next_due ? ` · next ${until(c.next_due)}` : ""}`;
  return <span className="mr-2 hidden text-xs whitespace-nowrap text-muted-foreground md:inline">{text}</span>;
}

function Loading() {
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
      <Skeleton className="h-72 rounded-xl md:col-span-4" />
    </div>
  );
}
