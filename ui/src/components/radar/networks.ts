/* Shared data for the network maps on Queue and Radar: disclosed radar clusters + their member cases. */
import { getClusterMembers, getRadar } from '../../api';
import type { QueueItem, RadarCluster, RadarResponse } from '../../types';
import type { BubbleGroup, BubbleLink, BubbleNode } from '../BubbleMap';

/** The API may add a significance (log10 of 1/p) later; shown only when present. */
export type Cluster = RadarCluster & { significance?: number | null; significance_log10?: number | null };

export interface Network {
  n: number; // 1-based display number
  cluster: Cluster;
  members: QueueItem[];
}

export interface NetworkData {
  radar: RadarResponse;
  networks: Network[];
  nodes: BubbleNode[];
  links: BubbleLink[];
  groups: BubbleGroup[];
}

export const netName = (n: number) => `Network ${n}`;

/** "same payout rhythm" wording from lag_ret_concentration. */
export function rhythm(c: Cluster): string | null {
  const v = c.lag_ret_concentration;
  if (v === null || v === undefined) return null;
  if (v >= 0.995) return 'same payout rhythm';
  return `same payout rhythm in ${Math.round(v * 100)} %`;
}

export function networkLine(nw: Network): string {
  const parts = [netName(nw.n), `${nw.members.length || nw.cluster.n_candidates} accounts`, `${nw.cluster.banks.length} banks`];
  const r = rhythm(nw.cluster);
  if (r) parts.push(r);
  return parts.join(' · ');
}

export async function loadNetworks(): Promise<NetworkData> {
  const radar = await getRadar();
  const disclosed = radar.clusters.filter((c) => c.disclosed) as Cluster[];
  const members = await getClusterMembers(disclosed.map((c) => c.cluster_id));
  const networks: Network[] = disclosed.map((cluster, i) => ({
    n: i + 1,
    cluster,
    members: [...(members[cluster.cluster_id] ?? [])].sort((a, b) => a.bank_id.localeCompare(b.bank_id) || b.priority - a.priority),
  }));
  const nodes: BubbleNode[] = [];
  const links: BubbleLink[] = [];
  const groups: BubbleGroup[] = networks.map((nw) => ({ id: nw.cluster.cluster_id, label: netName(nw.n) }));
  for (const nw of networks) {
    const hub = `hub:${nw.cluster.cluster_id}`;
    nodes.push({ id: hub, group: nw.cluster.cluster_id, bank: '', value: 0, label: `${nw.cluster.tokens} shared exit accounts`, hub: true });
    for (const m of nw.members) {
      nodes.push({
        id: m.case_id,
        group: nw.cluster.cluster_id,
        bank: m.bank_id,
        value: m.priority,
        label: `Client ${m.client_ref} · Bank ${m.bank_id} · priority ${m.priority}`,
        href: `/case/${m.case_id}`,
      });
      links.push({ source: m.case_id, target: hub });
    }
  }
  return { radar, networks, nodes, links, groups };
}
