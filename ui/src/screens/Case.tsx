// Case screen: who the client is, what happened with the money, why the engine flagged it,
// what could still be innocent, what the engine proposes, and the decision.
import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getCase, type CaseBrief } from '../api';
import AskRule from '../components/case/AskRule';
import Brief from '../components/case/Brief';
import ClientCard from '../components/case/ClientCard';
import Decision from '../components/case/Decision';
import Money from '../components/case/Money';
import { Network, Proposal } from '../components/case/Proposal';
import { RefProvider } from '../components/case/refs';
import { Flagged, Innocent } from '../components/case/Signals';
import { proposalHeadline } from '../components/case/text';
import { rememberCase } from '../components/Layout';
import { Bar, ErrorBox, Loading, Page, PageTitle } from '../components/ui';
import { useAsync } from '../state';
import type { CaseDetail } from '../types';

type CaseWithBrief = CaseDetail & { brief?: CaseBrief | null };

export default function CaseScreen() {
  const { id } = useParams();
  useEffect(() => {
    if (id) rememberCase(id);
  }, [id]);
  const c = useAsync(() => (id ? getCase(id) : Promise.resolve(null)), [id]);

  if (!id)
    return (
      <Page>
        <PageTitle
          title="Case"
          description={
            <>
              Open a case from the{' '}
              <Link className="text-accent underline-offset-4 hover:underline" to="/">
                queue
              </Link>
              .
            </>
          }
        />
      </Page>
    );
  if (c.loading && !c.data) return <Loading label="Loading case…" />;
  if (c.error)
    return (
      <Page>
        <PageTitle title={`Case ${id}`} />
        <ErrorBox error={c.error} message={/404|Not found/.test(c.error) ? 'This case does not exist.' : undefined} onRetry={c.reload} />
      </Page>
    );
  if (!c.data) return null;
  return <CaseView data={c.data as CaseWithBrief} reload={c.reload} />;
}

function CaseView({ data, reload }: { data: CaseWithBrief; reload: () => void }) {
  const victim = data.route === 'victim_protection';
  const hasNet = !!data.cluster;
  return (
    <RefProvider data={data}>
      <Page className="!space-y-6">
        {/* 1. Header: who, priority, proposal | decision */}
        <section className="card grid gap-x-10 gap-y-6 px-6 py-6 lg:grid-cols-12" aria-label="Case summary and decision">
          <div className="flex min-w-0 flex-col justify-between gap-5 lg:col-span-7">
            <div>
              <p className="text-[13px] text-muted">
                Bank {data.bank_id} · Case <span className="font-mono text-[12px]">{data.case_id}</span>
              </p>
              <h1 className="mt-1 text-[34px] font-semibold leading-tight tracking-tight text-ink">{data.client_ref}</h1>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[15px] text-muted">Priority</span>
              <span className="tnum text-[28px] font-semibold leading-none text-ink">{data.priority}</span>
              <Bar value={data.priority} max={100} width="w-40" tone={data.priority >= 90 ? 'warn' : undefined} label={`priority ${data.priority} of 100`} />
              <span className="text-[13px] text-faint">of 100</span>
            </div>
            <div>
              <p className="text-[19px] leading-snug text-ink">
                <span className="text-muted">Engine proposes:</span> <span className="font-semibold">{proposalHeadline(data).replace(' — ', ' · ')}</span>
              </p>
              {victim && (
                <p className="mt-1.5 text-[15px] text-amber">This client looks like a scam victim. Protect the client; do not treat as a mule.</p>
              )}
            </div>
          </div>
          <div className="rounded-xl bg-paper px-5 py-4 lg:col-span-5">
            <Decision data={data} onDone={reload} />
          </div>
        </section>

        {/* 2-3. Client | In brief */}
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <ClientCard data={data} />
          </div>
          <div className="lg:col-span-7">
            <Brief data={data} />
          </div>
        </div>

        {/* 4. Money */}
        <Money data={data} />

        {/* 5-6. Flagged | Innocent */}
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <Flagged data={data} />
          </div>
          <div className="lg:col-span-6">
            <Innocent data={data} />
          </div>
        </div>

        {/* 7-8. Network | Proposal */}
        <div className="grid gap-6 lg:grid-cols-12">
          {hasNet && (
            <div className="lg:col-span-5">
              <Network data={data} />
            </div>
          )}
          <div className={hasNet ? 'lg:col-span-7' : 'lg:col-span-12'}>
            <Proposal data={data} wide={!hasNet} />
          </div>
        </div>

        {/* 9. Ask */}
        <AskRule caseId={data.case_id} />
      </Page>
    </RefProvider>
  );
}
