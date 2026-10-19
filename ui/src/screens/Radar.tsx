import { useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAsync } from '../state';
import { useI18n } from '../i18n';
import BubbleMap, { type BubbleNode } from '../components/BubbleMap';
import { rememberCase } from '../components/Layout';
import { loadNetworks, type NetworkData } from '../components/radar/networks';
import { NetworkPanel } from '../components/radar/NetworkPanel';
import { Card, ErrorBox, Loading, Page, PageTitle, Section, Table, type Column } from '../components/ui';

function fmtBytes(b: number, num: (n: number, d?: number) => string) {
  if (b >= 1e6) return `${num(b / 1e6, 1)} MB`;
  if (b >= 1e3) return `${num(Math.round(b / 1e3))} KB`;
  return `${num(b)} B`;
}

export default function RadarScreen() {
  const { num } = useI18n();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const q = useAsync(loadNetworks, []);
  const onBubble = useCallback(
    (n: BubbleNode) => {
      rememberCase(n.id);
      nav(`/case/${n.id}`);
    },
    [nav],
  );
  const onGroup = useCallback((g: string) => setSp({ network: g }, { replace: true }), [setSp]);

  if (q.loading) return <Page><PageTitle title="Radar" /><Loading label="Loading the radar…" /></Page>;
  if (q.error || !q.data) return <Page><PageTitle title="Radar" /><ErrorBox error={q.error ?? 'no data'} onRetry={q.reload} /></Page>;
  const d = q.data;
  const selId = sp.get('network') ?? d.networks[0]?.cluster.cluster_id ?? null;
  const sel = d.networks.find((n) => n.cluster.cluster_id === selId) ?? d.networks[0];
  const banks = d.radar.banks.map((b) => b.bank_id);
  const nAccounts = d.networks.reduce((s, n) => s + n.members.length, 0);

  return (
    <Page>
      <header>
        <PageTitle title="Radar" />
        <div className="mt-2 max-w-3xl space-y-1 text-[15px] text-muted">
          <p>Banks compare only encrypted fingerprints of exit accounts. No customer data leaves a bank.</p>
          <p>
            It found <span className="font-semibold text-ink">{d.networks.length} networks</span> across{' '}
            <span className="font-semibold text-ink">{banks.length} banks</span>: {num(nAccounts)} accounts that pay out to the same exit accounts.
          </p>
          <p>For each network you get your own clients in it and the evidence that links them.</p>
        </div>
      </header>

      <Section
        id="map"
        title="Networks"
        explain="Each dot is one client, shaded by bank and sized by priority. Lines lead to the exit accounts the network shares. Scroll to zoom, drag to move, click a network for details."
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <Card padded={false}>
            <div className="p-2">
              <BubbleMap
                nodes={d.nodes}
                links={d.links}
                groups={d.groups}
                size={{ height: 560 }}
                onSelect={onBubble}
                onSelectGroup={onGroup}
                selectedGroup={sel?.cluster.cluster_id ?? null}
                tooltip={(n) => n.label}
                zoomable
                radiusRange={[5, 13]}
                bankLabelMin={5}
                ariaLabel="Zoomable map of cross-bank networks"
              />
            </div>
          </Card>
          {sel && <NetworkPanel nw={sel} />}
        </div>
      </Section>

      <AloneVsStaj d={d} />
      <Shared d={d} />
    </Page>
  );
}

function AloneVsStaj({ d }: { d: NetworkData }) {
  const { num } = useI18n();
  const rows = d.radar.banks.map((b) => {
    const mine = d.networks.flatMap((n) => n.members.filter((m) => m.bank_id === b.bank_id));
    const flaggedInNet = mine.filter((m) => m.triage === 'REVIEW').length;
    const notFlagged = mine.length - flaggedInNet;
    const nets = d.networks.filter((n) => n.members.some((m) => m.bank_id === b.bank_id));
    const others = new Set(nets.flatMap((n) => n.cluster.banks)).size - 1;
    const linked = nets.reduce((s, n) => s + n.members.filter((m) => m.bank_id !== b.bank_id).length, 0);
    return { b, mine: mine.length, flaggedInNet, notFlagged, nets: nets.length, others, linked };
  });
  return (
    <Section
      id="alone"
      title="What each bank sees alone vs. what Stáj sees"
      explain="Alone, a bank sees a list of suspicious clients. With Stáj it learns which of them belong to the same network at other banks."
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {rows.map((r) => (
          <Card key={r.b.bank_id} title={`Bank ${r.b.bank_id}`}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-[12px] font-medium text-muted">Alone</p>
                <p className="tnum mt-1 text-[28px] font-semibold leading-none text-ink">{num(r.b.n_review)}</p>
                <p className="mt-1.5 text-[13px] text-muted">clients flagged, no link to other banks</p>
              </div>
              <div>
                <p className="text-[12px] font-medium text-accent">With Stáj</p>
                <p className="tnum mt-1 text-[28px] font-semibold leading-none text-accent">{num(r.flaggedInNet)}</p>
                <p className="mt-1.5 text-[13px] text-muted">
                  of them in {r.nets} network{r.nets === 1 ? '' : 's'}, linked to {num(r.linked)} accounts at {r.others} other bank{r.others === 1 ? '' : 's'}
                </p>
              </div>
            </div>
            {r.notFlagged > 0 && <p className="mt-3 text-[12.5px] text-amber">{r.notFlagged} network accounts were not flagged by the bank alone.</p>}
          </Card>
        ))}
      </div>
    </Section>
  );
}

interface PairRow {
  pair: string;
  elements: number;
  bytes: number;
}

function Shared({ d }: { d: NetworkData }) {
  const { num } = useI18n();
  const ex = d.radar.exposure;
  const psi = ex.staj_psi;
  const perEl = psi && psi.blinded_elements ? psi.bytes_exchanged / psi.blinded_elements : 0;
  const rows: PairRow[] = useMemo(() => {
    const m = new Map<string, number>();
    for (const w of d.radar.wire) {
      if (!/^B\w+:B\w+$/.test(w.session)) continue;
      m.set(w.session, (m.get(w.session) ?? 0) + w.n);
    }
    return [...m.entries()].map(([s, n]) => ({ pair: s.replace(':', ' and '), elements: n, bytes: n * perEl }));
  }, [d.radar.wire, perEl]);
  const cols: Column<PairRow>[] = [
    { key: 'pair', header: 'Banks', render: (r) => <span className="text-ink">{r.pair}</span> },
    { key: 'el', header: 'Encrypted elements', align: 'right', render: (r) => <span className="tnum">{num(r.elements)}</span> },
    { key: 'b', header: 'Data sent', align: 'right', render: (r) => <span className="tnum">{fmtBytes(r.bytes, num)}</span> },
    { key: 'raw', header: 'Customer records', align: 'right', render: () => <span className="tnum">0</span> },
  ];
  const naive = ex.naive_raw_sharing;
  return (
    <Section id="shared" title="What was shared" explain="Every message between banks during the comparison, per pair of banks.">
      <div className="max-w-3xl space-y-3">
        <Table columns={cols} rows={rows} rowKey={(r) => r.pair} caption="Data exchanged per bank pair" maxHeight="none" />
        <p className="text-[15px] text-ink">
          Raw customer records shared: <span className="tnum font-semibold">{num(psi?.raw_records_exposed ?? 0)}</span>.
          {naive && (
            <span className="text-muted">
              {' '}
              Pooling raw data instead would expose <span className="tnum">{num(naive.raw_records_exposed)}</span> records (
              {fmtBytes(naive.bytes_exchanged, num)}).
            </span>
          )}
        </p>
      </div>
    </Section>
  );
}
