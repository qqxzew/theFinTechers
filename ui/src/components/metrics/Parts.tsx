import type { ReactNode } from 'react';
import { whoIs, whyFalseAlarm, whyMissed, schemeName, type FailureRow } from './derive';

/** One big headline number with a plain label and an optional one-line reading hint. */
export function HeadlineTile({ value, label, hint }: { value: ReactNode; label: ReactNode; hint?: ReactNode }) {
  return (
    <div className="card flex min-w-0 flex-col px-6 py-6">
      <div className="text-[14px] font-medium text-muted">{label}</div>
      <div className="tnum mt-3 text-[44px] font-semibold leading-none tracking-tight text-ink">{value}</div>
      {hint && <div className="mt-3 text-[13px] leading-snug text-muted">{hint}</div>}
    </div>
  );
}

function ListCard({ title, sub, children }: { title: string; sub: ReactNode; children: ReactNode }) {
  return (
    <div className="card min-w-0 px-6 py-5">
      <h3 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h3>
      <p className="mt-0.5 text-[13px] text-muted">{sub}</p>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function Row({ id, right, who, why }: { id: string; right: ReactNode; who: string; why: string }) {
  return (
    <li>
      <div className="flex items-baseline justify-between gap-4">
        <span className="min-w-0 truncate text-[14px] font-medium text-ink">
          {who} <span className="font-mono text-[12px] font-normal text-faint">{id}</span>
        </span>
        <span className="tnum shrink-0 text-[13px] text-muted">{right}</span>
      </div>
      <p className="mt-0.5 text-[13px] leading-snug text-muted">{why}</p>
    </li>
  );
}

const divided = 'space-y-4';

export function FalseAlarms({ rows, total }: { rows: FailureRow[]; total: number }) {
  const top = [...rows].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0)).slice(0, 5);
  return (
    <ListCard
      title="False alarms"
      sub={total ? `The ${top.length} highest-priority innocent accounts that were flagged, of ${total} in this world.` : 'No innocent account was flagged.'}
    >
      {top.length ? (
        <ul className={divided}>
          {top.map((r) => (
            <Row key={r.client_id} id={r.client_id} who={whoIs(r)} right={`priority ${r.priority ?? '–'}`} why={whyFalseAlarm(r)} />
          ))}
        </ul>
      ) : null}
    </ListCard>
  );
}

export function Missed({ rows, minPriority, nMules }: { rows: FailureRow[]; minPriority: number; nMules?: number }) {
  return (
    <ListCard
      title="Missed mules"
      sub={rows.length ? `Planted mules that did not become a flagged case.` : `None. All ${nMules ?? ''} planted mules in this world became a flagged case.`.replace('  ', ' ')}
    >
      {rows.length ? (
        <ul className={divided}>
          {rows.slice(0, 5).map((r) => (
            <Row key={r.client_id} id={r.client_id} who={schemeName(r.scheme)} right={r.priority !== undefined ? `priority ${r.priority}` : ''} why={whyMissed(r, minPriority)} />
          ))}
        </ul>
      ) : null}
    </ListCard>
  );
}
