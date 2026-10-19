// "Client": who this is, in plain facts with human units.
import type { ReactNode } from 'react';
import type { CaseDetail } from '../../types';
import { Card } from '../ui';
import { hlClass, useRefs } from './refs';
import { czk, int, times } from './text';

function refDate(c: CaseDetail): Date {
  const m = /(\d{4}-\d{2}-\d{2})/.exec(c.feature_glossary?.days_since_contract ?? '');
  return new Date(`${m ? m[1] : '2026-07-31'}T12:00:00Z`);
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export default function ClientCard({ data }: { data: CaseDetail }) {
  const { hl } = useRefs();
  const f = data.features;
  const num = (k: string) => (typeof f[k] === 'number' ? (f[k] as number) : undefined);
  const rows: { k: string; label: string; value: ReactNode; hint?: ReactNode }[] = [];

  const days = num('days_since_contract');
  if (days !== undefined) {
    const ref = refDate(data);
    const since = new Date(ref.getTime() - days * 86400000);
    rows.push({
      k: 'days_since_contract',
      label: 'Client since',
      value: since.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }),
      hint: `${int(days)} days ago`,
    });
  }
  if (typeof f.contract_form === 'string')
    rows.push({ k: 'contract_form', label: 'Contract signed', value: /person/i.test(f.contract_form) ? 'In person' : 'Remotely' });
  if (typeof f.client_type === 'string') rows.push({ k: 'client_type', label: 'Client type', value: f.client_type === 'natural person' ? 'Private person' : cap(f.client_type) });
  if (typeof f.aml_risk === 'string') rows.push({ k: 'aml_risk', label: 'AML risk', value: cap(f.aml_risk) });
  if (f.pep !== undefined) rows.push({ k: 'pep', label: 'Politically exposed', value: f.pep ? 'Yes' : 'No' });
  const nin = num('n_in');
  const nout = num('n_out');
  if (nin !== undefined && nout !== undefined) rows.push({ k: 'n_tx', label: 'Payments in July', value: `${int(nin)} in · ${int(nout)} out` });
  const ex = num('expected_monthly');
  const jt = num('july_total');
  if (ex !== undefined) rows.push({ k: 'expected_monthly', label: 'Expected per month', value: czk(ex) });
  if (jt !== undefined)
    rows.push({
      k: 'july_total',
      label: 'Actual in July',
      value: czk(jt),
      hint: ex ? (jt / ex >= 1.05 ? `${times(jt / ex)} expected` : jt / ex <= 0.95 ? `${times(jt / ex)} of expected` : 'as expected') : undefined,
    });

  return (
    <Card title="Client" sub="Who this is, from the bank’s own records." className="h-full">
      <dl className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
        {rows.map((r) => (
          <div key={r.k} id={`fact-${r.k}`} className={`-mx-2 rounded-lg px-2 py-1 ${hlClass(hl === `fact-${r.k}`)}`}>
            <dt className="text-[13px] text-muted">{r.label}</dt>
            <dd className="tnum text-[16px] font-medium text-ink">
              {r.value}
              {r.hint && <span className="ml-2 text-[13px] font-normal text-muted">{r.hint}</span>}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
