// "What happened with the money": a light timeline of money in vs. money out, and a fan diagram
// of where it came from and where it went.
import { useMemo } from 'react';
import { Bar as RBar, BarChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { CaseDetail, GraphEdge } from '../../types';
import { Card } from '../ui';
import { hlClass, useRefs } from './refs';
import { czk, hours, pct } from './text';

const ACCENT = 'rgb(30 56 102)';
const INK = 'rgb(22 24 29)';
const GREY = 'rgb(120 124 132)';
const MUTED = 'rgb(104 107 115)';

const DAY = 86400000;
const k = (v: number) => {
  const a = Math.abs(v);
  return a >= 1e6 ? `${(a / 1e6).toFixed(1)}M` : a >= 1000 ? `${Math.round(a / 1000)}k` : `${Math.round(a)}`;
};

interface Bucket {
  t: number;
  label: string;
  in: number;
  out: number;
  cps: string[];
}

function buckets(c: CaseDetail): { rows: Bucket[]; weekly: boolean } {
  if (!c.timeline.length) return { rows: [], weekly: false };
  const ts = c.timeline.map((e) => Date.parse(e.ts));
  const d0 = Math.floor(Math.min(...ts) / DAY) * DAY;
  const d1 = Math.floor(Math.max(...ts) / DAY) * DAY;
  const weekly = (d1 - d0) / DAY > 62;
  const step = weekly ? 7 * DAY : DAY;
  // Pad short histories so that a handful of payments do not become fat bars.
  const end = Math.max(d1, d0 + 20 * DAY);
  const rows: Bucket[] = [];
  for (let t = d0; t <= end; t += step)
    rows.push({ t, label: new Date(t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }), in: 0, out: 0, cps: [] });
  c.timeline.forEach((e, i) => {
    const b = rows[Math.min(rows.length - 1, Math.floor((ts[i] - d0) / step))];
    if (e.direction === 'in') b.in += e.amount_czk;
    else b.out -= e.amount_czk;
    if (!b.cps.includes(e.counterparty)) b.cps.push(e.counterparty);
  });
  return { rows, weekly };
}

function TimelineChart({ data }: { data: CaseDetail }) {
  const { rows, weekly } = useMemo(() => buckets(data), [data]);
  if (!rows.length) return <p className="text-sm text-muted">No payments in the data window.</p>;
  const max = Math.max(...rows.map((r) => Math.max(r.in, -r.out)), 1);
  // A round tick step so that two steps cover the largest bar.
  const raw = max / 2;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const nice = ([1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
  return (
    <div className="relative">
      <div className="pointer-events-none absolute left-0 top-0 z-10 w-[52px] pr-2 text-right text-[11px] text-faint">CZK</div>
      <div className="pointer-events-none absolute left-16 top-4 z-10 flex items-center gap-1.5 text-[12px] text-muted">
        <span className="h-2 w-2 rounded-sm" style={{ background: ACCENT }} aria-hidden="true" />
        Money in
      </div>
      <div className="pointer-events-none absolute bottom-7 left-16 z-10 flex items-center gap-1.5 text-[12px] text-muted">
        <span className="h-2 w-2 rounded-sm" style={{ background: GREY }} aria-hidden="true" />
        Money out
      </div>
      <div className="h-[232px] w-full" role="img" aria-label={`Money in and out per ${weekly ? 'week' : 'day'}, CZK`}>
        <ResponsiveContainer>
          <BarChart data={rows} stackOffset="sign" margin={{ top: 20, right: 8, bottom: 0, left: 0 }} barCategoryGap="20%">
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: MUTED }} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={28} />
            <YAxis
              tick={{ fontSize: 11, fill: MUTED }}
              tickFormatter={k}
              width={52}
              tickLine={false}
              axisLine={false}
              domain={[-nice * 2, nice * 2]}
              ticks={[-nice * 2, -nice, 0, nice, nice * 2]}
            />
            <ReferenceLine y={0} stroke="rgb(22 24 29 / 0.18)" />
            <Tooltip
              cursor={{ fill: 'rgb(22 24 29 / 0.04)' }}
              contentStyle={{ background: '#fff', border: 'none', borderRadius: 8, boxShadow: '0 2px 4px rgb(22 24 29 / .07), 0 8px 20px rgb(22 24 29 / .07)', fontSize: 12 }}
              labelStyle={{ color: INK, fontWeight: 600 }}
              formatter={(v: number, name: string) => [czk(Math.abs(v)), name === 'in' ? 'In' : 'Out']}
              labelFormatter={(l: string) => (weekly ? `Week of ${l}` : l)}
            />
            <RBar dataKey="in" stackId="a" fill={ACCENT} radius={[2, 2, 0, 0]} maxBarSize={14} isAnimationActive={false} />
            <RBar dataKey="out" stackId="a" fill={GREY} radius={[2, 2, 0, 0]} maxBarSize={14} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ fan diagram */

interface Leaf {
  id: string;
  amount: number;
  rare: boolean;
  y: number;
  r: number;
}

function Fan({ data }: { data: CaseDetail }) {
  const g = data.local_graph;
  const client = g.nodes.find((n) => n.kind === 'client');
  const kind = new Map(g.nodes.map((n) => [n.id, n.kind]));
  const ins = g.edges.filter((e) => e.direction === 'in' || e.target === client?.id);
  const outs = g.edges.filter((e) => !(e.direction === 'in' || e.target === client?.id));
  const amt = (e: GraphEdge) => e.amount_czk ?? 0;
  const maxA = Math.max(...g.edges.map(amt), 1);
  const rows = Math.max(ins.length, outs.length, 3);
  const rowH = 44;
  const H = rows * rowH + 32;
  const W = 1000;
  const cx = 420;
  const cy = H / 2;
  const xin = 210;
  const xout = 700;
  const top6 = new Set([...g.edges].sort((a, b) => amt(b) - amt(a)).slice(0, 6).map((e) => `${e.source}>${e.target}`));

  const layout = (es: GraphEdge[], other: (e: GraphEdge) => string): (Leaf & { e: GraphEdge })[] => {
    const sorted = [...es].sort((a, b) => amt(b) - amt(a));
    const span = (sorted.length - 1) * rowH;
    return sorted.map((e, i) => ({
      e,
      id: other(e),
      amount: amt(e),
      rare: kind.get(other(e)) !== 'counterparty_popular',
      y: cy - span / 2 + i * rowH,
      r: 4 + 13 * Math.sqrt(amt(e) / maxA),
    }));
  };
  const L = layout(ins, (e) => e.source);
  const R = layout(outs, (e) => e.target);
  const w = (a: number) => 1.5 + 16 * (a / maxA);
  const link = (x1: number, y1: number, x2: number, y2: number) => {
    const mx = (x1 + x2) / 2;
    return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
  };
  const node = (n: Leaf, side: 'in' | 'out', x: number) => {
    const labelled = top6.has(side === 'in' ? `${n.id}>${client?.id}` : `${client?.id}>${n.id}`);
    const lx = side === 'in' ? x - n.r - 10 : x + n.r + 10;
    const anchor = side === 'in' ? 'end' : 'start';
    return (
      <g key={`${side}-${n.id}`}>
        <title>{`${n.id} · ${czk(n.amount)} · ${n.rare ? 'rare account' : 'popular account'}`}</title>
        <circle cx={x} cy={n.y} r={n.r} fill={n.rare ? INK : '#fff'} fillOpacity={n.rare ? 0.88 : 1} stroke={INK} strokeWidth={n.rare ? 0 : 1.5} />
        {labelled && (
          <text x={lx} y={n.y} textAnchor={anchor} dominantBaseline="middle" fontSize={13}>
            <tspan fill={INK} fontFamily="JetBrains Mono, monospace" fontSize={12}>
              {n.id}
            </tspan>
            <tspan fill={MUTED} dx={8} className="tnum">
              {czk(n.amount)}
            </tspan>
          </text>
        )}
      </g>
    );
  };
  if (!client) return null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Where the money came from and where it went">
      <text x={xin} y={14} textAnchor="middle" fontSize={12} fill={MUTED}>
        Came from
      </text>
      <text x={xout} y={14} textAnchor="middle" fontSize={12} fill={MUTED}>
        Went to
      </text>
      {L.map((n) => (
        <path key={`li-${n.id}`} d={link(xin, n.y, cx, cy)} fill="none" stroke={ACCENT} strokeOpacity={0.22} strokeWidth={w(n.amount)} strokeLinecap="round" />
      ))}
      {R.map((n) => (
        <path key={`lo-${n.id}`} d={link(cx, cy, xout, n.y)} fill="none" stroke={INK} strokeOpacity={0.14} strokeWidth={w(n.amount)} strokeLinecap="round" />
      ))}
      {L.map((n) => node(n, 'in', xin))}
      {R.map((n) => node(n, 'out', xout))}
      <circle cx={cx} cy={cy} r={20} fill={ACCENT} />
      <text x={cx} y={cy + 36} textAnchor="middle" fontSize={13} fontWeight={600} fill={INK}>
        This client
      </text>
      <text x={cx} y={cy + 52} textAnchor="middle" fontSize={11} fill={MUTED} fontFamily="JetBrains Mono, monospace">
        {client.label}
      </text>
    </svg>
  );
}

export default function Money({ data }: { data: CaseDetail }) {
  const { hl } = useRefs();
  const f = data.features;
  const n = (key: string) => (typeof f[key] === 'number' ? (f[key] as number) : undefined);
  const facts: { label: string; value: string }[] = [];
  const inT = n('in_total');
  const outT = n('out_total');
  if (inT !== undefined) facts.push({ label: 'came in', value: czk(inT) });
  if (outT !== undefined) facts.push({ label: 'went out', value: czk(outT) });
  const drained = n('drained_24h_share');
  if (drained !== undefined && drained > 0) facts.push({ label: 'of the largest payment left within 24 h', value: pct(drained) });
  const lag = n('lag_median_h');
  if (lag !== undefined && (n('n_cycles') ?? 0) > 0) facts.push({ label: 'typical time before money moves on', value: hours(lag) });

  return (
    <section id="case-money" aria-labelledby="money-h" className={`rounded-2xl ${hlClass(hl === 'case-money')}`}>
      <Card padded={false}>
        <div className="grid gap-x-8 gap-y-6 px-6 pb-6 pt-5 lg:grid-cols-12">
          <header className="lg:col-span-12">
            <h2 id="money-h" className="text-[17px] font-semibold tracking-tight text-ink">
              What happened with the money
            </h2>
            <p className="mt-0.5 text-[14px] text-muted">Every payment in the data window, money in above the line, money out below.</p>
            <dl className="mt-4 flex flex-wrap gap-x-10 gap-y-3">
              {facts.map((x) => (
                <div key={x.label}>
                  <dd className="tnum text-[22px] font-semibold leading-none tracking-tight text-ink">{x.value}</dd>
                  <dt className="mt-1.5 text-[13px] text-muted">{x.label}</dt>
                </div>
              ))}
            </dl>
          </header>
          <div className="lg:col-span-12">
            <TimelineChart data={data} />
          </div>
          <div className="lg:col-span-12">
            <p className="text-[14px] text-muted">
              Where the money came from and where it went. Rare accounts (solid) are used by very few clients; popular accounts (hollow) by many. Line width shows the amount.
            </p>
            <div className="mx-auto mt-2 max-w-[1000px]">
              <Fan data={data} />
            </div>
          </div>
        </div>
      </Card>
    </section>
  );
}
