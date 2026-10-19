import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Bar as RBar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getMetrics, resolveApiUrl } from '../api';
import { Bar, Card, Chip, DatasetLine, ErrorBox, Loading, NA, PageHeader, fmtScalar } from '../components/ui';
import { useI18n, type I18nKey } from '../i18n';
import { useAsync } from '../state';
import WeakEvidence from '../components/WeakEvidence';
import type { Confusion, MetricsResponse, ModeResult } from '../types';

const MODES = ['isolated', 'staj_psi', 'naive_raw_sharing'] as const;
type Group = 'scheme' | 'persona' | 'victim' | 'other';
type BreakdownRow = [string, MetricsResponse['breakdown'][string]];

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

function Block({ title, dataset, seed, children, className = '', sub }: { title: string; dataset?: string; seed?: number; children: ReactNode; className?: string; sub?: ReactNode }) {
  return (
    <Card title={title} sub={sub} right={<DatasetLine dataset={dataset} seed={seed} />} className={className}>
      {children}
    </Card>
  );
}

function isNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

function MetricCell({ v, muted = false }: { v: unknown; muted?: boolean }) {
  const { num } = useI18n();
  if (!isNum(v)) return <NA />;
  return (
    <span className={`inline-flex items-center gap-2 ${muted ? 'text-muted' : ''}`}>
      <span className="tnum w-10 text-right">{num(v, 3)}</span>
      <Bar value={v} tone="navy" width="w-12" />
    </span>
  );
}

function MetricsView({ d }: { d: MetricsResponse }) {
  const { t, num } = useI18n();
  const ds = { dataset: d.dataset, seed: d.seed };
  const groups: Record<Group, BreakdownRow[]> = { scheme: [], persona: [], victim: [], other: [] };
  for (const [k, v] of Object.entries(d.breakdown ?? {})) {
    const i = k.indexOf(':');
    const p = i > 0 ? k.slice(0, i) : '';
    const name = i > 0 ? k.slice(i + 1) : k;
    (p === 'scheme' || p === 'persona' || p === 'victim' ? groups[p] : groups.other).push([name, v]);
  }
  for (const g of Object.values(groups)) g.sort((a, b) => a[0].localeCompare(b[0]));
  const ablRef: Confusion | undefined = d.ablations?.full ?? d.modes?.staj_psi?.overall;
  const iso = d.modes?.isolated;

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

      <Block title={t('m.modes')} {...ds}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse">
            <thead className="border-b border-line">
              <tr>
                <th className="th">{t('r.mode')}</th>
                <th className="th">{t('m.precision')}</th>
                <th className="th">{t('m.recall')}</th>
                <th className="th">{t('m.f1')}</th>
                <th className="th" title="average precision">
                  {t('m.ap')}
                </th>
                <th className="th" title="precision at K">
                  {t('m.patk')}
                </th>
                <th className="th text-right">TP / FP / FN</th>
                <th className="th text-right">mules / accounts</th>
              </tr>
            </thead>
            <tbody className="tnum">
              {MODES.map((k) => (
                <ModeRows key={k} k={k} m={d.modes?.[k]} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">
          <span className="text-muted">↳ {t('m.any_priority')}</span>: overall_any_priority · {t('m.ap')} = average precision · {t('m.patk')} = precision@K (K = n_mules)
        </p>
      </Block>

      {iso?.per_bank && Object.keys(iso.per_bank).length > 0 && (
        <Block title={t('m.per_bank')} {...ds}>
          <div className="mb-3 flex flex-wrap gap-6 text-sm">
            {isNum(iso.best_single_bank_f1) && (
              <span>
                {t('m.best_bank')}: <span className="tnum font-semibold">{num(iso.best_single_bank_f1, 3)}</span>
              </span>
            )}
            {isNum(iso.mean_bank_f1) && (
              <span>
                {t('m.mean_bank')}: <span className="tnum font-semibold">{num(iso.mean_bank_f1, 3)}</span>
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse">
              <thead className="border-b border-line">
                <tr>
                  <th className="th">{t('q.bank')}</th>
                  <th className="th">{t('m.precision')}</th>
                  <th className="th">{t('m.recall')}</th>
                  <th className="th">{t('m.f1')}</th>
                  <th className="th text-right">TP / FP / FN</th>
                </tr>
              </thead>
              <tbody className="tnum">
                {Object.entries(iso.per_bank).map(([b, o]) => (
                  <tr key={b} className="border-b border-line/70 last:border-0">
                    <th scope="row" className="td mono text-left">
                      {b}
                    </th>
                    <td className="td">
                      <MetricCell v={o?.precision} />
                    </td>
                    <td className="td">
                      <MetricCell v={o?.recall} />
                    </td>
                    <td className="td">
                      <MetricCell v={o?.f1} />
                    </td>
                    <td className="td text-right text-muted">
                      {fmtScalar(o?.tp, num)} / {fmtScalar(o?.fp, num)} / {fmtScalar(o?.fn, num)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Block>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Block title={t('m.schemes')} {...ds}>
          <BreakdownTable rows={groups.scheme} metric="flagged" />
        </Block>
        <Block title={t('m.personas')} {...ds}>
          <BreakdownTable rows={groups.persona} metric="flagged" bad />
        </Block>
        <Block title={t('m.victims')} {...ds}>
          <BreakdownTable rows={groups.victim} metric="victim" />
        </Block>
        {groups.other.length > 0 && (
          <Block title={t('m.other')} {...ds}>
            <BreakdownTable rows={groups.other} metric="flagged" bad />
          </Block>
        )}
      </div>

      <Block title={t('m.ablations')} {...ds} sub={!d.ablations?.full && ablRef ? t('m.delta_ref') : undefined}>
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
                {!d.ablations.full && ablRef && <AblationRow name={`${t('mode.staj_psi')} (${t('m.ablation_full')})`} a={ablRef} ref_={ablRef} isRef />}
                {Object.entries(d.ablations).map(([k, a]) => (
                  <AblationRow key={k} name={k === 'full' ? t('m.ablation_full') : k} a={a} ref_={ablRef} isRef={k === 'full'} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <NA />
        )}
      </Block>

      <div className="grid gap-5 xl:grid-cols-2">
        <Block title={t('m.worst_fp')} {...ds}>
          <FailureList items={d.failures?.worst_false_positives} />
        </Block>
        <Block title={t('m.fn')} {...ds}>
          <FailureList items={d.failures?.false_negatives} />
        </Block>
      </div>

      <CnbBlock d={d} />

      {d.weak_evidence_experiment && <WeakEvidence x={d.weak_evidence_experiment} {...ds} />}

      <Extra title={t('m.extra_headline')} value={d.headline_held_out_mean} {...ds} />
      <Extra title={t('m.extra_threshold')} value={d.threshold_curve_held_out_mean} {...ds} />
      <Extra title={t('m.extra_ring')} value={d.ring_size_sweep} {...ds} />

      <p className="text-xs text-muted">
        {t('h.limitations')}:{' '}
        <Link to="/honesty" className="text-teal underline">
          {t('nav.honesty')}
        </Link>
      </p>
    </>
  );
}

function ModeRows({ k, m }: { k: (typeof MODES)[number]; m?: ModeResult }) {
  const { t, num } = useI18n();
  const o = m?.overall;
  const any = m?.overall_any_priority;
  const rk = m?.rank;
  return (
    <>
      <tr className={`${any ? '' : 'border-b border-line/70'} ${k === 'staj_psi' ? 'bg-tealsoft/40' : ''}`}>
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
            <td className="td">
              <MetricCell v={rk?.average_precision} />
            </td>
            <td className="td">
              <MetricCell v={rk?.precision_at_k} />
              {rk?.k !== undefined && <span className="ml-1 text-[11px] text-muted">K={rk.k}</span>}
            </td>
            <td className="td text-right">
              {fmtScalar(o.tp, num)} / {fmtScalar(o.fp, num)} / {fmtScalar(o.fn, num)}
            </td>
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
      {any && (
        <tr className={`border-b border-line/70 text-xs ${k === 'staj_psi' ? 'bg-tealsoft/40' : ''}`}>
          <th scope="row" className="px-3 pb-2 pl-6 text-left font-normal text-muted">
            ↳ {t('m.any_priority')}
          </th>
          <td className="px-3 pb-2">
            <MetricCell v={any.precision} muted />
          </td>
          <td className="px-3 pb-2">
            <MetricCell v={any.recall} muted />
          </td>
          <td className="px-3 pb-2">
            <MetricCell v={any.f1} muted />
          </td>
          <td className="px-3 pb-2" />
          <td className="px-3 pb-2" />
          <td className="px-3 pb-2 text-right text-muted">
            {fmtScalar(any.tp, num)} / {fmtScalar(any.fp, num)} / {fmtScalar(any.fn, num)}
          </td>
          <td className="px-3 pb-2" />
        </tr>
      )}
    </>
  );
}

function AblationRow({ name, a, ref_, isRef }: { name: string; a: Confusion; ref_?: Confusion; isRef?: boolean }) {
  const { num } = useI18n();
  const delta = !isRef && ref_ && isNum(a?.f1) && isNum(ref_.f1) ? a.f1 - ref_.f1 : null;
  return (
    <tr className={`border-b border-line/70 last:border-0 ${isRef ? 'bg-tealsoft/40' : ''}`}>
      <th scope="row" className="td mono text-left font-medium">
        {name}
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
      <td className={`td text-right ${delta !== null && delta < 0 ? 'text-bad' : ''}`}>{delta === null ? '–' : `${delta > 0 ? '+' : ''}${num(delta, 3)}`}</td>
      <td className="td text-right text-muted">
        {fmtScalar(a?.tp, num)} / {fmtScalar(a?.fp, num)} / {fmtScalar(a?.fn, num)}
      </td>
    </tr>
  );
}

function CountTable({ title, data }: { title: string; data?: Record<string, number> }) {
  const { num } = useI18n();
  if (!data || !Object.keys(data).length) return null;
  return (
    <div>
      <h3 className="label mb-1.5">{title}</h3>
      <table className="w-full text-sm tnum">
        <tbody>
          {Object.entries(data).map(([k, v]) => (
            <tr key={k} className="border-b border-line/70 last:border-0">
              <th scope="row" className="py-1 pr-3 text-left font-normal mono text-[12px]">
                {k}
              </th>
              <td className="py-1 text-right font-semibold">{isNum(v) ? num(v) : String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CnbBlock({ d }: { d: MetricsResponse }) {
  const { t, num, pct } = useI18n();
  const c = d.cnb;
  // The CNB section has its own dataset (organiser data), distinct from the red-team world.
  const ds = { dataset: c?.dataset ?? d.dataset, seed: c?.dataset ? undefined : d.seed };
  const sheet = c?.sample_sheet_url;
  const sheetIsUrl = !!sheet && (/^https?:\/\//.test(sheet) || sheet.startsWith('/'));
  return (
    <Block title={t('m.cnb')} {...ds}>
      {c ? (
        <div className="space-y-6">
          <p className="text-xs text-muted tnum">
            {isNum(c.n_clients) ? num(c.n_clients) : '–'} {t('m.clients')} · {isNum(c.n_tx) ? num(c.n_tx) : '–'} {t('m.tx')}
            {isNum(c.cases) && ` · ${num(c.cases)} ${t('q.funnel_cases')}`}
            {isNum(c.actionable_review) && ` · ${t('m.actionable')}: ${num(c.actionable_review)}`}
            {isNum(c.operating_point_min_priority) && ` (min_priority ${c.operating_point_min_priority})`}
          </p>
          <div className="grid gap-6 lg:grid-cols-3">
            <div>
              {c.rule_a_alerts_per_unit && Object.keys(c.rule_a_alerts_per_unit).length ? <CountTable title={t('m.rule_a_units')} data={c.rule_a_alerts_per_unit} /> : <NA />}
            </div>
            <div className="space-y-4">
              <div className="flex gap-8">
                <Big n={isNum(c.rule_b_alerts) ? num(c.rule_b_alerts) : null} l={t('m.rule_b')} />
                <Big n={isNum(c.rule_c_alerts) ? num(c.rule_c_alerts) : null} l={t('m.rule_c')} />
              </div>
              <div>
                <h3 className="label mb-1.5">{t('m.rule_c_triage')}</h3>
                {c.rule_c_triage ? <SplitBar fp={c.rule_c_triage.FP} review={c.rule_c_triage.REVIEW} /> : <NA />}
              </div>
              {c.triage && (
                <div>
                  <h3 className="label mb-1.5">{t('m.cnb_triage')}</h3>
                  {isNum(c.triage.FP) && isNum(c.triage.REVIEW) ? <SplitBar fp={c.triage.FP} review={c.triage.REVIEW} /> : <CountTable title="" data={c.triage} />}
                </div>
              )}
              <CountTable title={t('m.alerts_by_type')} data={c.alerts_by_type} />
            </div>
            <div className="space-y-4">
              <div>
                <h3 className="label mb-1">{t('m.mom')}</h3>
                {c.mom_persona ? (
                  <>
                    <p className="tnum">
                      <span className="text-2xl font-semibold">{pct(c.mom_persona.fp_rate, 2)}</span> <span className="text-xs text-muted">(n = {num(c.mom_persona.n)})</span>
                    </p>
                    {c.mom_persona.definition && <p className="mt-1 text-xs text-muted">{c.mom_persona.definition}</p>}
                  </>
                ) : (
                  <NA />
                )}
              </div>
              <CountTable title={t('m.signals_by_detector')} data={c.signals_by_detector} />
              <div>
                <h3 className="label mb-1">{t('m.sheet')}</h3>
                {!sheet ? (
                  <NA />
                ) : sheetIsUrl ? (
                  <a className="text-sm text-teal underline underline-offset-2" href={resolveApiUrl(sheet)}>
                    {sheet}
                  </a>
                ) : (
                  <p className="text-xs text-muted">
                    {t('m.sheet_path')} <span className="mono text-ink">{sheet}</span>
                  </p>
                )}
              </div>
            </div>
          </div>
          <div>
            <h3 className="label mb-2">{t('m.hist')}</h3>
            {c.priority_hist?.length ? <Hist rows={c.priority_hist} /> : <NA />}
          </div>
        </div>
      ) : (
        <NA />
      )}
    </Block>
  );
}

/** Generic renderer for optional metric sections whose exact shape may evolve. Skips silently when absent. */
function Extra({ title, value, dataset, seed }: { title: string; value: unknown; dataset?: string; seed?: number }) {
  if (value === undefined || value === null) return null;
  return (
    <Block title={title} dataset={dataset} seed={seed}>
      <GenericValue v={value} />
    </Block>
  );
}

function GenericValue({ v }: { v: unknown }) {
  const { num } = useI18n();
  if (Array.isArray(v)) {
    if (v.length && v.every((r) => r && typeof r === 'object' && !Array.isArray(r))) {
      const rows = v as Record<string, unknown>[];
      const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
      return <ObjTable cols={cols} rows={rows.map((r, i) => [String(i), r])} hideKey />;
    }
    return <p className="mono text-sm">{v.map((x) => fmtScalar(x, num)).join(', ') || '–'}</p>;
  }
  if (v && typeof v === 'object') {
    const entries = Object.entries(v as Record<string, unknown>);
    if (entries.length && entries.every(([, x]) => x && typeof x === 'object' && !Array.isArray(x))) {
      const cols = [...new Set(entries.flatMap(([, x]) => Object.keys(x as object)))];
      return <ObjTable cols={cols} rows={entries as [string, Record<string, unknown>][]} />;
    }
    return (
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        {entries.map(([k, x]) => (
          <div key={k} className="contents">
            <dt className="mono text-muted">{k}</dt>
            <dd className="tnum">{x && typeof x === 'object' ? <GenericValue v={x} /> : fmtScalar(x, num)}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return <p className="tnum text-sm">{fmtScalar(v, num)}</p>;
}

function ObjTable({ cols, rows, hideKey = false }: { cols: string[]; rows: [string, Record<string, unknown>][]; hideKey?: boolean }) {
  const { num } = useI18n();
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead className="border-b border-line">
          <tr>
            {!hideKey && <th className="th">&nbsp;</th>}
            {cols.map((c) => (
              <th key={c} className="th mono text-right">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="tnum">
          {rows.map(([k, r]) => (
            <tr key={k} className="border-b border-line/70 last:border-0">
              {!hideKey && (
                <th scope="row" className="td mono text-left font-normal">
                  {k}
                </th>
              )}
              {cols.map((c) => (
                <td key={c} className="td text-right">
                  {r[c] !== null && typeof r[c] === 'object' ? JSON.stringify(r[c]) : fmtScalar(r[c], num)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
      <div className="mt-1.5 flex justify-between gap-2 text-xs tnum">
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-good" aria-hidden="true" />
          FP {num(fp)} ({num(f, f < 1 || f > 99 ? 1 : 0)} %)
        </span>
        <span>
          REVIEW {num(review)} ({num(100 - f, f < 1 || f > 99 ? 1 : 0)} %)
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
          <YAxis tick={{ fontSize: 10, fill: 'rgb(var(--muted))' }} width={40} allowDecimals={false} stroke="rgb(var(--line))" />
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

function BreakdownTable({ rows, metric, bad = false }: { rows: BreakdownRow[]; metric: 'flagged' | 'victim'; bad?: boolean }) {
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
                    <span className="w-14 text-right">{pct(v.rate, v.rate > 0 && v.rate < 0.01 ? 2 : 1)}</span>
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
  const { num, lang } = useI18n();
  if (!items) return <NA />;
  if (!items.length) return <p className="text-sm text-muted">{lang === 'cs' ? 'Žádné (0).' : 'None (0).'}</p>;
  return (
    <ul className="space-y-2.5">
      {items.map((f, i) => {
        const { case_id, client_id, client_ref, why, missed_because, signals, exculpatory, reasons, ...rest } = f as Record<string, unknown>;
        return (
          <li key={i} className="rounded-md border border-line p-3">
            <div className="flex flex-wrap items-center gap-2">
              {case_id != null && <span className="mono font-medium text-navy">{String(case_id)}</span>}
              {client_id != null && <span className="mono font-medium text-navy">{String(client_id)}</span>}
              {client_ref != null && <span className="mono text-muted">{String(client_ref)}</span>}
              {Array.isArray(signals) &&
                signals.map((s) => (
                  <Chip key={String(s)} mono tone="warn">
                    {String(s)}
                  </Chip>
                ))}
              {Array.isArray(exculpatory) &&
                exculpatory.map((s) => (
                  <Chip key={String(s)} mono tone="teal">
                    {String(s)}
                  </Chip>
                ))}
            </div>
            {(why != null || missed_because != null) && <p className="mt-1.5 text-sm">{String(why ?? missed_because)}</p>}
            {Array.isArray(reasons) && reasons.length > 0 && (
              <ul className="mt-1.5 list-disc pl-5 text-xs leading-relaxed">
                {reasons.map((r, j) => (
                  <li key={j}>{String(r)}</li>
                ))}
              </ul>
            )}
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
