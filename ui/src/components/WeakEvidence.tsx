import { CartesianGrid, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useI18n } from '../i18n';
import type { WeakEvidenceExperiment, WeakRun, WeakSplit } from '../types';
import { Card, DatasetLine, NA } from './ui';

const CHART_VARIANTS = ['baseline', 'weak_0.05', 'weak_0.10', 'weak_0.20', 'weak_0.40'] as const;

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

function mean(xs: (number | undefined)[]): number | null {
  const v = xs.filter(isNum);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

/** Mean of a run statistic over all seeds of a split, for one variant. */
function meanOver(split: WeakSplit | undefined, variant: string, f: (r: WeakRun) => number | undefined): number | null {
  if (!split) return null;
  return mean(Object.values(split).map((byVariant) => (byVariant?.[variant] ? f(byVariant[variant]) : undefined)));
}

function nSeeds(split?: WeakSplit) {
  return split ? Object.keys(split).length : 0;
}

interface Pt {
  variant: string;
  tokens: number;
  ghost: number | null;
  original: number | null;
}

function series(split: WeakSplit | undefined): Pt[] {
  return CHART_VARIANTS.map((v) => ({
    variant: v,
    tokens: meanOver(split, v, (r) => r.exported_tokens) ?? NaN,
    ghost: meanOver(split, v, (r) => r.staj_psi?.ghost_recall),
    original: meanOver(split, v, (r) => r.staj_psi?.original_recall),
  })).filter((p) => isNum(p.tokens) && p.tokens > 0);
}

export default function WeakEvidence({ x, dataset, seed }: { x: WeakEvidenceExperiment; dataset?: string; seed?: number }) {
  const { t, num, pct, lang } = useI18n();
  const dev = series(x.dev);
  const held = series(x.held_out);
  const cs = lang === 'cs';

  const tip = {
    contentStyle: { background: 'rgb(var(--surface))', border: '1px solid rgb(var(--line))', borderRadius: 6, fontSize: 12 },
  };

  return (
    <Card title={t('w.title')} right={<DatasetLine dataset={dataset} seed={seed} />} sub={t('w.caption')}>
      <div className="space-y-6">
        {x.preregistration && (
          <p className="rounded-md border border-line bg-paper/60 px-3 py-2 text-xs leading-relaxed">
            <span className="font-semibold">{t('w.prereg')}:</span> {x.preregistration}
          </p>
        )}
        {x.frozen_config && (
          <p className="text-xs text-muted">
            {t('w.frozen')}:{' '}
            {Object.entries(x.frozen_config).map(([k, v]) => (
              <span key={k} className="mr-3">
                <span className="mono">{k}</span> = <span className="mono text-ink">{String(v)}</span>
              </span>
            ))}
          </p>
        )}

        <div>
          <h3 className="text-sm font-semibold">{t('w.chart')}</h3>
          <p className="text-xs text-muted">
            {t('w.chart_sub')} · dev n = {nSeeds(x.dev)} · held-out n = {nSeeds(x.held_out)}
          </p>
          {dev.length + held.length === 0 ? (
            <NA />
          ) : (
            <div
              className="mt-2 h-[320px] w-full"
              role="img"
              aria-label={[...held.map((p) => `held-out ${p.variant}: tokens ${Math.round(p.tokens)}, ghost ${p.ghost ?? '–'}, original ${p.original ?? '–'}`)].join('; ')}
            >
              <ResponsiveContainer>
                <LineChart margin={{ top: 16, right: 24, bottom: 8, left: 0 }}>
                  <CartesianGrid stroke="rgb(var(--line))" />
                  <XAxis
                    type="number"
                    dataKey="tokens"
                    scale="log"
                    domain={['auto', 'auto']}
                    allowDataOverflow
                    tick={{ fontSize: 10, fill: 'rgb(var(--muted))' }}
                    tickFormatter={(v: number) => num(v)}
                    stroke="rgb(var(--line))"
                    label={{ value: t('w.x'), position: 'insideBottom', offset: -4, fontSize: 11, fill: 'rgb(var(--muted))' }}
                    height={40}
                  />
                  <YAxis
                    type="number"
                    domain={[0, 1]}
                    tick={{ fontSize: 10, fill: 'rgb(var(--muted))' }}
                    tickFormatter={(v: number) => pct(v, 0)}
                    width={44}
                    stroke="rgb(var(--line))"
                  />
                  <Tooltip
                    {...tip}
                    labelFormatter={(v) => `${t('w.tokens')}: ${num(Number(v))}`}
                    formatter={(v: unknown, name: unknown, p: { payload?: Pt }) => [`${isNum(v) ? pct(v, 0) : '–'} (${p.payload?.variant ?? ''})`, String(name)]}
                  />
                  <Legend verticalAlign="top" wrapperStyle={{ fontSize: 11, paddingBottom: 8 }} />
                  {/* Colour = metric (ghost vs original), dash = split (dev dashed, held-out solid). */}
                  <Line data={held} dataKey="ghost" name={`${t('w.ghost')} · held-out`} stroke="rgb(var(--c-out))" strokeWidth={2} dot={{ r: 4 }} isAnimationActive={false} connectNulls>
                    <LabelList dataKey="variant" position="top" fontSize={9} fill="rgb(var(--muted))" />
                  </Line>
                  <Line data={dev} dataKey="ghost" name={`${t('w.ghost')} · dev`} stroke="rgb(var(--c-out))" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 4 }} isAnimationActive={false} connectNulls />
                  <Line data={held} dataKey="original" name={`${t('w.original')} · held-out`} stroke="rgb(var(--c-in))" strokeWidth={2} dot={{ r: 4 }} isAnimationActive={false} connectNulls />
                  <Line data={dev} dataKey="original" name={`${t('w.original')} · dev`} stroke="rgb(var(--c-in))" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 4 }} isAnimationActive={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <CompareTable split={x.held_out} title={t('w.table')} />
        {x.dev_without_ghost_ring && <CompareTable split={x.dev_without_ghost_ring} title={t('w.table_noghost')} />}
        <p className="text-[11px] text-muted">{cs ? 'Hodnoty jsou průměry přes seedy dané části (TP/FP/FN také průměr).' : 'Values are means over the seeds of the split (TP/FP/FN are means too).'}</p>
      </div>
    </Card>
  );
}

function ratio(a: number | null, b: number | null) {
  if (!isNum(a) || !isNum(b) || a === 0) return null;
  return b / a;
}

function CompareTable({ split, title }: { split?: WeakSplit; title: string }) {
  const { t, num, pct } = useI18n();
  if (!split || !Object.keys(split).length) return null;
  const A = 'baseline';
  const B = 'weak_0.05';
  const m = (v: string, f: (r: WeakRun) => number | undefined) => meanOver(split, v, f);
  const rows: { k: string; f: (r: WeakRun) => number | undefined; fmt: (n: number) => string; ratio?: boolean }[] = [
    { k: t('w.ghost'), f: (r) => r.staj_psi?.ghost_recall, fmt: (n) => pct(n, 0) },
    { k: `${t('w.ghost')} (${t('mode.isolated')})`, f: (r) => r.isolated?.ghost_recall, fmt: (n) => pct(n, 0) },
    { k: t('w.original'), f: (r) => r.staj_psi?.original_recall, fmt: (n) => pct(n, 0) },
    { k: 'TP', f: (r) => r.staj_psi?.tp, fmt: (n) => num(n, 1) },
    { k: 'FP', f: (r) => r.staj_psi?.fp, fmt: (n) => num(n, 1) },
    { k: 'FN', f: (r) => r.staj_psi?.fn, fmt: (n) => num(n, 1) },
    { k: t('w.tokens'), f: (r) => r.exported_tokens, fmt: (n) => num(n, 0), ratio: true },
    { k: t('r.bytes'), f: (r) => r.bytes, fmt: (n) => (n >= 1e6 ? `${num(n / 1e6, 2)} MB` : `${num(n / 1e3, 1)} kB`), ratio: true },
    { k: t('w.non_mule'), f: (r) => r.disclosed_candidates_non_mule, fmt: (n) => num(n, 1), ratio: true },
  ];
  return (
    <div>
      <h3 className="text-sm font-semibold">
        {title} <span className="font-normal text-muted">· n = {Object.keys(split).length} seeds</span>
      </h3>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse text-sm">
          <thead className="border-b border-line">
            <tr>
              <th className="th">&nbsp;</th>
              <th className="th mono text-right">{A}</th>
              <th className="th mono text-right">{B}</th>
              <th className="th text-right">{t('w.ratio')}</th>
            </tr>
          </thead>
          <tbody className="tnum">
            {rows.map((r) => {
              const a = m(A, r.f);
              const b = m(B, r.f);
              const q = r.ratio ? ratio(a, b) : null;
              return (
                <tr key={r.k} className="border-b border-line/70 last:border-0">
                  <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                    {r.k}
                  </th>
                  <td className="px-3 py-1.5 text-right">{isNum(a) ? r.fmt(a) : '–'}</td>
                  <td className="px-3 py-1.5 text-right font-semibold">{isNum(b) ? r.fmt(b) : '–'}</td>
                  <td className={`px-3 py-1.5 text-right ${q && q > 1 ? 'text-warn' : 'text-muted'}`}>{q === null ? '' : `×${num(q, 1)}`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
