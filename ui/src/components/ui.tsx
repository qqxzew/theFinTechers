/*
 * Stáj UI primitives. Rules: light only, no borders (shadow delimits), colour only for meaning
 * (ink text, grey secondary, one ink-blue accent, amber for rare warnings), tabular numbers,
 * monospace only for ids and hashes. See ui/README.md "Primitives".
 */
import { useRef, type ButtonHTMLAttributes, type KeyboardEvent, type ReactNode } from 'react';

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

/* ------------------------------------------------------------------ layout */

/** Page wrapper: max content width, vertical rhythm between sections. */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('mx-auto w-full max-w-content space-y-10 pb-16', className)}>{children}</div>;
}

/** Page title with optional one-line description and right-aligned actions. */
export function PageTitle({ title, description, actions }: { title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-[15px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** A titled block of the page. `explain` is one plain line saying what this is. */
export function Section({
  title,
  explain,
  actions,
  children,
  id,
  className,
}: {
  title: ReactNode;
  explain?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
  className?: string;
}) {
  return (
    <section aria-labelledby={id ? `${id}-h` : undefined} className={cx('space-y-4', className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          <h2 id={id ? `${id}-h` : undefined} className="text-[17px] font-semibold tracking-tight text-ink">
            {title}
          </h2>
          {explain && <p className="mt-0.5 max-w-3xl text-[14px] text-muted">{explain}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

/** White surface lifted by a soft shadow. `title`/`sub`/`right` make an optional header. */
export function Card({
  title,
  sub,
  right,
  children,
  className,
  id,
  interactive = false,
  padded = true,
}: {
  title?: ReactNode;
  sub?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  interactive?: boolean;
  padded?: boolean;
}) {
  return (
    <section
      className={cx('card', interactive && 'transition-shadow duration-150 hover:shadow-raise', className)}
      aria-labelledby={id && title ? `${id}-h` : undefined}
    >
      {(title || right) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-6 pt-5">
          <div className="min-w-0">
            {title && (
              <h3 id={id ? `${id}-h` : undefined} className="card-h">
                {title}
              </h3>
            )}
            {sub && <p className="card-sub mt-0.5">{sub}</p>}
          </div>
          {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
        </header>
      )}
      <div className={padded ? 'px-6 pb-6 pt-4' : ''}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ controls */

type ButtonVariant = 'primary' | 'secondary' | 'quiet';

export function Button({ variant = 'secondary', className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return <button {...rest} className={cx(`btn-${variant}`, className)} />;
}

/** Neutral label. Emphasis is by weight, never by colour; `warn` (amber text) is for rare real warnings. */
export function Tag({
  children,
  tone = 'default',
  mono = false,
  title,
  className,
}: {
  children: ReactNode;
  tone?: 'default' | 'strong' | 'muted' | 'warn';
  mono?: boolean;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={cx(
        'inline-flex items-center whitespace-nowrap rounded-md bg-sunken px-1.5 py-[1px] text-[12px] leading-5',
        mono && 'font-mono text-[11.5px]',
        tone === 'strong' && 'font-semibold text-ink',
        tone === 'default' && 'font-medium text-ink/80',
        tone === 'muted' && 'text-muted',
        tone === 'warn' && 'bg-ambersoft font-semibold text-amber',
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Big number with a one-line label. */
export function Stat({ value, label, hint, emphasis = false }: { value: ReactNode; label: ReactNode; hint?: ReactNode; emphasis?: boolean }) {
  return (
    <div className="min-w-0">
      <div className={cx('tnum text-[30px] font-semibold leading-none tracking-tight', emphasis ? 'text-accent' : 'text-ink')}>{value}</div>
      <div className="mt-2 text-[13px] text-muted">{label}</div>
      {hint && <div className="mt-0.5 text-[12px] text-faint">{hint}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ table */

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: 'left' | 'right';
  sortable?: boolean;
  width?: string;
}

/**
 * Clean data table: sticky header, row hover lift, keyboard navigation
 * (Tab into a row, Arrow Up/Down to move, Enter to open).
 */
export function Table<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  rowLabel,
  sort,
  onSort,
  caption,
  maxHeight = '70vh',
  empty,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (r: T) => string;
  onRowClick?: (r: T) => void;
  rowLabel?: (r: T) => string;
  sort?: { key: string; dir: 1 | -1 };
  onSort?: (key: string) => void;
  caption?: string;
  maxHeight?: string;
  empty?: ReactNode;
}) {
  const body = useRef<HTMLTableSectionElement>(null);
  const move = (e: KeyboardEvent<HTMLTableRowElement>, r: T) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onRowClick?.(r);
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const sib = (e.key === 'ArrowDown' ? e.currentTarget.nextElementSibling : e.currentTarget.previousElementSibling) as HTMLElement | null;
      sib?.focus();
    }
  };
  if (!rows.length) return <>{empty ?? <EmptyState title="Nothing to show" />}</>;
  return (
    <div className="card overflow-auto" style={{ maxHeight }}>
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="sticky top-0 z-10 bg-surface" style={{ boxShadow: '0 1px 0 rgb(22 24 29 / 0.06)' }}>
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  scope="col"
                  style={c.width ? { width: c.width } : undefined}
                  className={cx('th', c.align === 'right' && 'text-right')}
                  aria-sort={active ? (sort!.dir === 1 ? 'ascending' : 'descending') : undefined}
                >
                  {c.sortable && onSort ? (
                    <button className={cx('inline-flex items-center gap-1 rounded hover:text-ink', active && 'text-ink')} onClick={() => onSort(c.key)}>
                      {c.header}
                      <span aria-hidden="true" className="text-[10px] text-faint">
                        {active ? (sort!.dir === 1 ? '↑' : '↓') : ''}
                      </span>
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody ref={body}>
          {rows.map((r) => (
            <tr
              key={rowKey(r)}
              tabIndex={onRowClick ? 0 : undefined}
              aria-label={rowLabel?.(r)}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              onKeyDown={onRowClick ? (e) => move(e, r) : undefined}
              className={cx(onRowClick && 'cursor-pointer transition-colors hover:bg-paper focus-visible:bg-accentsoft/60')}
            >
              {columns.map((c) => (
                <td key={c.key} className={cx('td', c.align === 'right' && 'text-right')}>
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ data marks */

/** Thin monochrome bar (0..max). `warn` turns it amber; use only for a real threshold. */
export function Bar({ value, max = 1, tone, label, width = 'w-20' }: { value: number; max?: number; tone?: string; label?: string; width?: string }) {
  const pctv = Math.max(0, Math.min(1, value / max)) * 100;
  const amber = tone === 'warn' || tone === 'bad';
  return (
    <span className={cx('relative inline-block h-1 overflow-hidden rounded-full bg-sunken align-middle', width)} role="img" aria-label={label ?? `${value}`}>
      <span className={cx('absolute inset-y-0 left-0 rounded-full', amber ? 'bg-amber' : 'bg-ink/70')} style={{ width: `${pctv}%` }} />
    </span>
  );
}

/** Priority 0..100: ink number plus thin ink bar; the bar turns amber only at or above `threshold`. */
export function PriorityBar({ p, threshold = 90 }: { p: number; threshold?: number }) {
  const hot = p >= threshold;
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="tnum w-7 text-right text-sm font-semibold text-ink">{p}</span>
      <Bar value={p} max={100} tone={hot ? 'warn' : undefined} width="w-14" label={`priority ${p}`} />
    </span>
  );
}

/* ------------------------------------------------------------------ states */

export function EmptyState({ title, hint, action }: { title: ReactNode; hint?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-start gap-1 px-6 py-8">
      <p className="text-[15px] font-medium text-ink">{title}</p>
      {hint && <p className="text-sm text-muted">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 px-1 py-6 text-sm text-muted">
      <span className="relative h-1 w-16 overflow-hidden rounded-full bg-sunken" aria-hidden="true">
        <span className="absolute inset-y-0 left-0 w-2/5 animate-pulsebar rounded-full bg-accent/70" />
      </span>
      {label}
    </div>
  );
}

export function ErrorBox({ error, onRetry, message }: { error: string; onRetry?: () => void; message?: string }) {
  return (
    <div role="alert" className="card px-6 py-5 text-sm">
      <p className="font-semibold text-amber">{message ?? 'Could not load this.'}</p>
      <p className="mono mt-1 break-all text-muted">{error}</p>
      {onRetry && (
        <Button className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function NA() {
  return <span className="text-sm text-faint">not available</span>;
}

/** Server findings (QA, rule violations). Never hidden; shown as a quiet amber panel. */
export function ViolationList({ items, title, total }: { items: unknown[]; title: string; total?: number }) {
  if (!items.length) return null;
  return (
    <div role="alert" className="rounded-lg bg-ambersoft px-4 py-3 text-sm">
      <p className="font-semibold text-amber">
        {title} <span className="tnum font-normal">({total ?? items.length})</span>
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

/* ------------------------------------------------------------------ helpers */

export const short = (h: string | null | undefined, n = 10) => (!h ? '–' : h.length <= n + 1 ? h : `${h.slice(0, n)}…`);

export function fmtScalar(v: unknown, num: (n: number, d?: number) => string): string {
  if (v === null || v === undefined) return '–';
  if (typeof v === 'number') return Number.isInteger(v) ? num(v) : num(v, Math.abs(v) < 1 ? 2 : 1);
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  if (Array.isArray(v)) return v.map((x) => fmtScalar(x, num)).join(', ');
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

/* ------------------------------------------------------------------
 * Compatibility layer for screens written before the redesign.
 * These keep old call sites compiling but render with the new neutral look.
 * New code should use Tag / PageTitle / Stat directly.
 * ------------------------------------------------------------------ */

type LegacyTone = 'neutral' | 'teal' | 'navy' | 'warn' | 'bad' | 'good' | 'violet' | 'outline';

/** @deprecated use Tag */
export function Chip({ tone = 'neutral', children, title, className, mono = false }: { tone?: LegacyTone; children: ReactNode; title?: string; className?: string; mono?: boolean }) {
  return (
    <Tag tone={tone === 'bad' ? 'warn' : tone === 'navy' ? 'strong' : 'default'} mono={mono} title={title} className={className}>
      {children}
    </Tag>
  );
}

/** @deprecated use PageTitle */
export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-8">
      <PageTitle title={title} actions={children} />
    </div>
  );
}

export function TriageChip({ triage }: { triage: string }) {
  return <Tag tone={triage === 'REVIEW' ? 'strong' : 'muted'}>{triage === 'REVIEW' ? 'Review' : triage === 'FP' ? 'Close (FP)' : triage}</Tag>;
}

export function RouteChip({ route }: { route: string }) {
  if (route !== 'victim_protection') return null;
  return <Tag tone="strong">Victim protection</Tag>;
}

export function StatusChip({ status }: { status: string }) {
  if (status === 'open') return <span className="text-sm text-faint">open</span>;
  return <span className="text-sm font-medium text-ink">{status}</span>;
}

export function RuleChip({ rule, title }: { rule: string; title?: string }) {
  return (
    <span title={title} className={cx('font-mono text-[12px]', rule === 'X' ? 'font-semibold text-ink' : 'text-muted')}>
      {rule}
    </span>
  );
}

export function ClusterBadge({ id }: { id: string | null }) {
  if (!id) return <span className="text-faint">–</span>;
  return <span className="font-mono text-[12px] text-ink">{short(id, 8)}</span>;
}

/** The data label now lives in one quiet place per page; this renders nothing. */
export function SyntheticBadge() {
  return null;
}

/** Quiet provenance line: synthetic data, dataset, seed. */
export function DatasetLine({ dataset, seed }: { dataset?: string; seed?: number }) {
  return (
    <span className="text-[12px] text-faint">
      Synthetic data
      {dataset && (
        <>
          {' '}
          · <span className="font-mono">{dataset}</span>
        </>
      )}
      {seed !== undefined && <> · seed {seed}</>}
    </span>
  );
}
