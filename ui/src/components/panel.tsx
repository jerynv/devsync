import { cn } from "@/lib/utils";

/** A flat section: a quiet heading row over content, separated from the next by a hairline. */
export function Section({ title, icon: Icon, action, children, className, bodyClass }: {
  title?: React.ReactNode; icon?: React.ComponentType<{ className?: string }>; action?: React.ReactNode;
  children: React.ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={cn("min-w-0", className)}>
      {title && (
        <div className="flex h-9 items-center gap-2 border-b">
          {Icon && <Icon className="size-3.5 text-muted-foreground" />}
          <h2 className="text-[13px] font-medium">{title}</h2>
          {action && <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">{action}</div>}
        </div>
      )}
      <div className={cn("min-w-0", bodyClass)}>{children}</div>
    </section>
  );
}

/** Kept for pages that still say Panel. */
export const Panel = Section;

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{children}</p>;
}

/** A row of numbers with hairline dividers; no boxes. */
export function Stats({ items }: { items: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "warn" | "bad"; href?: string }[] }) {
  return (
    <div className="grid grid-cols-2 border-y sm:grid-cols-3 lg:grid-cols-5 lg:divide-x">
      {items.map((s) => {
        const body = (
          <>
            <div className="text-xs text-muted-foreground">{s.label}</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className={cn("tabular text-2xl font-semibold tracking-tight", s.tone === "warn" && "text-warn", s.tone === "bad" && "text-bad")}>{s.value}</span>
              {s.sub && <span className="truncate text-xs text-muted-foreground">{s.sub}</span>}
            </div>
          </>
        );
        return s.href ? (
          <a key={s.label} href={s.href} className="min-w-0 px-4 py-3 first:pl-0 hover:bg-muted/40 max-lg:first:pl-4 max-sm:odd:pl-0">{body}</a>
        ) : (
          <div key={s.label} className="min-w-0 px-4 py-3 first:pl-0">{body}</div>
        );
      })}
    </div>
  );
}

/** Tables: hairlines top and bottom, sticky header under the page header, no card. */
export function TableCard({ children, toolbar }: { children: React.ReactNode; toolbar?: React.ReactNode }) {
  return (
    <div className="min-w-0">
      {toolbar && <div className="mb-3 flex flex-wrap items-center gap-2">{toolbar}</div>}
      <div className="border-y">{children}</div>
    </div>
  );
}
