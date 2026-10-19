export type SectionStatus = 'auto-filled' | 'needs your input' | 'edited';

export function Toc({ items }: { items: { no: string; title: string; status: SectionStatus }[] }) {
  return (
    <nav aria-label="Report sections" className="sticky top-20 space-y-0.5">
      <p className="mb-3 px-3 text-[12px] font-medium uppercase tracking-[0.08em] text-faint">Sections</p>
      {items.map((s) => (
        <a
          key={s.no}
          href={`#sec-${s.no}`}
          className="group block rounded-lg px-3 py-1 transition-colors hover:bg-surface hover:shadow-rest"
          onClick={(e) => {
            e.preventDefault();
            document.getElementById(`sec-${s.no}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }}
        >
          <span className="flex gap-2 text-[13.5px] leading-snug text-ink">
            <span className="tnum w-6 shrink-0 text-muted">{s.no}</span>
            <span className="min-w-0">{s.title}</span>
          </span>
          <span
            className={`ml-8 block text-[12px] ${
              s.status === 'needs your input' ? 'font-medium text-amber' : s.status === 'edited' ? 'font-medium text-accent' : 'text-faint'
            }`}
          >
            {s.status}
          </span>
        </a>
      ))}
    </nav>
  );
}
