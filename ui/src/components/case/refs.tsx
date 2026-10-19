// Evidence references: a brief/answer sentence cites refs like "D7:R03024", "features.in_total" or
// "cluster.n_other_banks". Each resolves to one element on the page; clicking the small [n] scrolls to it
// and softly lifts it for a moment.
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import type { CaseDetail, Sentence } from '../../types';

/** Feature keys shown as rows of the Client card. */
export const CLIENT_FACT_KEYS: Record<string, string> = {
  days_since_contract: 'since',
  contract_form: 'contract',
  client_type: 'type',
  aml_risk: 'risk',
  pep: 'pep',
  expected_monthly: 'expected',
  july_total: 'july',
};

interface RefCtx {
  hl: string | null;
  focus: (target: string) => void;
  resolve: (ref: string) => string | null;
}

const Ctx = createContext<RefCtx>({ hl: null, focus: () => undefined, resolve: () => null });

export function RefProvider({ data, children }: { data: CaseDetail; children: ReactNode }) {
  const [hl, setHl] = useState<string | null>(null);
  const timer = useRef<number>();
  const resolve = useMemo(() => {
    const all = [...data.signals, ...data.exculpatory];
    const ids = new Set(all.map((s) => s.signal_id));
    const det = new Map(all.map((s) => [s.detector_id, s.signal_id]));
    return (ref: string): string | null => {
      const r = ref.trim();
      if (ids.has(r)) return `sig-${r}`;
      const head = r.split(/[.:]/)[0];
      const dot = r.indexOf('.');
      if (dot > 0 && ids.has(r.slice(0, dot))) return `sig-${r.slice(0, dot)}`;
      if (/^cluster/.test(r) || head === 'X') return data.cluster ? 'case-network' : det.has('X') ? `sig-${det.get('X')}` : null;
      const f = /^features?[.:](.+)$/.exec(r);
      if (f) {
        const k = f[1];
        if (k in CLIENT_FACT_KEYS) return `fact-${k}`;
        const owner = all.find((s) => k in s.evidence);
        if (owner) return `sig-${owner.signal_id}`;
        return 'case-money';
      }
      if (det.has(head)) return `sig-${det.get(head)}`;
      return null;
    };
  }, [data]);

  const focus = useCallback((target: string) => {
    const el = document.getElementById(target);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setHl(target);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setHl(null), 2600);
  }, []);

  const value = useMemo(() => ({ hl, focus, resolve }), [hl, focus, resolve]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useRefs = () => useContext(Ctx);

/** Class for an element that can be highlighted by a ref click. */
export function hlClass(on: boolean) {
  return `transition-[background-color,box-shadow] duration-500 ${on ? 'bg-accentsoft/70 shadow-raise' : ''}`;
}

/** Sentences with small superscript [n] refs, numbered by distinct target within this list. */
export function CitedSentences({ items, className, size = 'text-[15px]' }: { items: Sentence[]; className?: string; size?: string }) {
  const { resolve, focus } = useRefs();
  const order: string[] = [];
  const rows = items.map((s) => {
    const targets: string[] = [];
    for (const r of s.refs) {
      const t = resolve(r);
      if (!t || targets.includes(t) || targets.length >= 3) continue;
      targets.push(t);
      if (!order.includes(t)) order.push(t);
    }
    return { text: s.text, targets };
  });
  return (
    <div className={className}>
      {rows.map((r, i) => (
        <span key={i} className={`${size} leading-relaxed text-ink`}>
          {r.text}
          {r.targets.map((t) => (
            <sup key={t} className="ml-[1px]">
              <button
                type="button"
                onClick={() => focus(t)}
                className="tnum rounded px-[2px] text-[11px] font-semibold text-accent hover:underline"
                aria-label={`Show evidence ${order.indexOf(t) + 1}`}
              >
                [{order.indexOf(t) + 1}]
              </button>
            </sup>
          ))}{' '}
        </span>
      ))}
    </div>
  );
}

/** Server findings on generated text, as plain sentences. */
export function violationText(v: Record<string, unknown> | string): string {
  if (typeof v === 'string') return v.replace(/_/g, ' ');
  const d = v.detail ?? v.message ?? v.reason;
  const idx = typeof v.sentence_index === 'number' ? `Sentence ${v.sentence_index + 1}: ` : '';
  if (typeof d === 'string') return idx + d;
  if (typeof v.check === 'string') return idx + v.check.replace(/_/g, ' ');
  return idx + JSON.stringify(v);
}
