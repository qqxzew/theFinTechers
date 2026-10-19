import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar as RBar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ApiError, explainCase, getCase, postDecision } from '../api';
import Graph from '../components/Graph';
import { rememberCase } from '../components/Layout';
import { Bar, Card, Chip, ClusterBadge, ErrorBox, Loading, PageHeader, PriorityBar, RouteChip, RuleChip, StatusChip, TriageChip, ViolationList, fmtScalar } from '../components/ui';
import { useI18n, type I18nKey, type Lang } from '../i18n';
import { STAFF, useApp, useAsync } from '../state';
import type { CaseDetail, Explanation, Sentence, Signal } from '../types';

export default function CaseScreen() {
  const { id } = useParams();
  const { t } = useI18n();
  useEffect(() => {
    if (id) rememberCase(id);
  }, [id]);
  const c = useAsync(() => (id ? getCase(id) : Promise.resolve(null)), [id]);

  if (!id)
    return (
      <div>
        <PageHeader title={t('c.title')} />
        <p className="text-sm text-muted">
          {t('c.select_case')} <Link className="text-teal underline" to="/">{t('nav.queue')}</Link>
        </p>
      </div>
    );
  if (c.loading && !c.data) return <Loading />;
  if (c.error)
    return (
      <div>
        <PageHeader title={`${t('c.title')} ${id}`} />
        <ErrorBox error={c.error} message={c.error.includes('404') || c.error.startsWith('Not found') ? t('c.not_found') : undefined} onRetry={c.reload} />
      </div>
    );
  if (!c.data) return null;
  return <CaseView data={c.data} reload={c.reload} />;
}

function CaseView({ data, reload }: { data: CaseDetail; reload: () => void }) {
  const { t, num } = useI18n();
  const [hl, setHl] = useState<string | null>(null);
  const [explain, setExplain] = useState<{ exp: Explanation | null; violations: Record<string, unknown>[]; model?: string; cached?: boolean }>({
    exp: data.explanation,
    violations: data.explanation_violations ?? [],
  });
  useEffect(() => setExplain({ exp: data.explanation, violations: data.explanation_violations ?? [] }), [data]);

  const signalIds = useMemo(() => new Set([...data.signals, ...data.exculpatory].map((s) => s.signal_id)), [data]);

  const focusRef = useCallback(
    (ref: string) => {
      setHl(ref);
      const el = document.getElementById(signalIds.has(ref) ? `sig-${ref}` : ref.startsWith('cluster:') ? 'cluster-card' : ref.startsWith('feature:') ? 'features-card' : '');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (el.tagName === 'DETAILS') (el as HTMLDetailsElement).open = true;
      }
      window.setTimeout(() => setHl((h) => (h === ref ? null : h)), 3500);
    },
    [signalIds],
  );

  const victim = data.route === 'victim_protection';

  return (
    <div className="space-y-5">
      <PageHeader title={`${t('c.title')} · ${data.case_id}`}>
        <Link to={`/opo/${data.case_id}`} className="btn-secondary">
          {t('c.open_opo')}
        </Link>
      </PageHeader>

      <div className="card flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 text-sm">
        <Meta k={t('q.col_client')}>
          <span className="mono">{data.client_ref}</span>
        </Meta>
        <Meta k={t('q.col_bank')}>
          <span className="mono">{data.bank_id}</span>
        </Meta>
        <Meta k={t('q.col_priority')}>
          <PriorityBar p={data.priority} />
        </Meta>
        <Meta k={t('c.triage_proposal')}>
          <span className="flex gap-1">
            <TriageChip triage={data.triage} />
            <RouteChip route={data.route} />
          </span>
        </Meta>
        <Meta k={t('q.col_cluster')}>
          <ClusterBadge id={data.cluster?.cluster_id ?? null} />
        </Meta>
        <Meta k={t('q.col_escalation')}>{t(`role.${data.escalation.role}` as I18nKey)}</Meta>
        <Meta k={t('q.col_decision')}>
          <StatusChip status={data.decision ? (data.decision.action === 'confirm' ? 'confirmed' : 'overridden') : 'open'} />
        </Meta>
      </div>

      {victim && (
        <div role="note" className="rounded-md border border-violet/30 bg-violetsoft px-4 py-3 text-sm text-violet">
          {t('c.victim_note')}
        </div>
      )}

      {/* Mom, or mule? */}
      <section aria-labelledby="mom-h">
        <div className="mb-2 flex flex-wrap items-baseline gap-2">
          <h2 id="mom-h" className="text-base font-semibold">
            {t('c.mom_or_horse')}
          </h2>
          <span className="text-xs text-muted">{t('c.mom_or_horse_sub')}</span>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-warn">
              <span className="h-2 w-2 rounded-full bg-warn" aria-hidden="true" />
              {t('c.suspicious')} <span className="tnum font-normal text-muted">({data.signals.length})</span>
            </h3>
            {data.signals.length === 0 && <p className="text-sm text-muted">{t('c.no_signals')}</p>}
            {data.signals.map((s) => (
              <SignalCard key={s.signal_id} s={s} kind="sus" highlighted={hl === s.signal_id} victim={victim && s.detector_id === 'VICTIM'} />
            ))}
          </div>
          <div className="space-y-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-teal">
              <span className="h-2 w-2 rounded-full bg-teal" aria-hidden="true" />
              {t('c.exculpatory')} <span className="tnum font-normal text-muted">({data.exculpatory.length})</span>
            </h3>
            {data.exculpatory.length === 0 && <p className="rounded-md border border-dashed border-line p-3 text-sm text-muted">{t('c.no_exculpatory')}</p>}
            {data.exculpatory.map((s) => (
              <SignalCard key={s.signal_id} s={s} kind="exc" highlighted={hl === s.signal_id} />
            ))}
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-5">
        <Card title={t('c.timeline')} sub={t('c.timeline_sub')} className="xl:col-span-3">
          <Timeline data={data} />
        </Card>
        <Card title={t('c.graph')} sub={t('c.graph_sub')} className="xl:col-span-2">
          <Graph graph={data.local_graph} ariaLabel={`${t('c.graph')} ${data.client_ref}`} showAmounts height={300} />
          <GraphLegend />
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-5">
        <div className="space-y-5 xl:col-span-3">
          <ExplanationCard caseId={data.case_id} state={explain} setState={setExplain} onRef={focusRef} signalIds={signalIds} />
        </div>
        <div className="space-y-5 xl:col-span-2">
          <div id="cluster-card" className={`rounded-lg transition-shadow ${hl?.startsWith('cluster:') ? 'ring-2 ring-warn' : ''}`}>
            <Card title={t('c.cluster')}>
              {data.cluster ? (
                <div className="flex flex-wrap items-center gap-4">
                  <ClusterBadge id={data.cluster.cluster_id} />
                  <Stat n={num(data.cluster.n_other_banks)} l={t('c.other_banks')} />
                  <Stat n={num(data.cluster.n_other_candidates)} l={t('c.other_candidates')} />
                  <Stat n={data.cluster.lag_ret_concentration === null ? '–' : num(data.cluster.lag_ret_concentration, 2)} l={t('c.lag_ret')} />
                </div>
              ) : (
                <p className="text-sm text-muted">{t('c.no_cluster')}</p>
              )}
            </Card>
          </div>
          <TriageCard data={data} />
        </div>
      </div>

      <DecisionPanel data={data} onDone={reload} />

      <div className="grid gap-5 md:grid-cols-2">
        <details id="features-card" className={`card group p-4 ${hl?.startsWith('feature:') ? 'ring-2 ring-teal' : ''}`}>
          <summary className="card-h cursor-pointer">{t('c.features')}</summary>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {Object.entries(data.features).map(([k, v]) => (
              <div key={k} className={`contents ${hl === `feature:${k}` ? 'font-semibold text-teal' : ''}`}>
                <dt className="mono text-muted">{k}</dt>
                <dd className="mono tnum">{fmtScalar(v, num)}</dd>
              </div>
            ))}
          </dl>
        </details>
        <details className="card p-4">
          <summary className="card-h cursor-pointer">{t('c.rule_defs')}</summary>
          <dl className="mt-3 space-y-1.5 text-sm">
            {Object.entries(data.rule_definitions).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt>
                  <RuleChip rule={k} />
                </dt>
                <dd className="text-muted">{v}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
    </div>
  );
}

function Meta({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="label">{k}</span>
      <span>{children}</span>
    </div>
  );
}

function Stat({ n, l }: { n: string; l: string }) {
  return (
    <div>
      <div className="tnum text-lg font-semibold">{n}</div>
      <div className="text-xs text-muted">{l}</div>
    </div>
  );
}

function renderTemplate(tpl: string, ev: Signal['evidence'], num: (n: number, d?: number) => string, pct: (n: number, d?: number) => string) {
  return tpl.replace(/\{(\w+)\}/g, (m, k: string) => {
    if (!(k in ev)) return m;
    const v = ev[k];
    if (typeof v === 'number' && /share|rate/.test(k) && v >= 0 && v <= 1) return pct(v, 0);
    return fmtScalar(v, num);
  });
}

function SignalCard({ s, kind, highlighted, victim }: { s: Signal; kind: 'sus' | 'exc'; highlighted: boolean; victim?: boolean }) {
  const { t, num, pct } = useI18n();
  const accent = victim ? 'border-l-violet' : kind === 'sus' ? 'border-l-warn' : 'border-l-teal';
  return (
    <article
      id={`sig-${s.signal_id}`}
      tabIndex={-1}
      className={`card border-l-4 ${accent} p-3 transition-shadow ${highlighted ? 'ring-2 ring-teal ring-offset-2 ring-offset-paper' : ''}`}
      aria-label={`${s.signal_id} ${t('common.score')} ${s.score}`}
    >
      <header className="flex flex-wrap items-center gap-2">
        <Chip tone={victim ? 'violet' : kind === 'sus' ? 'warn' : 'teal'} mono>
          {s.detector_id}
        </Chip>
        <span className="mono text-muted">{s.signal_id}</span>
        <span className="ml-auto inline-flex items-center gap-2 text-xs text-muted">
          {t('common.score')} <span className="tnum font-semibold text-ink">{num(s.score, 2)}</span>
          <Bar value={s.score} tone={kind === 'sus' ? 'warn' : 'teal'} width="w-16" label={`score ${s.score}`} />
        </span>
      </header>
      <p className="mt-2 text-sm leading-relaxed">{renderTemplate(s.template, s.evidence, num, pct)}</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded bg-paper/70 px-2 py-1.5 text-xs">
        {Object.entries(s.evidence).map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="mono text-muted">{k}</dt>
            <dd className="mono tnum break-all">{fmtScalar(v, num)}</dd>
          </div>
        ))}
      </dl>
      {s.notes.length > 0 && (
        <ul className="mt-2 list-disc pl-4 text-xs text-muted">
          {s.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[11px] text-muted">
        {t('c.source')}: <span className="mono">{s.source}</span>
      </p>
    </article>
  );
}

function Timeline({ data }: { data: CaseDetail }) {
  const { t, num, lang } = useI18n();
  const rows = data.timeline.slice(0, 60).map((e, i) => ({
    i,
    label: new Date(e.ts).toLocaleDateString(lang === 'cs' ? 'cs-CZ' : 'en-GB', { day: 'numeric', month: 'numeric' }),
    ts: e.ts,
    v: e.direction === 'in' ? e.amount_czk : -e.amount_czk,
    dir: e.direction,
    cp: e.counterparty,
  }));
  if (!rows.length) return <p className="text-sm text-muted">{t('common.empty')}</p>;
  const color = (d: string) => (d === 'in' ? 'rgb(var(--c-in))' : d === 'remit_out' ? 'rgb(var(--c-remit))' : 'rgb(var(--c-out))');
  return (
    <div>
      <div className="h-[280px] w-full" role="img" aria-label={`${t('c.timeline')}: ${rows.length}`}>
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke="rgb(var(--line))" />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'rgb(var(--muted))' }} interval="preserveStartEnd" minTickGap={24} stroke="rgb(var(--line))" />
            <YAxis tick={{ fontSize: 10, fill: 'rgb(var(--muted))' }} tickFormatter={(v: number) => `${num(v / 1000)}k`} width={48} stroke="rgb(var(--line))" />
            <ReferenceLine y={0} stroke="rgb(var(--muted))" />
            <Tooltip
              cursor={{ fill: 'rgb(var(--line) / 0.4)' }}
              contentStyle={{ background: 'rgb(var(--surface))', border: '1px solid rgb(var(--line))', borderRadius: 6, fontSize: 12 }}
              labelFormatter={(_: unknown, p: readonly { payload?: { ts: string } }[]) => (p?.[0]?.payload ? new Date(p[0].payload.ts).toLocaleString(lang === 'cs' ? 'cs-CZ' : 'en-GB') : '')}
              formatter={(v: unknown, _n: unknown, p: { payload?: { cp: string; dir: string } }) => [`${num(Math.abs(Number(v)))} CZK · ${p.payload?.cp ?? ""}`, t(`c.${p.payload?.dir ?? "in"}` as I18nKey)]}
            />
            <RBar dataKey="v" isAnimationActive={false}>
              {rows.map((r) => (
                <Cell key={r.i} fill={color(r.dir)} />
              ))}
            </RBar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
        <Legend c="bg-[rgb(var(--c-in))]" l={t('c.in')} />
        <Legend c="bg-[rgb(var(--c-out))]" l={t('c.out')} />
        <Legend c="bg-[rgb(var(--c-remit))]" l={t('c.remit_out')} />
        <span className="tnum">n = {rows.length}</span>
      </div>
    </div>
  );
}

function Legend({ c, l, shape = 'rounded-sm' }: { c: string; l: string; shape?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2.5 w-2.5 ${shape} ${c}`} aria-hidden="true" />
      {l}
    </span>
  );
}

function GraphLegend() {
  const { lang } = useI18n();
  return (
    <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
      <Legend c="bg-navy" l={lang === 'cs' ? 'klient' : 'client'} shape="rounded-full" />
      <Legend c="border-2 border-warn bg-surface" l={lang === 'cs' ? 'vzácná protistrana' : 'rare counterparty'} shape="rounded-full" />
      <Legend c="bg-teal" l={lang === 'cs' ? 'běžná protistrana' : 'popular counterparty'} />
    </div>
  );
}

function RefChips({ refs, onRef, signalIds }: { refs: string[]; onRef: (r: string) => void; signalIds: Set<string> }) {
  if (!refs.length) return <Chip tone="bad">no refs</Chip>;
  return (
    <>
      {refs.map((r) => {
        const clickable = signalIds.has(r) || r.startsWith('cluster:') || r.startsWith('feature:');
        return clickable ? (
          <button key={r} type="button" onClick={() => onRef(r)} className="rounded" aria-label={`highlight ${r}`}>
            <Chip tone="navy" mono className="hover:bg-navy/20">
              {r}
            </Chip>
          </button>
        ) : (
          <Chip key={r} tone="neutral" mono>
            {r}
          </Chip>
        );
      })}
    </>
  );
}

function SentenceList({ items, onRef, signalIds }: { items: Sentence[]; onRef: (r: string) => void; signalIds: Set<string> }) {
  return (
    <ol className="space-y-2">
      {items.map((s, i) => (
        <li key={i} className="text-sm leading-relaxed">
          <span>{s.text}</span>{' '}
          <span className="inline-flex flex-wrap gap-1 align-middle">
            <RefChips refs={s.refs} onRef={onRef} signalIds={signalIds} />
          </span>
        </li>
      ))}
    </ol>
  );
}

function ExplanationCard({
  caseId,
  state,
  setState,
  onRef,
  signalIds,
}: {
  caseId: string;
  state: { exp: Explanation | null; violations: Record<string, unknown>[]; model?: string; cached?: boolean };
  setState: (s: { exp: Explanation | null; violations: Record<string, unknown>[]; model?: string; cached?: boolean }) => void;
  onRef: (r: string) => void;
  signalIds: Set<string>;
}) {
  const { t, lang } = useI18n();
  const [view, setView] = useState<Lang>(lang);
  useEffect(() => setView(lang), [lang]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await explainCase(caseId);
      setState({ exp: r, violations: r.violations ?? [], model: r.model_id, cached: r.cached });
    } catch (e) {
      setErr(e instanceof ApiError || e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const e = state.exp;
  return (
    <Card
      title={t('c.explanation')}
      sub={t('c.refs_hint')}
      right={
        <>
          <div className="flex overflow-hidden rounded-md border border-line" role="group" aria-label={t('c.lang_view')}>
            {(['cs', 'en'] as const).map((l) => (
              <button key={l} className={`px-2 py-1 text-xs uppercase ${view === l ? 'bg-navy text-white dark:text-paper' : 'bg-surface text-muted'}`} aria-pressed={view === l} onClick={() => setView(l)}>
                {l}
              </button>
            ))}
          </div>
          <button className="btn-secondary" onClick={run} disabled={busy} aria-busy={busy}>
            {busy && <span className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-teal" aria-hidden="true" />}
            {busy ? t('c.generating') : e ? t('c.regenerate') : t('c.generate')}
          </button>
        </>
      }
    >
      <div className="space-y-4" aria-live="polite">
        {err && <ErrorBox error={err} />}
        {state.violations.length > 0 ? <ViolationList items={state.violations} title={t('c.qa_violations')} /> : e ? <p className="text-xs text-good">{t('c.qa_ok')}</p> : null}
        {!e && !busy && <p className="text-sm text-muted">{t('c.explanation_none')}</p>}
        {e && (
          <>
            <SentenceList items={e[view] ?? []} onRef={onRef} signalIds={signalIds} />
            {e.not_a_mom && (
              <div className="rounded-md border border-line bg-paper/60 p-3">
                <h3 className="label mb-1.5">{t('c.not_a_mom')}</h3>
                <SentenceList items={e.not_a_mom[view] ?? []} onRef={onRef} signalIds={signalIds} />
              </div>
            )}
            {e.triage_justification && (
              <div className="rounded-md border border-navy/20 bg-navy/5 p-3">
                <h3 className="label mb-1.5">{t('c.triage_justification')}</h3>
                <SentenceList items={[e.triage_justification[view]].filter(Boolean)} onRef={onRef} signalIds={signalIds} />
              </div>
            )}
            {(state.model || state.cached !== undefined) && (
              <p className="text-[11px] text-muted">
                {t('c.model')}: <span className="mono">{state.model ?? '–'}</span>
                {state.cached ? ` · ${t('c.cached')}` : ''}
              </p>
            )}
          </>
        )}
      </div>
    </Card>
  );
}

function TriageCard({ data }: { data: CaseDetail }) {
  const { t, lang } = useI18n();
  return (
    <Card title={t('c.triage_proposal')} right={<Chip tone="neutral">{t('common.proposal')}</Chip>}>
      <div className="flex flex-wrap items-center gap-2">
        <TriageChip triage={data.triage} />
        <RouteChip route={data.route} />
      </div>
      <h3 className="label mt-3">{t('c.reasons')}</h3>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
        {data.triage_reasons.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
      <h3 className="label mt-4">{t('c.escalation')}</h3>
      <p className="mt-1 text-sm">
        {t('c.escalation_role')}: <span className="font-semibold">{t(`role.${data.escalation.role}` as I18nKey)}</span>{' '}
        <span className="text-muted">
          ({t('c.matrix_row')} <span className="tnum">{data.escalation.rule_index}</span>)
        </span>
      </p>
      {data.escalation.matrix_is_placeholder && (
        <p className="mt-1.5">
          <Chip tone="warn">{t('c.matrix_placeholder')}</Chip>
        </p>
      )}
      {data.proposals.length > 0 && (
        <>
          <h3 className="label mt-4">{t('c.proposals_log')}</h3>
          <ol className="mt-1 space-y-1.5 border-l border-line pl-3 text-xs">
            {data.proposals.map((p, i) => (
              <li key={i}>
                <span className="mono text-muted">{new Date(p.ts).toLocaleString(lang === 'cs' ? 'cs-CZ' : 'en-GB')}</span> · <span className="mono">{p.agent}</span> → <TriageChip triage={p.triage} />
                <div className="text-muted">{p.reason}</div>
              </li>
            ))}
          </ol>
        </>
      )}
    </Card>
  );
}

function DecisionPanel({ data, onDone }: { data: CaseDetail; onDone: () => void }) {
  const { t, tx, lang } = useI18n();
  const { identity, meta } = useApp();
  const [action, setAction] = useState<'confirm' | 'override'>('confirm');
  const [reason, setReason] = useState('');
  const [decider, setDecider] = useState(identity.name);
  const [role, setRole] = useState(identity.role);
  const [approver, setApprover] = useState('');
  const [busy, setBusy] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  useEffect(() => {
    setDecider(identity.name);
    setRole(identity.role);
  }, [identity]);

  const minP = meta?.four_eyes_min_priority ?? 70;
  const fourEyes = data.priority >= minP;
  const overrideTarget = data.triage === 'FP' ? 'REVIEW' : 'FP';
  const reasonMissing = action === 'override' && !reason.trim();
  const canSubmit = !busy && decider.trim() !== '' && !reasonMissing;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setErr(null);
    setViolations(null);
    try {
      const r = await postDecision(data.case_id, { action, decider: decider.trim(), role, reason: reason.trim(), approver: fourEyes ? approver || null : approver || null });
      if (r.ok) {
        setAccepted(true);
        onDone();
      } else setViolations(r.violations ?? []);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  };

  if (data.decision) {
    const d = data.decision;
    return (
      <Card title={t('c.decided')} id="decision">
        {accepted && <p className="mb-3 text-sm text-good" role="status">{t('c.accepted')}</p>}
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className="label">{t('q.col_decision')}</dt>
          <dd>
            <StatusChip status={d.action === 'confirm' ? 'confirmed' : 'overridden'} />
          </dd>
          <dt className="label">{t('c.decider')}</dt>
          <dd>
            {d.decider} · {t(`role.${d.role}` as I18nKey)}
          </dd>
          <dt className="label">{t('c.approver')}</dt>
          <dd>{d.approver ?? '–'}</dd>
          <dt className="label">{t('c.reason')}</dt>
          <dd className="whitespace-pre-wrap">{d.reason || '–'}</dd>
          <dt className="label">{t('a.ts')}</dt>
          <dd className="mono">{new Date(d.ts).toLocaleString(lang === 'cs' ? 'cs-CZ' : 'en-GB')}</dd>
        </dl>
      </Card>
    );
  }

  return (
    <Card title={t('c.action')} sub={t('c.action_sub')} id="decision">
      <form onSubmit={submit} className="space-y-4">
        <fieldset>
          <legend className="sr-only">{t('c.action')}</legend>
          <div className="flex flex-wrap gap-2">
            <label className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${action === 'confirm' ? 'border-navy bg-navy/5' : 'border-line'}`}>
              <input type="radio" name="action" value="confirm" checked={action === 'confirm'} onChange={() => setAction('confirm')} className="accent-[rgb(var(--navy))]" />
              {t('c.confirm')} <TriageChip triage={data.triage} />
            </label>
            <label className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${action === 'override' ? 'border-warn bg-warnsoft' : 'border-line'}`}>
              <input type="radio" name="action" value="override" checked={action === 'override'} onChange={() => setAction('override')} className="accent-[rgb(var(--warn))]" />
              {t('c.override')} <TriageChip triage={data.triage} /> → <TriageChip triage={overrideTarget} />
            </label>
          </div>
        </fieldset>

        <div className="flex flex-col gap-1">
          <label htmlFor="reason" className="label">
            {t('c.reason')} {action === 'override' && <span className="text-bad">*</span>}
          </label>
          <textarea
            id="reason"
            rows={3}
            className={`input ${reasonMissing ? 'border-warn' : ''}`}
            placeholder={t('c.reason_ph')}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            aria-required={action === 'override'}
            aria-invalid={reasonMissing}
            aria-describedby="reason-help"
          />
          {action === 'override' && (
            <p id="reason-help" className={`text-xs ${reasonMissing ? 'text-warn' : 'text-muted'}`}>
              {t('c.reason_required')}
            </p>
          )}
        </div>

        <div className="flex flex-wrap gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="decider" className="label">
              {t('c.decider')}
            </label>
            <input id="decider" className="input w-52" value={decider} onChange={(e) => setDecider(e.target.value)} list="staff-list" />
            <datalist id="staff-list">
              {STAFF.map((s) => (
                <option key={s.name} value={s.name} />
              ))}
            </datalist>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="drole" className="label">
              {t('c.decider_role')}
            </label>
            <select id="drole" className="input" value={role} onChange={(e) => setRole(e.target.value)}>
              {(meta?.roles ?? ['analyst_l1', 'analyst_l2', 'aml_officer', 'mlro']).map((r) => (
                <option key={r} value={r}>
                  {t(`role.${r}` as I18nKey)}
                </option>
              ))}
            </select>
          </div>
          {fourEyes && (
            <div className="flex flex-col gap-1">
              <label htmlFor="approver" className="label">
                {t('c.approver')} <span className="text-bad">*</span>
              </label>
              <select id="approver" className="input w-60" value={approver} onChange={(e) => setApprover(e.target.value)} aria-describedby="fe-help">
                <option value="">{t('c.approver_none')}</option>
                {STAFF.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name} ({t(`role.${s.role}` as I18nKey)})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        {fourEyes && (
          <p id="fe-help" className="text-xs text-muted">
            <Chip tone="navy">{lang === 'cs' ? 'čtyři oči' : 'four eyes'}</Chip>{' '}{t('c.four_eyes', { n: minP })}
          </p>
        )}
        {!decider.trim() && <p className="text-xs text-warn">{t('c.no_name')}</p>}

        {violations && violations.length > 0 && (
          <div role="alert" className="rounded-md border border-bad/40 bg-badsoft p-3 text-sm">
            <p className="font-semibold text-bad">{t('c.rejected')}</p>
            <ul className="mt-2 space-y-1">
              {violations.map((v) => (
                <li key={v} className="flex flex-wrap items-baseline gap-2">
                  <span className="mono rounded bg-surface px-1.5 py-0.5 text-bad">{v}</span>
                  <span className="text-ink">{tx(`v.${v}`, '')}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {violations && violations.length === 0 && (
          <div role="alert" className="rounded-md border border-bad/40 bg-badsoft p-3 text-sm text-bad">
            {t('c.rejected')}
          </div>
        )}
        {err && <ErrorBox error={err} />}

        <div className="flex items-center gap-3">
          <button type="submit" className={action === 'override' ? 'btn-warn' : 'btn-primary'} disabled={!canSubmit}>
            {busy ? t('c.submitting') : t('c.submit')}
          </button>
          <span className="text-xs text-muted">
            {decider || '—'} · {t(`role.${role}` as I18nKey)}
          </span>
        </div>
      </form>
    </Card>
  );
}
