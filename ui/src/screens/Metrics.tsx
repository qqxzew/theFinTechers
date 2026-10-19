/*
 * Results (route /metrics). One question per block: does it work, how well, what it costs in
 * privacy, and where it fails. Charts are Grafana panels (infra/grafana, dashboard staj-eval);
 * every sentence of interpretation below them is computed from /api/metrics.
 */
import type { ReactNode } from 'react';
import { getMetrics } from '../api';
import { ErrorBox, Loading, Page, PageTitle, Section, Table } from '../components/ui';
import { useAsync } from '../state';
import type { MetricsResponse } from '../types';
import { GrafanaPanel, useGrafanaUp } from '../components/metrics/GrafanaPanel';
import { FalseAlarms, HeadlineTile, Missed } from '../components/metrics/Parts';
import {
  atThreshold,
  breakdownTakeaway,
  count,
  curve,
  headline,
  heldOutCount,
  int,
  pct0,
  privacySweep,
  privacyTakeaway,
  thresholdTakeaway,
  type FailureRow,
  type ModeKey,
} from '../components/metrics/derive';

/** Panel ids of the provisioned dashboard infra/grafana/dashboards/eval.json. */
const PANEL = { threshold: 2, privacy: 3, schemes: 5, personas: 6 } as const;

export default function MetricsScreen() {
  const m = useAsync(getMetrics, []);
  return (
    <Page>
      {m.loading && !m.data ? (
        <>
          <PageTitle title="Results" />
          <Loading />
        </>
      ) : m.error ? (
        <>
          <PageTitle title="Results" />
          <ErrorBox error={m.error} onRetry={m.reload} message="Could not load the results." />
        </>
      ) : m.data ? (
        <Results d={m.data} />
      ) : null}
    </Page>
  );
}

function Results({ d }: { d: MetricsResponse }) {
  const up = useGrafanaUp();
  const minP = d.operating_point?.min_priority ?? 30;
  const h = headline(d);
  const c = curve(d);
  const nWorlds = heldOutCount(d);
  const sAt = c ? atThreshold(c, 'staj_psi', minP) : null;
  const iAt = c ? atThreshold(c, 'isolated', minP) : null;
  const nAccounts = d.modes.staj_psi?.overall.n_accounts;
  const privacy = privacySweep(d);
  const fps = (d.failures?.worst_false_positives ?? []) as unknown as FailureRow[];
  const fns = (d.failures?.false_negatives ?? []) as unknown as FailureRow[];
  const demo = d.modes.staj_psi?.overall;

  return (
    <>
      <PageTitle
        title="Results"
        description={
          <>
            We planted known money-mule schemes and honest look-alikes in a simulated world of three banks and counted what Stáj catches; the real CNB data contain no mules, so
            they cannot be scored this way. A case counts as flagged when it is in REVIEW with priority ≥ {minP}.
          </>
        }
      />

      {/* 1. Headline */}
      <section aria-label="Headline results" className="grid gap-4 md:grid-cols-3">
        {h?.isolated && h.staj_psi ? (
          <HeadlineTile
            label="Mules found"
            value={
              <>
                <span className="text-muted">{Math.round(h.isolated.recall * 100)}</span>
                <span className="mx-2 text-faint" aria-label="to">
                  →
                </span>
                <span className="text-accent">{Math.round(h.staj_psi.recall * 100)} %</span>
              </>
            }
            hint="Banks working alone, then banks working together through Stáj."
          />
        ) : null}
        {sAt ? (
          <HeadlineTile
            label="False alarms"
            value={count(sAt.fp)}
            hint={
              <>
                Innocent accounts flagged per world of {nAccounts ? `about ${int(Math.round(nAccounts / 100) * 100)}` : 'several thousand'} accounts
                {iAt ? `; banks alone: ${count(iAt.fp)}.` : '.'}
              </>
            }
          />
        ) : null}
        {h?.staj_psi ? (
          <HeadlineTile
            label="Customer records shared"
            value={int(h.staj_psi.raw_records_exposed)}
            hint={h.naive_raw_sharing ? `Versus ${int(h.naive_raw_sharing.raw_records_exposed)} if the banks pooled their data. Only blinded tokens cross.` : 'Only blinded tokens cross between banks.'}
          />
        ) : null}
      </section>

      {/* 2. Charts */}
      <Section title="How well it works" explain={nWorlds ? `Averages over ${nWorlds} test worlds that were not used for tuning, unless a chart says otherwise.` : undefined}>
        <div className="space-y-10">
          <GrafanaPanel
            up={up}
            panelId={PANEL.threshold}
            title="Mules found as the priority cut-off rises"
            howToRead="Each line is one setup. A point shows how many planted mules are found if only cases at or above that priority count. Higher is better. In the chart, “Isolated” means banks alone, “Stáj PSI” is Stáj and “Naive raw sharing” is pooled data."
            takeaway={c ? thresholdTakeaway(c, minP) : null}
            ratio="16 / 6"
          />
          <div className="space-y-3">
            <div className="grid gap-6 md:grid-cols-2">
              <GrafanaPanel
                up={up}
                panelId={PANEL.schemes}
                title="Found, per mule scheme"
                howToRead="Share of each planted scheme's mules that became a flagged case. One example world."
                ratio="4 / 3"
              />
              <GrafanaPanel
                up={up}
                panelId={PANEL.personas}
                title="False alarms, per honest look-alike"
                howToRead="Share of honest clients who resemble mules that were wrongly flagged. Lower is better."
                ratio="4 / 3"
              />
            </div>
            <p className="max-w-3xl text-[14px] leading-snug text-ink">{breakdownTakeaway(d)}</p>
          </div>
          <GrafanaPanel
            up={up}
            panelId={PANEL.privacy}
            title="Privacy cost of finding the hidden ring"
            howToRead="Left to right, each bank also exports blinded tokens for more of its weakest suspects. A point at the top means the hidden cross-bank ring was found. Dark line: test worlds; grey: tuning worlds."
            takeaway={privacyTakeaway(privacy)}
            ratio="16 / 6"
          />
        </div>
      </Section>

      {/* 3. Failures */}
      <Section title="Where it fails" explain="Every error in one example world, in plain words.">
        <div className="grid gap-4 md:grid-cols-2">
          <FalseAlarms rows={fps} total={demo?.fp ?? fps.length} />
          <Missed rows={fns} minPriority={minP} nMules={demo?.n_mules} />
        </div>
        <AblationNote d={d} />
      </Section>

      {/* 4. Limits */}
      <Section title="What these numbers do not prove">
        <ul className="max-w-3xl list-disc space-y-2 pl-5 text-[14px] leading-snug text-ink marker:text-faint">
          <li>The mule scenarios were written by the same team that built the detectors. The real CNB data contain no known mules, so detection on real accounts is unmeasured.</li>
          <li>
            The headline numbers average only {nWorlds || 'a few'} test worlds. One mule more or less moves “found” by about{' '}
            {demo?.n_mules ? `${Math.round(100 / demo.n_mules)}` : 'a few'} percentage points.
          </li>
          <li>
            Finding the hidden ring needs each bank to export blinded tokens for its weakest
            {d.weak_evidence_experiment?.frozen_config?.weak_top_frac ? ` ${Math.round(d.weak_evidence_experiment.frozen_config.weak_top_frac * 100)} %` : ''} of accounts. No records leave
            the bank, but more customers are touched, and the exchange assumes every bank follows the protocol honestly.
          </li>
        </ul>
      </Section>

      <AllNumbers d={d} />
    </>
  );
}

function AblationNote({ d }: { d: MetricsResponse }) {
  const a = d.ablations ?? {};
  const full = a.full;
  const noInn = a.without_innocence_layer;
  const noPat = a.without_D6_D7;
  if (!full || (!noInn && !noPat)) return null;
  const parts: string[] = [];
  if (noInn) parts.push(`without the “innocent explanations” layer, false alarms rise from ${full.fp} to ${noInn.fp}`);
  if (noPat) parts.push(`without the pattern detectors (same hand, fixed skim), only ${noPat.tp} of ${full.tp + full.fn} mules are found instead of ${full.tp}`);
  return (
    <p className="max-w-3xl text-[13px] leading-snug text-muted">
      What each layer contributes, same world: {parts.join('; ')}.
    </p>
  );
}

/* ------------------------------------------------------------------ expert drawer */

interface NumRow {
  k: string;
  what: string;
  vals: Partial<Record<ModeKey, ReactNode>>;
}

function AllNumbers({ d }: { d: MetricsResponse }) {
  const h = headline(d);
  const c = curve(d);
  const minP = d.operating_point?.min_priority ?? 30;
  const modes: ModeKey[] = ['isolated', 'staj_psi', 'naive_raw_sharing'];
  const rows: NumRow[] = [];
  if (h) {
    rows.push({ k: 'found', what: 'Mules found', vals: Object.fromEntries(modes.map((m) => [m, h[m] ? pct0(h[m]!.recall) : '–'])) });
    rows.push({ k: 'prec', what: 'Flagged cases that are real mules', vals: Object.fromEntries(modes.map((m) => [m, h[m] ? pct0(h[m]!.precision) : '–'])) });
  }
  if (c) {
    rows.push({ k: 'fp', what: `False alarms per world (priority ≥ ${minP})`, vals: Object.fromEntries(modes.map((m) => [m, atThreshold(c, m, minP) ? count(atThreshold(c, m, minP)!.fp) : '–'])) });
    rows.push({ k: 'miss', what: `Missed mules per world (priority ≥ ${minP})`, vals: Object.fromEntries(modes.map((m) => [m, atThreshold(c, m, minP) ? count(atThreshold(c, m, minP)!.fn) : '–'])) });
  }
  if (h) {
    rows.push({ k: 'rec', what: 'Customer records shared', vals: Object.fromEntries(modes.map((m) => [m, h[m] ? int(h[m]!.raw_records_exposed) : '–'])) });
    rows.push({ k: 'mb', what: 'Data exchanged between banks', vals: Object.fromEntries(modes.map((m) => [m, h[m] ? `${(h[m]!.bytes_exchanged / 1e6).toFixed(1)} MB` : '–'])) });
  }
  const cnb = d.cnb;
  if (!rows.length && !cnb) return null;
  const col = (m: ModeKey, header: string) => ({ key: m, header, align: 'right' as const, render: (r: NumRow) => <span className="tnum">{r.vals[m] ?? '–'}</span> });
  return (
    <details className="group card px-6 py-4 [&_summary::-webkit-details-marker]:hidden">
      <summary className="flex cursor-pointer list-none items-center justify-between text-[15px] font-semibold text-ink">
        All numbers
        <span className="text-[13px] font-normal text-muted group-open:hidden">Show</span>
        <span className="hidden text-[13px] font-normal text-muted group-open:inline">Hide</span>
      </summary>
      <div className="mt-4 space-y-4">
        <Table<NumRow>
          caption="All headline numbers"
          rowKey={(r) => r.k}
          rows={rows}
          maxHeight="none"
          columns={[
            { key: 'what', header: 'Average over test worlds', render: (r) => r.what },
            col('isolated', 'Banks alone'),
            col('staj_psi', 'Stáj'),
            col('naive_raw_sharing', 'Pooled data'),
          ]}
        />
        {cnb && (
          <p className="text-[13px] leading-snug text-muted">
            Real CNB data ({int(cnb.n_clients)} clients, no known mules):{' '}
            {cnb.actionable_review !== undefined ? `${int(cnb.actionable_review)} cases reach the flag line` : `${int(cnb.cases ?? 0)} cases are opened`}
            {cnb.mom_persona?.review_actionable !== undefined
              ? `, and ${cnb.mom_persona.review_actionable} of the ${int(cnb.mom_persona.n)} clients who regularly send money to one relative are flagged`
              : ''}
            .
          </p>
        )}
        <p className="text-[12px] leading-snug text-faint">
          For specialists: “found” is recall, the share of planted mules that became a flagged case. Precision is the share of flagged cases that are real mules.
        </p>
      </div>
    </details>
  );
}
