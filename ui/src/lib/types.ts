// The shape of /api/dashboard, built by devsync/model.py. Keep the two in step.
export type Tone = "ok" | "info" | "warn" | "bad";
export type CellStatus = Tone | "none" | "absent";

export interface Issue { text: string; tone: Tone; tag: string }

export interface RepoCell {
  status: CellStatus;
  label: string;
  issues: Issue[];
  branch?: string;
  upstream?: string;
  last_fetch?: number | null;
  error?: string;
}

export interface Repo {
  path: string;
  url: string;
  remote: string;
  status: CellStatus;
  machines: Record<string, RepoCell>;
}

export interface FolderCell {
  status: CellStatus;
  label: string;
  issues: Issue[];
  state?: string;
  type?: string;
  error?: string;
  conflicts?: string[];
}

export interface Folder {
  id: string;
  label: string;
  path: string;
  status: CellStatus;
  machines: Record<string, FolderCell>;
}

export interface Cycle {
  enabled: boolean;
  running: boolean;
  queued: boolean;
  started: number | null;
  finished: number | null;
  next_due: number | null;
  error: string;
}

export interface Machine {
  name: string;
  me: boolean;
  reach: "ok" | "bad" | "none";
  seen: number | null;
  error: string;
  has_state: boolean;
  version: string;
  url: string;
  cycle: Cycle;
  syncthing: { reachable: boolean; error: string; connected: { name: string; connected: boolean }[] };
}

export interface AttentionGroup { machine: string; subject: string; messages: string[] }

export interface SkillTarget {
  path: string;
  ok: number;
  total: number;
  problems: { name: string; status: string }[];
}

export interface Skills {
  machine: string;
  has_state: boolean;
  source?: string;
  source_exists?: boolean;
  skills?: string[];
  targets?: SkillTarget[];
  instructions?: { path: string; status: string }[];
}

export interface Activity { machine: string; finished: number | null; dry_run: boolean; actions: string[] }
export interface Housekeeping { machine: string; unlisted: string[]; naming: string[]; config_conflicts: string[] }

export interface Dashboard {
  me: string;
  version: string;
  generated: number;
  interval_s: number;
  cycle: Cycle;
  machines: Machine[];
  attention: AttentionGroup[];
  repos: Repo[];
  folders: Folder[];
  skills: Skills[];
  activity: Activity[];
  housekeeping: Housekeeping[];
}
