import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getQueueSlice } from '../api';
import { useAsync } from '../state';
import { useI18n } from '../i18n';
import type { QueueItem } from '../types';
import BubbleMap, { type BubbleNode } from '../components/BubbleMap';
import { rememberCase } from '../components/Layout';
import { BankKey } from '../components/radar/BankKey';
import { loadNetworks, networkLine } from '../components/radar/networks';
import { roleWords, whyText } from '../components/queue/why';
import { Button, Card, ErrorBox, Loading, Page, PageTitle, PriorityBar, Section, Table, type Column } from '../components/ui';

const PAGE = 25;

export default function QueueScreen() {
  const { num } = useI18n();
  const nav = useNavigate();
  const nets = useAsync(loadNetworks, []);
  const review = useAsync(() => getQueueSlice({ triage: 'REVIEW', route: 'mule_review', limit: 2000, offset: 0 }), []);
  const victims = useAsync(() => getQueueSlice({ triage: 'REVIEW', route: 'victim_protection', limit: 100, offset: 0 }), []);
  const [shown, setShown] = useState(PAGE);
  const [hl, setHl] = useState<string | null>(null);

  const open = useCallback(
    (id: string) => {
      rememberCase(id);
      nav(`/case/${id}`);
    },
    [nav],
  );
  const onBubble = useCallback((n: BubbleNode) => open(n.id), [open]);

  // Singles: cases that need a decision and are not part of a cross-bank network.
  const singles = useMemo(() => (review.data?.items ?? []).filter((i) => !i.cluster_id), [review.data]);
  const counts = review.data?.counts ?? null;

  const columns: Column<QueueItem>[] = [
    { key: 'priority', header: 'Priority', render: (r) => <PriorityBar p={r.priority} />, width: '120px' },
    { key: 'client', header: 'Client', render: (r) => <span className="mono text-ink">{r.client_ref}</span>, width: '130px' },
    { key: 'bank', header: 'Bank', render: (r) => r.bank_id, width: '70px' },
    { key: 'why', header: 'Why', render: (r) => <span className="text-ink">{whyText(r)}</span> },
    { key: 'next', header: 'Next step', render: (r) => roleWords(r.escalation_role), width: '140px' },
    {
      key: 'status',
      header: 'Status',
      render: (r) => <span className={r.decision_status === 'open' ? 'text-faint' : 'font-medium text-ink'}>{r.decision_status}</span>,
      width: '100px',
    },
  ];
  const rowLabel = (r: QueueItem) => `Open case of client ${r.client_ref}, bank ${r.bank_id}, priority ${r.priority}`;

  return (
    <Page>
      <PageTitle
        title="Work queue"
        actions={
          counts && (
            <p className="text-[14px] text-muted">
              <span className="tnum font-semibold text-ink">{num(counts.review)}</span> cases need a decision ·{' '}
              <span className="tnum">{num(counts.fp_auto_closed)}</span> closed automatically
            </p>
          )
        }
      />

      <Section
        id="networks"
        title="Networks across banks"
        explain={
          <>
            Groups of accounts at different banks that send money to the same exit accounts. Each dot is one client; bigger means higher priority.{' '}
            <BankKey />
          </>
        }
      >
        {nets.loading && <Loading label="Loading networks…" />}
        {nets.error && <ErrorBox error={nets.error} onRetry={nets.reload} />}
        {nets.data && (
          <Card padded={false}>
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_300px]">
              <div className="px-2 py-2">
                <BubbleMap
                  nodes={nets.data.nodes}
                  links={nets.data.links}
                  groups={nets.data.groups}
                  size={{ height: 460 }}
                  onSelect={onBubble}
                  onSelectGroup={(g) => nav(`/radar?network=${g}`)}
                  highlightGroup={hl}
                  tooltip={(n) => n.label}
                  ariaLabel="Map of cross-bank networks; each dot is one client"
                />
              </div>
              <ol className="space-y-0.5 px-4 py-4 lg:pl-2" aria-label="Networks">
                {nets.data.networks.map((nw) => (
                  <li key={nw.cluster.cluster_id}>
                    <button
                      className="w-full rounded-lg px-3 py-2 text-left text-[13.5px] transition-colors hover:bg-paper focus-visible:bg-paper"
                      onMouseEnter={() => setHl(nw.cluster.cluster_id)}
                      onMouseLeave={() => setHl(null)}
                      onFocus={() => setHl(nw.cluster.cluster_id)}
                      onBlur={() => setHl(null)}
                      onClick={() => nav(`/radar?network=${nw.cluster.cluster_id}`)}
                    >
                      <span className="block font-semibold text-ink">{networkLine(nw).split(' · ')[0]}</span>
                      <span className="block text-muted">{networkLine(nw).split(' · ').slice(1).join(' · ')}</span>
                    </button>
                  </li>
                ))}
                <li className="px-3 pt-2 text-[12.5px] text-faint">Click a dot to open the client. Click a network for its evidence.</li>
              </ol>
            </div>
          </Card>
        )}
      </Section>

      <Section id="singles" title="Single cases" explain="Clients flagged on their own. Highest priority first.">
        {review.loading && <Loading />}
        {review.error && <ErrorBox error={review.error} onRetry={review.reload} />}
        {review.data && (
          <>
            <Table
              columns={columns}
              rows={singles.slice(0, shown)}
              rowKey={(r) => r.case_id}
              onRowClick={(r) => open(r.case_id)}
              rowLabel={rowLabel}
              caption="Single cases that need a decision"
              maxHeight="none"
            />
            <div className="flex items-center gap-4 text-[13px] text-muted">
              <span className="tnum">
                Showing {num(Math.min(shown, singles.length))} of {num(singles.length)}
              </span>
              {shown < singles.length && <Button onClick={() => setShown((s) => s + PAGE)}>Show 25 more</Button>}
            </div>
          </>
        )}
      </Section>

      {victims.data && victims.data.items.length > 0 && (
        <Section id="victims" title="Possible victims" explain="Clients who may be losing their own savings to a scam. Protect them; do not treat them as mules.">
          <Table
            columns={columns}
            rows={victims.data.items}
            rowKey={(r) => r.case_id}
            onRowClick={(r) => open(r.case_id)}
            rowLabel={rowLabel}
            caption="Possible victims"
            maxHeight="none"
          />
        </Section>
      )}
    </Page>
  );
}
