import { useEffect, useState } from 'react';

/** The first draft runs a model on the server (1-2 min). A quiet state with elapsed seconds. */
export function ReportLoading() {
  const [s, setS] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const h = window.setInterval(() => setS(Math.floor((Date.now() - start) / 1000)), 500);
    return () => window.clearInterval(h);
  }, []);
  return (
    <div role="status" aria-live="polite" className="card max-w-[720px] px-10 py-12">
      <div className="flex items-baseline justify-between gap-6">
        <p className="text-[17px] font-medium text-ink">Drafting section V from the case data…</p>
        <p className="tnum text-[15px] text-muted">{s} s</p>
      </div>
      <div className="relative mt-5 h-[3px] overflow-hidden rounded-full bg-sunken" aria-hidden="true">
        <span className="absolute inset-y-0 left-0 w-1/4 animate-pulsebar rounded-full bg-accent/60" />
      </div>
      <p className="mt-5 text-[14px] leading-relaxed text-muted">
        The first draft of a case takes one to two minutes. After that it opens instantly. You can leave this page; the draft keeps being written.
      </p>
    </div>
  );
}
