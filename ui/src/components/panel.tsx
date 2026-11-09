import { cn } from "@/lib/utils";

/** A flat card: hairline border, no shadow. */
export function Panel({ title, icon: Icon, action, children, className, bodyClass }: {
  title?: React.ReactNode; icon?: React.ComponentType<{ className?: string }>; action?: React.ReactNode;
  children: React.ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={cn("flex min-w-0 flex-col rounded-xl border bg-card", className)}>
      {title && (
        <div className="flex items-center gap-2 px-4 pt-3.5 pb-2">
          {Icon && <Icon className="size-4 text-muted-foreground" />}
          <h2 className="text-[13px] font-medium">{title}</h2>
          {action && <div className="ml-auto text-xs text-muted-foreground">{action}</div>}
        </div>
      )}
      <div className={cn("min-w-0 flex-1 px-4 pb-4", !title && "pt-4", bodyClass)}>{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted-foreground">{children}</p>;
}

/** Tables share one look: muted header, hairline rows, horizontal scroll inside the card on phones. */
export function TableCard({ children, toolbar }: { children: React.ReactNode; toolbar?: React.ReactNode }) {
  return (
    <div className="min-w-0">
      {toolbar && <div className="mb-3 flex flex-wrap items-center gap-2">{toolbar}</div>}
      <div className="overflow-x-auto rounded-xl border bg-card">{children}</div>
    </div>
  );
}
