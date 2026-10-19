import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { rememberCase } from '../Layout';
import { BANK_TONES } from '../BubbleMap';
import { netName, type Network } from './networks';

function Row({ k, v, hint }: { k: string; v: ReactNode; hint?: string }) {
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between gap-4">
        <dt className="text-[13px] text-muted">{k}</dt>
        <dd className="tnum text-right text-[14px] font-semibold text-ink">{v}</dd>
      </div>
      {hint && <p className="mt-0.5 text-[12px] text-faint">{hint}</p>}
    </div>
  );
}

/** Side panel for one network: the evidence, then its members per bank. */
export function NetworkPanel({ nw }: { nw: Network }) {
  const c = nw.cluster;
  const sig = c.significance_log10 ?? c.significance ?? null;
  const byBank = new Map<string, Network['members']>();
  for (const m of nw.members) {
    if (!byBank.has(m.bank_id)) byBank.set(m.bank_id, []);
    byBank.get(m.bank_id)!.push(m);
  }
  const count = nw.members.length || c.n_candidates;
  return (
    <aside className="card flex max-h-[576px] flex-col overflow-hidden" aria-label={`${netName(nw.n)} details`}>
      <div className="px-5 pt-5">
        <h3 className="text-[17px] font-semibold tracking-tight text-ink">{netName(nw.n)}</h3>
        <p className="text-[13px] text-muted">
          {count} accounts at {c.banks.length} banks pay out to the same {c.tokens} exit account{c.tokens === 1 ? '' : 's'}.
        </p>
        <dl className="mt-3" style={{ boxShadow: 'inset 0 -1px 0 rgb(22 24 29 / 0.06)' }}>
          <Row k="Banks" v={c.banks.join(', ')} />
          <Row k="Accounts" v={count} />
          <Row k="Shared exit accounts" v={c.tokens} />
          {sig !== null && sig !== undefined && (
            <Row k="Significance" v={<>1 in 10<sup>{Math.round(sig)}</sup></>} hint="How unlikely this overlap is by chance." />
          )}
          {c.lag_ret_concentration !== null && (
            <Row
              k="Same payout rhythm"
              v={`${Math.round(c.lag_ret_concentration * 100)} % of accounts`}
              hint="Same delay before paying out and same share kept."
            />
          )}
        </dl>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-5 pb-5 pt-3">
        {[...byBank.entries()].map(([bank, ms]) => (
          <div key={bank} className="mt-2">
            <p className="flex items-center gap-2 text-[13px] font-semibold text-ink">
              <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: BANK_TONES[bank] ?? '#999' }} />
              Bank {bank} <span className="font-normal text-muted">· {ms.length}</span>
            </p>
            <ul className="mt-1">
              {ms.map((m) => (
                <li key={m.case_id}>
                  <Link
                    to={`/case/${m.case_id}`}
                    onClick={() => rememberCase(m.case_id)}
                    className="flex items-center justify-between rounded-md px-2 py-1 text-[13px] hover:bg-paper focus-visible:bg-paper"
                  >
                    <span className="mono text-ink">{m.client_ref}</span>
                    <span className="tnum text-muted">priority {m.priority}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </aside>
  );
}
