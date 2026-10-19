import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getQueue } from '../api';
import { useI18n, type I18nKey } from '../i18n';
import { useAsync } from '../state';
import type { QueueFilters, QueueItem } from '../types';
import { Chip, ClusterBadge, ErrorBox, Loading, PageHeader, PriorityBar, RouteChip, RuleChip, StatusChip, SyntheticBadge, TriageChip } from '../components/ui';
import { rememberCase } from '../components/Layout';

const RULES = ['R-A', 'R-B', 'R-C', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'X'];
type SortKey = 'priority' | 'case_id' | 'bank_id' | 'client_ref' | 'triage' | 'cluster_id' | 'escalation_role' | 'decision_status';

export default function QueueScreen() {
  const { t, num } = useI18n();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const filters: QueueFilters = {
    rule: sp.get('rule') ?? undefined,
    min_priority: sp.get('min_priority') ? Number(sp.get('min_priority')) : undefined,
    max_priority: sp.get('max_priority') ? Number(sp.get('max_priority')) : undefined,
    triage: sp.get('triage') ?? undefined,
    cluster: sp.get('cluster') ?? undefined,
    bank: sp.get('bank') ?? undefined,
  };
  const key = sp.toString();
  const q = useAsync(() => getQueue(filters), [key]);
  const all = useAsync(() => getQueue({}), []);
  const [sort, setSort] = useState<{ k: SortKey; dir: 1 | -1 }>({ k: 'priority', dir: -1 });

  const setF = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v === '') n.delete(k);
    else n.set(k, v);
    setSp(n, { replace: true });
  };

  const clusters = useMemo(() => [...new Set((all.data?.items ?? []).map((i) => i.cluster_id).filter(Boolean) as string[])].sort(), [all.data]);
  const banks = useMemo(() => [...new Set((all.data?.items ?? []).map((i) => i.bank_id))].sort(), [all.data]);

  const rows = useMemo(() => {
    const items = [...(q.data?.items ?? [])];
    items.sort((a, b) => {
      const av = a[sort.k] ?? '';
      const bv = b[sort.k] ?? '';
      const c = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return c * sort.dir || b.priority - a.priority;
    });
    return items;
  }, [q.data, sort]);

  const open = (it: QueueItem) => {
    rememberCase(it.case_id);
    nav(`/case/${it.case_id}`);
  };

  const counts = q.data?.counts ?? all.data?.counts;

  const Th = ({ k, label, className = '' }: { k: SortKey; label: string; className?: string }) => {
    const active = sort.k === k;
    return (
      <th className={`th ${className}`} aria-sort={active ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'} scope="col">
        <button
          className={`inline-flex items-center gap-1 rounded hover:text-ink ${active ? 'text-ink' : ''}`}
          onClick={() => setSort((s) => ({ k, dir: s.k === k ? ((s.dir * -1) as 1 | -1) : k === 'priority' ? -1 : 1 }))}
        >
          {label}
          <span aria-hidden="true" className="text-[10px]">
            {active ? (sort.dir === 1 ? '▲' : '▼') : '↕'}
          </span>
        </button>
      </th>
    );
  };

  return (
    <div>
      <PageHeader title={t('q.title')}>
        <SyntheticBadge />
      </PageHeader>

      {/* funnel strip */}
      <div className="card mb-5 flex flex-wrap items-stretch divide-line overflow-hidden sm:divide-x" aria-label="triage funnel">
        {counts ? (
          <>
            <Funnel n={counts.alerts_before_triage} label={t('q.funnel_before')} num={num} />
            <Arrow />
            <Funnel n={counts.review} label={t('q.funnel_review')} num={num} tone="navy" sub={`${num(counts.cases)} ${t('q.funnel_cases')}`} />
            <Arrow />
            <Funnel n={counts.fp_auto_closed} label={t('q.funnel_fp')} num={num} tone="good" />
            <Funnel n={counts.victim_protection} label={t('q.funnel_victim')} num={num} tone="violet" />
          </>
        ) : (
          <div className="p-4">{all.error ? <ErrorBox error={all.error} /> : <Loading />}</div>
        )}
      </div>

      {/* filters */}
      <form className="card mb-4 flex flex-wrap items-end gap-3 p-3" aria-label={t('q.filters')} onSubmit={(e) => e.preventDefault()}>
        <Sel id="f-rule" label={t('q.rule')} value={filters.rule ?? ''} onChange={(v) => setF('rule', v)} options={RULES.map((r) => [r, r === 'X' ? 'X (cluster)' : r])} all={t('common.all')} />
        <div className="flex flex-col gap-1">
          <label className="label" htmlFor="f-min">
            {t('q.min_p')}
          </label>
          <input id="f-min" type="number" min={0} max={100} className="input w-20 tnum" value={filters.min_priority ?? ''} onChange={(e) => setF('min_priority', e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="label" htmlFor="f-max">
            {t('q.max_p')}
          </label>
          <input id="f-max" type="number" min={0} max={100} className="input w-20 tnum" value={filters.max_priority ?? ''} onChange={(e) => setF('max_priority', e.target.value)} />
        </div>
        <Sel id="f-tri" label={t('q.triage')} value={filters.triage ?? ''} onChange={(v) => setF('triage', v)} options={[['REVIEW', 'REVIEW'], ['FP', 'FP']]} all={t('common.all')} />
        <Sel id="f-cl" label={t('q.cluster')} value={filters.cluster ?? ''} onChange={(v) => setF('cluster', v)} options={clusters.map((c) => [c, c])} all={t('common.all')} />
        <Sel id="f-bank" label={t('q.bank')} value={filters.bank ?? ''} onChange={(v) => setF('bank', v)} options={banks.map((b) => [b, b])} all={t('common.all')} />
        <button type="button" className="btn-secondary" onClick={() => setSp(new URLSearchParams(), { replace: true })} disabled={!key}>
          {t('common.reset')}
        </button>
        <p className="ml-auto self-center text-xs text-muted tnum">
          {rows.length} {t('q.shown')}
        </p>
      </form>

      <div className="card overflow-hidden">
        {q.loading && !q.data ? (
          <Loading />
        ) : q.error ? (
          <div className="p-4">
            <ErrorBox error={q.error} onRetry={q.reload} />
          </div>
        ) : rows.length === 0 ? (
          <p className="p-6 text-sm text-muted">{t('common.empty')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] border-collapse">
              <caption className="sr-only">
                {t('q.title')}. {t('q.sort_hint')}
              </caption>
              <thead className="border-b border-line bg-paper/60">
                <tr>
                  <Th k="priority" label={t('q.col_priority')} />
                  <Th k="case_id" label={t('q.col_case')} />
                  <Th k="bank_id" label={t('q.col_bank')} />
                  <Th k="client_ref" label={t('q.col_client')} />
                  <Th k="triage" label={t('q.col_triage')} />
                  <th className="th" scope="col">
                    {t('q.col_rules')}
                  </th>
                  <Th k="cluster_id" label={t('q.col_cluster')} />
                  <Th k="escalation_role" label={t('q.col_escalation')} />
                  <Th k="decision_status" label={t('q.col_decision')} />
                </tr>
              </thead>
              <tbody>
                {rows.map((it) => (
                  <tr
                    key={it.case_id}
                    tabIndex={0}
                    onClick={() => open(it)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        open(it);
                      }
                    }}
                    aria-label={`${it.case_id}, priority ${it.priority}, ${it.triage}`}
                    className={`cursor-pointer border-b border-line/70 last:border-0 hover:bg-paper focus-visible:bg-tealsoft/40 ${it.route === 'victim_protection' ? 'bg-violetsoft/40' : ''}`}
                  >
                    <td className="td">
                      <PriorityBar p={it.priority} />
                    </td>
                    <td className="td mono font-medium text-navy">{it.case_id}</td>
                    <td className="td mono">{it.bank_id}</td>
                    <td className="td mono text-muted">{it.client_ref}</td>
                    <td className="td">
                      <span className="flex flex-wrap items-center gap-1">
                        <TriageChip triage={it.triage} />
                        <RouteChip route={it.route} />
                      </span>
                    </td>
                    <td className="td">
                      <span className="flex flex-wrap gap-1">
                        {it.rules.map((r) => (
                          <RuleChip key={r} rule={r} />
                        ))}
                      </span>
                    </td>
                    <td className="td">
                      <ClusterBadge id={it.cluster_id} />
                    </td>
                    <td className="td text-sm">{t(`role.${it.escalation_role}` as I18nKey)}</td>
                    <td className="td">
                      <StatusChip status={it.decision_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="mt-2 text-xs text-muted">
        {t('q.sort_hint')} {t('q.fp_note')}{' '}
        <Chip tone="violet" className="ml-1">
          {t('route.victim_protection')}
        </Chip>{' '}
        = {t('c.victim_note').split(':')[0]}.
      </p>
    </div>
  );
}

function Funnel({ n, label, num, tone, sub }: { n: number; label: string; num: (n: number) => string; tone?: 'navy' | 'good' | 'violet'; sub?: string }) {
  const c = tone === 'navy' ? 'text-navy' : tone === 'good' ? 'text-good' : tone === 'violet' ? 'text-violet' : 'text-ink';
  return (
    <div className="min-w-[150px] flex-1 px-5 py-3">
      <div className={`tnum text-2xl font-semibold ${c}`}>{num(n)}</div>
      <div className="text-xs text-muted">{label}</div>
      {sub && <div className="tnum text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

function Arrow() {
  return (
    <div className="hidden items-center px-1 text-muted sm:flex" aria-hidden="true">
      →
    </div>
  );
}

function Sel({ id, label, value, onChange, options, all }: { id: string; label: string; value: string; onChange: (v: string) => void; options: [string, string][]; all: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <select id={id} className="input min-w-[7rem]" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{all}</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </div>
  );
}
