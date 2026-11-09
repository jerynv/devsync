import * as React from "react";

export type ThemePref = "system" | "light" | "dark";
const KEY = "devsync-theme";
const ORDER: ThemePref[] = ["system", "light", "dark"];

function read(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

const Ctx = React.createContext<{ pref: ThemePref; resolved: "light" | "dark"; cycle: () => void } | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [pref, setPref] = React.useState<ThemePref>(read);
  const [systemDark, setSystemDark] = React.useState(() => matchMedia("(prefers-color-scheme: dark)").matches);

  React.useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => setSystemDark(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  const resolved = pref === "system" ? (systemDark ? "dark" : "light") : pref;
  React.useEffect(() => {
    document.documentElement.classList.toggle("dark", resolved === "dark");
  }, [resolved]);

  const cycle = React.useCallback(() => {
    setPref((p) => {
      const next = ORDER[(ORDER.indexOf(p) + 1) % ORDER.length];
      try {
        localStorage.setItem(KEY, next);
      } catch {
        /* storage blocked: the choice lasts for this tab */
      }
      return next;
    });
  }, []);

  return <Ctx.Provider value={{ pref, resolved, cycle }}>{children}</Ctx.Provider>;
}

export function useTheme() {
  const v = React.useContext(Ctx);
  if (!v) throw new Error("useTheme needs ThemeProvider");
  return v;
}
