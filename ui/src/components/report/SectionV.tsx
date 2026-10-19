import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { Sentence } from '../../types';
import { sentenceNumbers, violationIndex, violationText, type SourceEntry } from './evidence';

/** Textarea that grows with its content. */
function GrowingText({ value, onChange, onDone, label }: { value: string; onChange: (v: string) => void; onDone: () => void; label: string }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, []);
  return (
    <textarea
      ref={ref}
      aria-label={label}
      value={value}
      rows={1}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onDone}
      onKeyDown={(e) => {
        if (e.key === 'Escape' || (e.key === 'Enter' && (e.metaKey || e.ctrlKey))) {
          e.preventDefault();
          onDone();
        }
      }}
      className="block w-full resize-none overflow-hidden rounded-md bg-surface px-3 py-2 text-[16px] leading-[1.7] text-ink shadow-focus outline-none"
    />
  );
}

export function SectionVBody({
  rows,
  setRows,
  violations,
  numOf,
}: {
  rows: Sentence[];
  setRows: (fn: (r: Sentence[]) => Sentence[]) => void;
  violations: Record<string, unknown>[];
  numOf: Map<string, number>;
}) {
  const [editing, setEditing] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const flagged = new Set(violations.map(violationIndex).filter((x): x is number => x !== null));
  const upd = (i: number, text: string) => setRows((r) => r.map((s, j) => (j === i ? { ...s, text } : s)));
  const done = (i: number) => {
    setEditing(null);
    if (!rows[i]?.text.trim() && !rows[i]?.refs.length) setRows((r) => r.filter((_, j) => j !== i));
  };

  return (
    <div>
      <div className="space-y-3">
        {rows.map((s, i) => {
          const nums = sentenceNumbers(s, numOf);
          const bad = flagged.has(i);
          return editing === i ? (
            <div key={i} id={`sv-${i}`}>
              <GrowingText value={s.text} onChange={(v) => upd(i, v)} onDone={() => done(i)} label={`Statement ${i + 1}`} />
              <div className="mt-1.5 flex items-center gap-4 text-[12.5px] text-muted">
                <span>Esc or click outside to finish</span>
                <button
                  type="button"
                  className="rounded px-1 hover:text-ink"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    setEditing(null);
                    setRows((r) => r.filter((_, j) => j !== i));
                  }}
                >
                  Remove statement
                </button>
              </div>
            </div>
          ) : (
            <p
              key={i}
              id={`sv-${i}`}
              tabIndex={0}
              role="button"
              aria-label={`Edit statement ${i + 1}`}
              onClick={(e) => {
                if ((e.target as HTMLElement).closest('a')) return;
                setEditing(i);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  setEditing(i);
                }
              }}
              className="-mx-3 cursor-text rounded-md px-3 py-0.5 text-[16px] leading-[1.7] text-ink transition-colors hover:bg-paper focus-visible:bg-paper focus-visible:outline-none"
            >
              <span className={bad ? 'underline decoration-amber decoration-[1.5px] underline-offset-[5px]' : undefined}>
                {s.text || <span className="text-faint">Empty statement</span>}
              </span>
              {nums.length > 0 && (
                <sup className="ml-0.5 text-[10.5px] font-medium text-accent">
                  {nums.map((n, k) => (
                    <span key={n}>
                      {k > 0 && ','}
                      <a href={`#src-${n}`} className="hover:underline">
                        {n}
                      </a>
                    </span>
                  ))}
                </sup>
              )}
            </p>
          );
        })}
      </div>

      <button
        type="button"
        className="mt-4 rounded-md px-0 text-[13.5px] text-muted hover:text-ink"
        onClick={() => {
          setRows((r) => [...r, { text: '', refs: [] }]);
          setEditing(rows.length);
        }}
      >
        Add a statement
      </button>

      {violations.length > 0 && (
        <div className="mt-6">
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="text-left text-[14px] font-medium text-amber hover:underline">
            {violations.length} {violations.length === 1 ? 'statement' : 'statements'} could not be verified — review {violations.length === 1 ? 'it' : 'them'}
            <span className="ml-2 text-muted">{open ? 'Hide' : 'Show'}</span>
          </button>
          {open && (
            <ul className="mt-3 space-y-2 text-[14px] leading-relaxed">
              {violations.map((v, k) => {
                const idx = violationIndex(v);
                const s = idx !== null ? rows[idx] : undefined;
                return (
                  <li key={k} className="text-ink/85">
                    {idx !== null ? (
                      <a href={`#sv-${idx}`} className="font-medium text-ink hover:underline">
                        Statement {idx + 1}
                      </a>
                    ) : (
                      <span className="font-medium text-ink">Section V</span>
                    )}
                    <span className="text-muted"> — {violationText(v)}</span>
                    {s && <span className="block text-[13px] text-muted">“{s.text.length > 110 ? `${s.text.slice(0, 110)}…` : s.text}”</span>}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function SourcesList({ sources }: { sources: SourceEntry[] }) {
  if (!sources.length) return null;
  return (
    <ol className="space-y-3">
      {sources.map((s) => (
        <li key={s.key} id={`src-${s.n}`} className="grid scroll-mt-24 grid-cols-[28px_1fr] text-[14px] leading-relaxed">
          <span className="tnum text-accent">{s.n}</span>
          <span>
            <span className={s.key.includes(':') ? 'font-mono text-[12.5px] text-ink' : 'font-medium text-ink'}>{s.label}</span>
            {s.meaning && <span className="text-muted"> — {s.meaning}</span>}
            {s.detail.length > 0 && <span className="mt-0.5 block font-mono text-[11.5px] leading-relaxed text-faint">{s.detail.join(', ')}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
