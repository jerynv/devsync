import { ExternalLink } from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader,
  SidebarMenu, SidebarMenuBadge, SidebarMenuButton, SidebarMenuItem, SidebarRail, useSidebar,
} from "@/components/ui/sidebar";
import { Dot } from "@/components/status";
import { Logo } from "@/components/logo";
import { ROUTES } from "@/routes";
import { href } from "@/lib/router";
import type { Dashboard } from "@/lib/types";

export function AppSidebar({ page, data }: { page: string; data: Dashboard | null }) {
  const { setOpenMobile } = useSidebar();
  const groups = ["Workspace", "System"] as const;
  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild className="hover:bg-transparent">
              <a href={href("overview")} onClick={() => setOpenMobile(false)}>
                <div className="flex size-8 items-center justify-center rounded-lg border bg-card"><Logo /></div>
                <div className="grid leading-tight">
                  <span className="text-[15px] font-semibold tracking-tight">devsync</span>
                  <span className="font-mono text-xs text-muted-foreground">{data?.me ?? "…"}</span>
                </div>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {groups.map((g) => (
          <SidebarGroup key={g}>
            <SidebarGroupLabel>{g}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {ROUTES.filter((r) => r.group === g).map((r) => {
                  const n = data && r.badge ? r.badge(data) : 0;
                  return (
                    <SidebarMenuItem key={r.id}>
                      <SidebarMenuButton asChild isActive={page === r.id} tooltip={r.title}>
                        <a href={href(r.id)} onClick={() => setOpenMobile(false)}>
                          <r.icon />
                          <span>{r.title}</span>
                        </a>
                      </SidebarMenuButton>
                      {n > 0 && <SidebarMenuBadge className="tabular text-warn">{n}</SidebarMenuBadge>}
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <SidebarGroupLabel>Machines</SidebarGroupLabel>
        <SidebarMenu>
          {(data?.machines ?? []).map((m) => (
            <SidebarMenuItem key={m.name}>
              <SidebarMenuButton asChild={!m.me && !!m.url} tooltip={m.me ? `${m.name} (this machine)` : `Open ${m.name}`} size="sm">
                {!m.me && m.url ? (
                  <a href={m.url} target="_blank" rel="noreferrer">
                    <Dot status={m.reach === "bad" ? "bad" : m.reach === "none" ? "none" : "ok"} className="mx-1" />
                    <span className="font-mono">{m.name}</span>
                    <ExternalLink className="ml-auto opacity-60" />
                  </a>
                ) : (
                  <>
                    <Dot status="ok" className="mx-1" />
                    <span className="font-mono">{m.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">this machine</span>
                  </>
                )}
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
        {data?.version && <p className="px-2 pt-1 font-mono text-[11px] text-muted-foreground group-data-[collapsible=icon]:hidden">v{data.version}</p>}
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
