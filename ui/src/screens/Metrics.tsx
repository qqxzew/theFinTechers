import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Bar as RBar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getMetrics, resolveApiUrl } from '../api';
import { Bar, Card, Chip, DatasetLine, ErrorBox, Loading, NA, PageHeader, fmtScalar } from '../components/ui';
import { useI18n, type I18nKey } from '../i18n';
import { useAsync } from '../state';
import type { Confusion, MetricsResponse } from '../types';

const MODES = ['isolated', 'staj_psi', 'naive_raw_sharing'] as const;

export default function MetricsScreen() {
  const { t } = useI18n();
  const m = useAsync(getMetrics, []);
  return (
    <div className="space-y-5">
      <PageHeader title={t('m.title')}>{m.data && <DatasetLine dataset={m.data.dataset} seed={m.data.seed} />}</PageHeader>
      {m.loading && !m.data ? <Loading /> : m.error ? <ErrorBox error={m.error} onRetry={m.reload} /> : m.data ? <MetricsView d={m.data} /> : null}
    </div>
  );
}

function Block({ title, d, children, className = '', sub }: { title: string; d: MetricsResponse; children: ReactNode; className?: string; sub?: ReactNode }) {
  return (
    <Card title={title} sub={sub} right={<DatasetLine dataset={d.dataset} seed={d.seed} />} className={className}>
      {children}
    </Card>
  );
}

function isNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

function MetricCell({ v }: { v: unknown }) {
  const { num } = useI18n();
  if (!isNum(v)) return <NA />;
  return (
    <span className="inline-flex items-center gap-2">
      <span className="tnum w-10 text-right">{num(v, 3)}</span>
      <Bar value={v} tone="navy" width="w-14" />
    </span>
  );
}

function MetricsView({ d }: { d: MetricsResponse }) {
  const { t, num, pct, tx } = useI18n();
  const breakdown = d.breakdown ?? {};
  const groups: Record<'scheme' | 'persona' | 'victim' | 'other', [string, MetricsResponse['breakdown'][string]][]> = { scheme: [], persona: [], victim: [], other: [] };
  for (const [k, v] of Object.entries(breakdown)) {
    const p = k.split(':')[0];
    (p === 'scheme' || p === 'persona' || p === 'victim' ? groups[p] : groups.other).push([k.includes(':') ? k.slice(k.indexOf(':') + 1) : k, v]);
  }
  const full = d.ablations?.full;

  return (
    <>
      {d.operating_point && (
        <p className="rounded-md border border-line bg-surface px-4 py-2.5 text-sm">
          <span className="font-semibold">{t('m.operating_point')}:</span> {d.operating_point.definition}{' '}
          <Chip tone="navy" className="tnum">
            min_priority = {d.operating_point.min_priority}
          </Chip>
        </p>
      )}

      <Block title={t('m.modes')} d={d}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse">
            <thead className="border-b border-line">
              <tr>
                <th className="th">{t('r.mode')}</th>
                <th className="th">{t('m.precision')}</th>
                <th className="th">{t('m.recall')}</th>
                <th className="th">{t('m.f1')}</th>
                <th className="th text-right">TP</th>
                <th className="th text-right">FP</th>
                <th className="th text-right">FN</th>
                <th className="th text-right">mules / accounts</th>
              </tr>
            </thead>
            <tbody className="tnum">
              {MODES.map((k) => {
                const o = d.modes?.[k]?.overall;
                return (
                  <tr key={k} className={`border-b border-line/70 last:border-0 ${k === 'staj_psi' ? 'bg-tealsoft/40' : ''}`}>
                    <th scope="row" className="td text-left font-medium">
                      {t(`mode.${k}` as I18nKey)}
                    </th>
                    {o ? (
                      <>
                        <td className="td">
                          <MetricCell v={o.precision} />
                        </td>
                        <td className="td">
                          <MetricCell v={o.recall} />
                        </td>
                        <td className="td">
                          <MetricCell v={o.f1} />
                        </td>
                        <td className="td text-right">{fmtScalar(o.tp, num)}</td>
                        <td className="td text-right">{fmtScalar(o.fp, num)}</td>
                        <td className="td text-right">{fmtScalar(o.fn, num)}</td>
                        <td className="td text-right text-muted">
                          {fmtScalar(o.n_mules, num)} / {fmtScalar(o.n_accounts, num)}
                        </td>
                      </>
                    ) : (
                      <td className="td" colSpan={7}>
                        <NA />
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Block>

      <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
        <Block title={t('m.schemes')} d={d}>
          <BreakdownTable rows={groups.scheme} metric="flagged" />
        </Block>
        <Block title={t('m.personas')} d={d}>
          <BreakdownTable rows={groups.persona} metric="flagged" bad />
        </Block>
        <Block title={t('m.victims')} d={d}>
          <BreakdownTable rows={groups.victim} metric="victim" />
        </Block>
      </div>
      {groups.other.length > 0 && (
        <Block title={t('m.other')} d={d}>
          <BreakdownTable rows={groups.other} metric="flagged" />
        </Block>
      )}

      <Block title={t('m.ablations')} d={d}>
        {d.ablations && Object.keys(d.ablations).length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse">
              <thead className="border-b border-line">
                <tr>
                  <th className="th">variant</th>
                  <th className="th">{t('m.precision')}</th>
                  <th className="th">{t('m.recall')}</th>
                  <th className="th">{t('m.f1')}</th>
                  <th className="th text-right">ΔF1</th>
                  <th className="th text-right">TP / FP / FN</th>
                </tr>
              </thead>
              <tbody className="tnum">
                {Object.entries(d.ablations).map(([k, a]: [string, Confusion]) => {
                  const delta = full && isNum(a?.f1) && isNum(full.f1) ? a.f1 - full.f1 : null;
                  return (
                    <tr key={k} className="border-b border-line/70 last:border-0">
                      <th scope="row" className="td mono text-left font-medium">
                        {k === 'full' ? t('m.ablation_full') : k}
                      </th>
                      <td className="td">
                        <MetricCell v={a?.precision} />
                      </td>
                      <td className="td">
                        <MetricCell v={a?.recall} />
                      </td>
                      <td className="td">
                        <MetricCell v={a?.f1} />
                      </td>
                      <td className={`td text-right ${delta !== null && delta < 0 ? 'text-bad' : ''}`}>{delta === null || k === 'full' ? '–' : `${delta > 0 ? '+' : ''}${num(delta, 3)}`}</td>
                      <td className="td text-right text-muted">
                        {fmtScalar(a?.tp, num)} / {fmtScalar(a?.fp, num)} / {fmtScalar(a?.fn, num)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <NA />
        )}
      </Block>

      <div className="grid gap-5 xl:grid-cols-2">
        <Block title={t('m.worst_fp')} d={d}>
          <FailureList items={d.failures?.worst_false_positives} />
        </Block>
        <Block title={t('m.fn')} d={d}>
          <FailureList items={d.failures?.false_negatives} />
        </Block>
      </div>

      <Block title={t('m.cnb')} d={d}>
        {d.cnb ? (
          <div className="space-y-6">
            <p className="text-xs text-muted tnum">
              {num(d.cnb.n_clients)} {t('m.clients')} · {num(d.cnb.n_tx)} {t('m.tx')}
            </p>
            <div className="grid gap-6 lg:grid-cols-3">
              <div>
                <h3 className="label mb-2">{t('m.rule_a_units')}</h3>
                {d.cnb.rule_a_alerts_per_unit && Object.keys(d.cnb.rule_a_alerts_per_unit).length ? (
                  <table className="w-full text-sm tnum">
                    <tbody>
                      {Object.entries(d.cnb.rule_a_alerts_per_unit).map(([k, v]) => (
                        <tr key={k} className="border-b border-line/70 last:border-0">
                          <th scope="row" className="py-1.5 pr-3 text-left font-normal mono">
                            {k}
                          </th>
                          <td className="py-1.5 text-right font-semibold">{num(v)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <NA />
                )}
              </div>
              <div className="space-y-4">
                <div className="flex gap-8">
                  <Big n={isNum(d.cnb.rule_b_alerts) ? num(d.cnb.rule_b_alerts) : null} l={t('m.rule_b')} />
                  <Big n={isNum(d.cnb.rule_c_alerts) ? num(d.cnb.rule_c_alerts) : null} l={t('m.rule_c')} />
                </div>
                <div>
                  <h3 className="label mb-1.5">{t('m.rule_c_triage')}</h3>
                  {d.cnb.rule_c_triage ? <SplitBar fp={d.cnb.rule_c_triage.FP} review={d.cnb.rule_c_triage.REVIEW} /> : <NA />}
                </div>
              </div>
              <div className="space-y-4">
                <div>
                  <h3 className="label mb-1">{t('m.mom')}</h3>
                  {d.cnb.mom_persona ? (
                    <p className="tnum">
                      <span className="text-2xl font-semibold">{pct(d.cnb.mom_persona.fp_rate)}</span> <span className="text-xs text-muted">(n = {num(d.cnb.mom_persona.n)})</span>
                    </p>
                  ) : (
                    <NA />
                  )}
                </div>
                <div>
                  <h3 className="label mb-1">{t('m.sheet')}</h3>
                  {d.cnb.sample_sheet_url ? (
                    <a className="text-sm text-teal underline underline-offset-2" href={resolveApiUrl(d.cnb.sample_sheet_url)}>
                      {d.cnb.sample_sheet_url}
                    </a>
                  ) : (
                    <NA />
                  )}
                </div>
              </div>
            </div>
            <div>
              <h3 className="label mb-2">{t('m.hist')}</h3>
              {d.cnb.priority_hist?.length ? <Hist rows={d.cnb.priority_hist} /> : <NA />}
            </div>
          </div>
        ) : (
          <NA />
        )}
      </Block>
      <p className="text-xs text-muted">
        {tx('h.limitations')}:{' '}
        <Link to="/honesty" className="text-teal underline">
          {t('nav.honesty')}
        </Link>
      </p>
    </>
  );
}

function Big({ n, l }: { n: string | null; l: string }) {
  return (
    <div>
      <div className="tnum text-2xl font-semibold">{n ?? <NA />}</div>
      <div className="text-xs text-muted">{l}</div>
    </div>
  );
}

function SplitBar({ fp, review }: { fp: number; review: number }) {
  const { num } = useI18n();
  const tot = (fp ?? 0) + (review ?? 0);
  if (!tot) return <NA />;
  const f = (fp / tot) * 100;
  return (
    <div>
      <div className="flex h-2.5 w-full gap-[2px] overflow-hidden rounded-full" role="img" aria-label={`FP ${fp}, REVIEW ${review}`}>
        <span className="h-full bg-good" style={{ width: `${f}%` }} />
        <span className="h-full flex-1 bg-navy" />
      </div>
      <div className="mt-1.5 flex justify-between text-xs tnum">
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-good" aria-hidden="true" />
          FP {num(fp)} ({num(f, 0)} %)
        </span>
        <span>
          REVIEW {num(review)} ({num(100 - f, 0)} %)
          <span className="ml-1 inline-block h-2 w-2 rounded-sm bg-navy" aria-hidden="true" />
        </span>
      </div>
    </div>
  );
}

function Hist({ rows }: { rows: { bin: string; count: number }[] }) {
  const { num } = useI18n();
  return (
    <div className="h-[200px] w-full" role="img" aria-label={rows.map((r) => `${r.bin}: ${r.count}`).join(', ')}>
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barCategoryGap="18%">
          <CartesianGrid vertical={false} stroke="rgb(var(--line))" />
          <XAxis dataKey="bin" tick={{ fontSize: 10, fill: 'rgb(var(--muted))' }} stroke="rgb(var(--line))" />
          <YAxis tick={{ fontSize: 10, fill: 'rgb(var(--muted))' }} width={32} allowDecimals={false} stroke="rgb(var(--line))" />
          <Tooltip
            cursor={{ fill: 'rgb(var(--line) / 0.4)' }}
            contentStyle={{ background: 'rgb(var(--surface))', border: '1px solid rgb(var(--line))', borderRadius: 6, fontSize: 12 }}
            formatter={(v: number) => [num(v), 'count']}
          />
          <RBar dataKey="count" fill="rgb(var(--navy))" radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function BreakdownTable({ rows, metric, bad = false }: { rows: [string, { n: number; flagged_as_mule_case: number; routed_to_victim_protection: number; rate: number }][]; metric: 'flagged' | 'victim'; bad?: boolean }) {
  const { t, num, pct } = useI18n();
  if (!rows.length) return <NA />;
  return (
    <div className="overflow-x-auto">
    <table className="w-full border-collapse text-sm">
      <thead className="border-b border-line">
        <tr>
          <th className="th px-0">&nbsp;</th>
          <th className="th text-right">{t('m.n')}</th>
          <th className="th text-right">{metric === 'victim' ? t('m.routed_victim') : t('m.flagged')}</th>
          <th className="th">{t('m.rate')}</th>
        </tr>
      </thead>
      <tbody className="tnum">
        {rows.map(([k, v]) => (
          <tr key={k} className="border-b border-line/70 last:border-0">
            <th scope="row" className="py-1.5 pr-2 text-left font-normal mono text-[12px]">
              {k}
            </th>
            <td className="px-3 py-1.5 text-right text-muted">{fmtScalar(v?.n, num)}</td>
            <td className="px-3 py-1.5 text-right">
              {fmtScalar(metric === 'victim' ? v?.routed_to_victim_protection : v?.flagged_as_mule_case, num)}
              {metric === 'victim' && isNum(v?.flagged_as_mule_case) && v.flagged_as_mule_case > 0 && (
                <span className="ml-1 text-xs text-bad" title={t('m.flagged')}>
                  ({v.flagged_as_mule_case}× mule)
                </span>
              )}
            </td>
            <td className="px-3 py-1.5">
              {isNum(v?.rate) ? (
                <span className="inline-flex items-center gap-2">
                  <span className="w-12 text-right">{pct(v.rate)}</span>
                  <Bar value={v.rate} tone={bad ? 'warn' : 'navy'} width="w-12" />
                </span>
              ) : (
                <NA />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

function FailureList({ items }: { items: Record<string, unknown>[] | undefined }) {
  const { num } = useI18n();
  if (!items) return <NA />;
  if (!items.length) return <p className="text-sm text-muted">0</p>;
  return (
    <ul className="space-y-2.5">
      {items.map((f, i) => {
        const { case_id, client_ref, why, missed_because, signals, ...rest } = f as Record<string, unknown>;
        return (
          <li key={i} className="rounded-md border border-line p-3">
            <div className="flex flex-wrap items-center gap-2">
              {case_id != null ? <span className="mono font-medium text-navy">{String(case_id)}</span> : null}
              {client_ref != null ? <span className="mono text-muted">{String(client_ref)}</span> : null}
              {Array.isArray(signals) &&
                signals.map((s) => (
                  <Chip key={String(s)} mono tone="outline">
                    {String(s)}
                  </Chip>
                ))}
            </div>
            {(why != null || missed_because != null) && <p className="mt-1.5 text-sm">{String(why ?? missed_because)}</p>}
            {Object.keys(rest).length > 0 && (
              <p className="mt-1 flex flex-wrap gap-x-3 text-xs text-muted">
                {Object.entries(rest).map(([k, v]) => (
                  <span key={k}>
                    {k}: <span className="mono text-ink">{fmtScalar(v, num)}</span>
                  </span>
                ))}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
