export function Logo({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={className}>
      <rect x="2" y="5" width="13" height="13" rx="3.5" className="fill-brand" />
      <rect x="9" y="7" width="13" height="13" rx="3.5" className="fill-brand-soft opacity-85 mix-blend-multiply dark:mix-blend-screen" />
    </svg>
  );
}
