// "Network" (cross-bank match, only when it exists) and "Engine proposal" (headline, plain reasons,
// who decides and why).
import { useApp } from '../../state';
import type { CaseDetail } from '../../types';
import { Card } from '../ui';
import { hlClass, useRefs } from './refs';
import { int, plainReasons, proposalHeadline, whyThisPerson } from './text';

export function Network({ data }: { data: CaseDetail }) {
  const { hl } = useRefs();
  const c = data.cluster;
  if (!c) return null;
  const accts = c.matched_exit_accounts ?? [];
  return (
    <div id="case-network" className={`h-full rounded-xl ${hlClass(hl === 'case-network')}`}>
      <Card title="Network" sub="What other banks saw, matched without sharing raw data." className="h-full">
        <p className="text-[18px] leading-snug text-ink">
          This client’s exit accounts are also used by <span className="tnum font-semibold">{int(c.n_other_candidates)}</span> account
          {c.n_other_candidates === 1 ? '' : 's'} at <span className="tnum font-semibold">{int(c.n_other_banks)}</span> other bank{c.n_other_banks === 1 ? '' : 's'}.
        </p>
        {accts.length > 0 && (
          <div className="mt-4">
            <p className="text-[13px] text-muted">The shared exit accounts</p>
            <ul className="mt-1.5 flex flex-wrap gap-2">
              {accts.map((a) => (
                <li key={a} className="rounded-md bg-sunken px-2 py-1 font-mono text-[13px] text-ink">
                  {a}
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="mt-4 max-w-[60ch] text-[13px] leading-relaxed text-muted">
          Plain account numbers are known only to this bank; Stáj saw encrypted fingerprints. Finding the account holder is the bank’s own step.
        </p>
      </Card>
    </div>
  );
}

export function Proposal({ data, wide }: { data: CaseDetail; wide: boolean }) {
  const reasons = plainReasons(data);
  const minP = useApp().meta?.four_eyes_min_priority ?? 70;
  return (
    <Card title="Engine proposal" sub="What the engine suggests and why. You decide at the top of the page." className="h-full">
      <div className={wide ? 'grid gap-x-10 gap-y-5 md:grid-cols-12' : 'space-y-5'}>
        <div className={wide ? 'md:col-span-7' : ''}>
          <p className="text-[20px] font-semibold tracking-tight text-ink">{proposalHeadline(data)}</p>
          <ul className="mt-3 space-y-1.5">
            {reasons.map((r, i) => (
              <li key={i} className="text-[15px] leading-snug text-ink">
                {r}
              </li>
            ))}
          </ul>
          <details className="mt-3 text-[13px] text-muted">
            <summary className="cursor-pointer list-none hover:text-ink">Details</summary>
            <ul className="mt-2 space-y-0.5 font-mono text-[12px]">
              {data.triage_reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </details>
        </div>
        <div className={wide ? 'md:col-span-5' : ''}>
          <p className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Why this person decides</p>
          <p className="mt-1.5 text-[15px] leading-snug text-ink">{whyThisPerson(data)}</p>
          {data.priority >= minP && <p className="mt-1.5 text-[15px] leading-snug text-ink">A second person must approve, because priority is {minP} or more.</p>}
          {data.escalation.matrix_is_placeholder && (
            <p className="mt-2 text-[13px] text-muted">The escalation matrix is a placeholder until the bank sets its own.</p>
          )}
        </div>
      </div>
    </Card>
  );
}
