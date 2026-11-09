import type { LucideIcon } from "lucide-react";
import { Activity, Boxes, FolderSync, GitBranch, LayoutDashboard, Monitor, Sparkles } from "lucide-react";
import type { Dashboard } from "@/lib/types";
import { OverviewPage, attentionCount } from "@/pages/overview";
import { ReposPage } from "@/pages/repos";
import { FoldersPage } from "@/pages/folders";
import { SkillsPage } from "@/pages/skills";
import { MachinesPage } from "@/pages/machines";
import { ActivityPage } from "@/pages/activity";
import { HousekeepingPage } from "@/pages/housekeeping";

export interface PageProps { data: Dashboard; params: URLSearchParams }

/** Every page in one list: adding a page is one entry here plus its component. */
export interface Route {
  id: string;
  title: string;
  icon: LucideIcon;
  group: "Workspace" | "System";
  description: string;
  component: (p: PageProps) => React.ReactNode;
  /** Problems to badge in the sidebar. */
  badge?: (d: Dashboard) => number;
}

const problems = (rows: { status: string }[]) => rows.filter((r) => r.status === "warn" || r.status === "bad").length;

export const ROUTES: Route[] = [
  { id: "overview", title: "Overview", icon: LayoutDashboard, group: "Workspace", component: OverviewPage,
    description: "What needs you, across every machine.", badge: attentionCount },
  { id: "repos", title: "Repositories", icon: GitBranch, group: "Workspace", component: ReposPage,
    description: "Every repo in repos.toml, on every machine that keeps it.", badge: (d) => problems(d.repos) },
  { id: "folders", title: "Synced folders", icon: FolderSync, group: "Workspace", component: FoldersPage,
    description: "Syncthing folders, their state, errors and conflict copies.", badge: (d) => problems(d.folders) },
  { id: "skills", title: "Agent skills", icon: Sparkles, group: "Workspace", component: SkillsPage,
    description: "The shared skills folder and the links that make agents load it.",
    badge: (d) => d.skills.reduce((n, s) => n + (s.targets ?? []).reduce((k, t) => k + t.problems.length, 0), 0) },
  { id: "machines", title: "Machines", icon: Monitor, group: "System", component: MachinesPage,
    description: "Each machine's devsync, its sync cycle and Syncthing link.",
    badge: (d) => d.machines.filter((m) => m.reach === "bad").length },
  { id: "activity", title: "Activity", icon: Activity, group: "System", component: ActivityPage,
    description: "What the last sync on each machine did." },
  { id: "housekeeping", title: "Housekeeping", icon: Boxes, group: "System", component: HousekeepingPage,
    description: "Repos not in the manifest, folder names off the naming rule, config conflict copies.",
    badge: (d) => d.housekeeping.reduce((n, h) => n + h.config_conflicts.length, 0) },
];

export const routeById = (id: string) => ROUTES.find((r) => r.id === id) ?? ROUTES[0];
