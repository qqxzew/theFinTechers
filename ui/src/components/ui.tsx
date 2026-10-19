import type { ReactNode } from 'react';
import { useI18n } from '../i18n';
import type { DecisionStatus, Route, Triage } from '../types';

type Tone = 'neutral' | 'teal' | 'navy' | 'warn' | 'bad' | 'good' | 'violet' | 'outline';

const TONES: Record<Tone, string> = {
  neutral: 'bg-paper text-muted border-line',
  teal: 'bg-tealsoft text-teal border-teal/30',
  navy: 'bg-navy/10 text-navy border-navy/25',
  warn: 'bg-warnsoft text-warn border-warn/35',
  bad: 'bg-badsoft text-bad border-bad/30',
  good: 'bg-goodsoft text-good border-good/30',
  violet: 'bg-violetsoft text-violet border-violet/30',
  outline: 'bg-transparent text-ink border-line',
};

export function Chip({ tone = 'neutral', children, title, className = '', mono = false }: { tone?: Tone; children: ReactNode; title?: string; className?: string; mono?: boolean }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-[1px] text-[11px] font-medium leading-4 ${mono ? 'font-mono' : ''} ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/** Thin horizontal bar for priority (0..100) or score (0..1). */
export function Bar({ value, max = 1, tone = 'navy', label, width = 'w-20' }: { value: number; max?: number; tone?: 'navy' | 'warn' | 'teal' | 'bad' | 'good'; label?: string; width?: string }) {
  const pct = Math.max(0, Math.min(1, value / max)) * 100;
  const color = { navy: 'bg-navy', warn: 'bg-warn', teal: 'bg-teal', bad: 'bg-bad', good: 'bg-good' }[tone];
  return (
    <span className="inline-flex items-center gap-2" aria-label={label}>
      <span className={`relative h-1.5 ${width} overflow-hidden rounded-full bg-line`} aria-hidden="true">
        <span className={`absolute inset-y-0 left-0 ${color}`} style={{ width: `${pct}%` }} />
      </span>
    </span>
  );
}

export function PriorityBar({ p }: { p: number }) {
  const tone = p >= 85 ? 'bad' : p >= 70 ? 'warn' : p >= 40 ? 'navy' : 'teal';
  return (
    <span className="inline-flex items-center gap-2">
      <span className="tnum w-7 text-right text-sm font-semibold">{p}</span>
      <Bar value={p} max={100} tone={tone} width="w-16" label={`priority ${p}`} />
    </span>
  );
}

export function TriageChip({ triage }: { triage: Triage | string }) {
  return (
    <Chip tone={triage === 'FP' ? 'good' : 'navy'} title={triage === 'FP' ? 'proposed auto-close' : 'proposed human review'}>
      {triage}
    </Chip>
  );
}

export function RouteChip({ route }: { route: Route | string }) {
  const { t } = useI18n();
  if (route !== 'victim_protection') return null;
  return <Chip tone="violet">{t('route.victim_protection')}</Chip>;
}

export function StatusChip({ status }: { status: DecisionStatus }) {
  const { t } = useI18n();
  const tone: Tone = status === 'open' ? 'outline' : status === 'confirmed' ? 'teal' : 'warn';
  return <Chip tone={tone}>{t(`status.${status}`)}</Chip>;
}

export function RuleChip({ rule, title }: { rule: string; title?: string }) {
  const tone: Tone = rule === 'X' ? 'warn' : rule.startsWith('R-') ? 'neutral' : 'outline';
  return (
    <Chip tone={tone} mono title={title}>
      {rule}
    </Chip>
  );
}

export function ClusterBadge({ id }: { id: string | null }) {
  if (!id) return <span className="text-muted">–</span>;
  return (
    <Chip tone="warn" mono>
      ◆ {id}
    </Chip>
  );
}

export function Card({ title, sub, right, children, className = '', id }: { title?: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section className={`card ${className}`} aria-labelledby={id ? `${id}-h` : undefined}>
      {(title || right) && (
        <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && (
              <h2 id={id ? `${id}-h` : undefined} className="card-h">
                {title}
              </h2>
            )}
            {sub && <p className="card-sub mt-0.5">{sub}</p>}
          </div>
          {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Loading() {
  const { t } = useI18n();
  return (
    <div role="status" className="flex items-center gap-2 p-6 text-sm text-muted">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-teal" aria-hidden="true" />
      {t('common.loading')}
    </div>
  );
}

export function ErrorBox({ error, onRetry, message }: { error: string; onRetry?: () => void; message?: string }) {
  const { t } = useI18n();
  return (
    <div role="alert" className="rounded-md border border-bad/30 bg-badsoft p-4 text-sm text-bad">
      <p className="font-semibold">{message ?? t('common.error')}</p>
      <p className="mono mt-1 break-all opacity-80">{error}</p>
      {onRetry && (
        <button className="btn-secondary mt-3" onClick={onRetry}>
          {t('common.retry')}
        </button>
      )}
    </div>
  );
}

export function NA() {
  const { t } = useI18n();
  return <span className="text-sm italic text-muted">{t('common.na')}</span>;
}

export function SyntheticBadge() {
  const { t } = useI18n();
  return <Chip tone="warn">{t('chip.synthetic')}</Chip>;
}

export function DatasetLine({ dataset, seed }: { dataset?: string; seed?: number }) {
  const { t } = useI18n();
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
      <SyntheticBadge />
      <span>
        {t('common.dataset')}: <span className="mono text-ink">{dataset ?? t('common.na')}</span>
      </span>
      <span>
        · {t('common.seed')}: <span className="mono tnum text-ink">{seed ?? t('common.na')}</span>
      </span>
    </span>
  );
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export const short = (h: string | null | undefined, n = 10) => (h ? `${h.slice(0, n)}…` : '–');

export function fmtScalar(v: unknown, num: (n: number, d?: number) => string): string {
  if (v === null || v === undefined) return '–';
  if (typeof v === 'number') return Number.isInteger(v) ? num(v) : num(v, Math.abs(v) < 1 ? 2 : 1);
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (Array.isArray(v)) return v.map((x) => fmtScalar(x, num)).join(', ');
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

/** Generic renderer for violation objects the server returns; never hides any field. */
export function ViolationList({ items, title }: { items: unknown[]; title: string }) {
  if (!items.length) return null;
  return (
    <div role="alert" className="rounded-md border border-warn/40 bg-warnsoft p-3 text-sm">
      <p className="font-semibold text-warn">
        {title} ({items.length})
      </p>
      <ul className="mt-2 space-y-1.5">
        {items.map((v, i) => (
          <li key={i} className="text-ink">
            {typeof v === 'string' ? (
              <span className="mono">{v}</span>
            ) : (
              <span className="flex flex-wrap gap-x-3 gap-y-0.5">
                {Object.entries(v as Record<string, unknown>).map(([k, val]) => (
                  <span key={k}>
                    <span className="text-muted">{k}:</span> <span className={k === 'detail' ? '' : 'mono'}>{typeof val === 'object' ? JSON.stringify(val) : String(val)}</span>
                  </span>
                ))}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
