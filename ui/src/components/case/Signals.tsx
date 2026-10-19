// "Why the engine flagged this" (signals grouped by meaning) and "What could still be innocent"
// (the checks for normal explanations). Same visual weight, side by side on wide screens.
import { useState } from 'react';
import type { CaseDetail, Signal } from '../../types';
import { Bar, Card } from '../ui';
import { hlClass, useRefs } from './refs';
import { GROUPS, INNOCENT, NOT_TRIGGERED, fmtEvidence, int, pct, groupSignals, signalFacts, signalSentence, type Fact } from './text';

function Facts({ facts }: { facts: Fact[] }) {
  if (!facts.length) return null;
  return (
    <p className="mt-1 flex flex-wrap gap-x-5 gap-y-0.5 text-[13px]">
      {facts.map((f, i) => (
        <span key={i} className="tnum">
          <span className="font-semibold text-ink">{f.value}</span> <span className="text-muted">{f.label}</span>
        </span>
      ))}
    </p>
  );
}

function Technical({ s, data }: { s: Signal; data: CaseDetail }) {
  const ev = Object.entries(s.evidence);
  return (
    <div className="mt-3 space-y-1.5 rounded-lg bg-paper px-3 py-2.5 text-[12.5px] text-muted">
      <p>
        <span className="font-mono text-ink">{s.signal_id}</span> · {s.source} · strength {s.score.toFixed(2)}
      </p>
      {data.rule_definitions[s.detector_id] && <p>{data.rule_definitions[s.detector_id]}</p>}
      {ev.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5">
          {ev.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-mono">{k}</dt>
              <dd className="tnum break-all text-ink">{Array.isArray(v) && v.every((x) => typeof x === 'string') ? (v as string[]).join(', ') : fmtEvidence(k, v) ?? (Array.isArray(v) ? v.length + ' values' : String(v))}</dd>
            </div>
          ))}
        </dl>
      )}
      {s.notes.length > 0 && <p className="font-mono">{s.notes.join(' · ')}</p>}
    </div>
  );
}

function Row({ s, data, sentence, facts, extra }: { s: Signal; data: CaseDetail; sentence: string; facts: Fact[]; extra?: string }) {
  const { hl } = useRefs();
  const [open, setOpen] = useState(false);
  const id = `sig-${s.signal_id}`;
  return (
    <li id={id} className={`-mx-3 rounded-lg px-3 py-3 ${hlClass(hl === id)}`}>
      <button type="button" className="group flex w-full items-start gap-4 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="min-w-0 flex-1">
          <span className="block text-[15px] leading-snug text-ink group-hover:underline group-hover:decoration-ink/30 group-hover:underline-offset-4">{sentence}</span>
          <Facts facts={facts} />
          {extra && <span className="mt-1 block text-[13px] text-muted">{extra}</span>}
        </span>
        <span className="mt-1.5 flex shrink-0 flex-col items-end gap-1">
          <Bar value={s.score} max={1} width="w-16" label={`strength ${Math.round(s.score * 100)} of 100`} />
          <span className="text-[11px] text-faint">{open ? 'less' : 'details'}</span>
        </span>
      </button>
      {open && <Technical s={s} data={data} />}
    </li>
  );
}

export function Flagged({ data }: { data: CaseDetail }) {
  const groups = groupSignals(data.signals);
  return (
    <Card title="Why the engine flagged this" sub="Warning signs, grouped by what they mean. The bar shows how strong each one is." className="h-full">
      {groups.length === 0 ? (
        <p className="text-[15px] text-muted">No warning signs.</p>
      ) : (
        <div className="space-y-5">
          {groups.map(({ group, items }) => (
            <div key={group.key}>
              <h4 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">{group.title}</h4>
              <ul className="mt-1">
                {items.map((s) => (
                  <Row key={s.signal_id} s={s} data={data} sentence={signalSentence(s)} facts={signalFacts(s, data)} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <NotTriggered data={data} />
    </Card>
  );
}

/** Checks that ran and did not fire: a short list when few signals fired, one line otherwise. */
function NotTriggered({ data }: { data: CaseDetail }) {
  const fired = new Set(data.signals.map((s) => s.detector_id));
  const ids = GROUPS.flatMap((g) => g.ids).filter((i) => i in NOT_TRIGGERED && !fired.has(i));
  if (!ids.length) return null;
  return (
    <div className="mt-5">
      <h4 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Checked, not triggered</h4>
      <ul className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 text-[13px] text-muted sm:grid-cols-2">
        {ids.map((i) => (
          <li key={i}>{NOT_TRIGGERED[i]}</li>
        ))}
      </ul>
    </div>
  );
}

export function Innocent({ data }: { data: CaseDetail }) {
  const items = [...data.exculpatory].sort((a, b) => b.score - a.score);
  return (
    <Card title="What could still be innocent" sub="Checks for normal explanations: regular salary, family transfers, rent splitting, shop payments." className="h-full">
      {items.length === 0 ? (
        <p className="text-[17px] font-medium text-ink">No normal explanation found.</p>
      ) : (
        <ul>
          {items.map((s) => {
            const t = INNOCENT[s.detector_id];
            const facts = Object.entries(s.evidence)
              .map(([k, v]) => ({ k, v: fmtEvidence(k, v) }))
              .filter((x): x is { k: string; v: string } => x.v !== null)
              .slice(0, 3)
              .map((x) => ({ label: INNOCENT_LABEL[x.k] ?? x.k.replace(/_/g, ' '), value: x.v }));
            return (
              <Row
                key={s.signal_id}
                s={s}
                data={data}
                sentence={t?.means ?? data.rule_definitions[s.detector_id] ?? 'A normal explanation matched.'}
                facts={facts}
                extra={t ? `Does not rule out: ${t.notRuledOut.charAt(0).toLowerCase()}${t.notRuledOut.slice(1)}` : undefined}
              />
            );
          })}
        </ul>
      )}
      <Checked data={data} />
    </Card>
  );
}

/** The normal explanations that were checked and did not match, each with the number it was judged on. */
function Checked({ data }: { data: CaseDetail }) {
  const hit = new Set(data.exculpatory.map((s) => s.detector_id));
  const f = data.features;
  const n = (k: string) => (typeof f[k] === 'number' ? (f[k] as number) : undefined);
  const rows: { ids: string[]; name: string; value?: string }[] = [
    { ids: ['E3'], name: 'Salary or other regular income', value: n('recurring_income_share') !== undefined ? `${pct(n('recurring_income_share')!)} of money in is regular` : undefined },
    { ids: ['E4'], name: 'Payments from an employer, insurer or platform', value: n('popular_inflow_share') !== undefined ? `${pct(n('popular_inflow_share')!)} of money in from large payers` : undefined },
    { ids: ['E2'], name: 'Ordinary spending at shops and utilities', value: n('share_popular') !== undefined ? `${pct(n('share_popular')!)} of money out` : undefined },
    { ids: ['E1'], name: 'Family support to one person', value: n('remit_top_recipient_count') !== undefined ? `${int(n('remit_top_recipient_count')!)} repeat payment${n('remit_top_recipient_count') === 1 ? '' : 's'} to one person` : undefined },
    { ids: ['E5'], name: 'Shared bills, money going both ways', value: n('reciprocity_share') !== undefined ? `${pct(n('reciprocity_share')!)} of volume two-way` : undefined },
    { ids: ['E6', 'E7'], name: 'Rent split, collection or co-hosting', value: n('days_since_contract') !== undefined ? `account ${int(n('days_since_contract')!)} days old` : undefined },
    { ids: ['E8'], name: 'Freelance earnings kept and spent', value: n('life_payment_share') !== undefined ? `${pct(n('life_payment_share')!)} of payments to common payees` : undefined },
  ];
  const missing = rows.filter((r) => !r.ids.some((i) => hit.has(i)));
  if (!missing.length) return null;
  return (
    <div className={data.exculpatory.length ? 'mt-5' : 'mt-4'}>
      <h4 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">{data.exculpatory.length ? 'Also checked, not found' : 'Checked, not found'}</h4>
      <ul className="mt-2">
        {missing.map((r) => (
          <li key={r.name} className="flex items-baseline justify-between gap-4 py-2 text-[15px]" style={{ boxShadow: 'inset 0 -1px 0 rgb(22 24 29 / 0.05)' }}>
            <span className="text-ink">{r.name}</span>
            {r.value && <span className="tnum shrink-0 text-[13px] text-muted">{r.value}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

const INNOCENT_LABEL: Record<string, string> = {
  share_popular: 'of money out goes to common payees',
  recurring_income_share: 'of money in is regular income',
  popular_inflow_share: 'of money in is from large payers',
  big_in_sender_degree: 'clients are paid by the main payer',
  reciprocity_share: 'of volume is two-way',
  top_exit_share: 'goes to one payee',
  life_payment_share: 'of payments go to common payees',
};
