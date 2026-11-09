import * as React from "react";
import { FolderSync, GitBranch, Moon, RefreshCw } from "lucide-react";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator, CommandShortcut,
} from "@/components/ui/command";
import { ROUTES } from "@/routes";
import { navigate } from "@/lib/router";
import type { Dashboard } from "@/lib/types";

export function CommandMenu({ open, setOpen, data, onSync, onTheme }: {
  open: boolean; setOpen: (v: boolean) => void; data: Dashboard | null; onSync: () => void; onTheme: () => void;
}) {
  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(!open);
      }
    };
    addEventListener("keydown", down);
    return () => removeEventListener("keydown", down);
  }, [open, setOpen]);

  const go = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Search devsync" description="Jump to a page, repo or folder">
      <CommandInput placeholder="Jump to a page, repo or folder…" />
      <CommandList>
        <CommandEmpty>Nothing matches.</CommandEmpty>
        <CommandGroup heading="Pages">
          {ROUTES.map((r) => (
            <CommandItem key={r.id} value={`page ${r.title}`} onSelect={go(() => navigate(r.id))}>
              <r.icon />{r.title}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Actions">
          <CommandItem value="action sync now" onSelect={go(onSync)}><RefreshCw />Sync now</CommandItem>
          <CommandItem value="action theme light dark" onSelect={go(onTheme)}><Moon />Switch theme</CommandItem>
        </CommandGroup>
        {data && data.repos.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Repositories">
              {data.repos.map((r) => (
                <CommandItem key={r.path} value={`repo ${r.path} ${r.remote}`} onSelect={go(() => navigate("repos", { open: r.path }))}>
                  <GitBranch /><span className="font-mono text-[13px]">{r.path}</span>
                  {r.remote && <CommandShortcut className="max-w-48 truncate tracking-normal">{r.remote}</CommandShortcut>}
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
        {data && data.folders.length > 0 && (
          <CommandGroup heading="Folders">
            {data.folders.map((f) => (
              <CommandItem key={f.id} value={`folder ${f.label} ${f.id} ${f.path}`} onSelect={go(() => navigate("folders", { open: f.id }))}>
                <FolderSync />{f.label}
                <CommandShortcut className="max-w-48 truncate font-mono tracking-normal">{f.path}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
