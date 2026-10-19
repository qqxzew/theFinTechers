/*
 * BubbleMap: a Bubblemaps-style cluster map on a light canvas.
 * One bubble per node, packed with d3-force (collide + pull towards its group, and inside a group
 * towards its bank's sector). The simulation runs synchronously once and is stopped, so the map
 * never jitters. Soft shadows, no strokes, thin curved links inside a group, labels on hover.
 */
import { forceCollide, forceSimulation, forceX, forceY, type SimulationNodeDatum } from 'd3-force';
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent, type ReactNode } from 'react';

export interface BubbleNode {
  id: string;
  group: string;
  bank: string;
  /** 0..100, drives the radius. */
  value: number;
  label: string;
  href?: string;
  /** A small anchor dot (e.g. the shared exit accounts of a network). Not hoverable as a case. */
  hub?: boolean;
}
export interface BubbleLink {
  source: string;
  target: string;
}
export interface BubbleGroup {
  id: string;
  label: string;
}

/** Three muted neutral tones, one per bank (dark, mid, light). */
export const BANK_TONES: Record<string, string> = { B1: '#2F3747', B2: '#7C8494', B3: '#C3C7CE' };
const FALLBACK = ['#2F3747', '#7C8494', '#C3C7CE', '#555C6B', '#A3A8B2'];
export function bankTone(bank: string, banks?: string[]) {
  if (BANK_TONES[bank]) return BANK_TONES[bank];
  const i = Math.max(0, banks?.indexOf(bank) ?? 0);
  return FALLBACK[i % FALLBACK.length];
}
const isDark = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  const l = 0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255);
  return l < 150;
};

interface Placed extends SimulationNodeDatum {
  n: BubbleNode;
  r: number;
  tx: number;
  ty: number;
  x: number;
  y: number;
}
interface GroupGeo {
  id: string;
  label: string;
  cx: number;
  cy: number;
  R: number;
  bankLabels: { bank: string; x: number; y: number }[];
}

function radiusOf(v: number, [lo, hi]: [number, number]) {
  const t = Math.max(0, Math.min(1, v / 100));
  return lo + (hi - lo) * Math.pow(t, 1.6);
}

function layout(nodes: BubbleNode[], groups: BubbleGroup[], aspect: number, rr: [number, number], bankLabelMin: number) {
  const byGroup = new Map<string, BubbleNode[]>();
  for (const n of nodes) {
    if (!byGroup.has(n.group)) byGroup.set(n.group, []);
    byGroup.get(n.group)!.push(n);
  }
  const order = groups.length ? groups.map((g) => g.id).filter((id) => byGroup.has(id)) : [...byGroup.keys()];
  const labelOf = new Map(groups.map((g) => [g.id, g.label]));

  // 1. Place groups: one circle per group, packed by a small force run that spreads them to the canvas aspect.
  type G = SimulationNodeDatum & { id: string; R: number; x: number; y: number };
  const gs: G[] = order.map((id, i) => {
    const members = byGroup.get(id)!;
    const area = members.reduce((s, n) => s + (n.hub ? 9 : (radiusOf(n.value, rr) + 1.5) ** 2), 0);
    const R = Math.sqrt(area) * 1.22 + 8;
    return { id, R, x: (i - order.length / 2) * 60, y: (i % 2 ? 1 : -1) * 20 };
  });
  const gap = 34;
  const gsim = forceSimulation(gs)
    .force('collide', forceCollide<G>((d) => d.R + gap).iterations(3))
    .force('x', forceX<G>(0).strength(0.02))
    .force('y', forceY<G>(0).strength(0.02 * Math.max(1, aspect * aspect)))
    .stop();
  for (let i = 0; i < 320; i++) gsim.tick();

  // 2. Place nodes: pull to the group centre, and within a group towards the bank sector.
  const placed: Placed[] = [];
  const geo: GroupGeo[] = [];
  for (const g of gs) {
    const members = byGroup.get(g.id)!;
    const banks = [...new Set(members.filter((m) => !m.hub).map((m) => m.bank))].sort();
    const spread = members.length >= 5 && banks.length > 1 ? g.R * 0.4 : 0;
    // first bank upper-left, never straight up (the group title sits there)
    const angle = (b: string) => (-5 * Math.PI) / 6 + (banks.indexOf(b) * 2 * Math.PI) / Math.max(1, banks.length);
    for (const n of members) {
      const a = angle(n.bank);
      const tx = n.hub ? g.x : g.x + Math.cos(a) * spread;
      const ty = n.hub ? g.y : g.y + Math.sin(a) * spread;
      placed.push({ n, r: n.hub ? 3 : radiusOf(n.value, rr), tx, ty, x: tx + ((placed.length * 7) % 13) - 6, y: ty + ((placed.length * 11) % 13) - 6, ...(n.hub ? { fx: g.x, fy: g.y } : {}) });
    }
  }
  const sim = forceSimulation(placed)
    .force('collide', forceCollide<Placed>((d) => d.r + 1.6).iterations(3))
    .force('x', forceX<Placed>((d) => d.tx).strength(0.14))
    .force('y', forceY<Placed>((d) => d.ty).strength(0.14))
    .stop();
  for (let i = 0; i < 300; i++) sim.tick();

  for (const g of gs) {
    const ms = placed.filter((p) => p.n.group === g.id);
    const cx = g.x;
    const cy = g.y;
    const R = Math.max(...ms.map((p) => Math.hypot(p.x - cx, p.y - cy) + p.r));
    const bankLabels: GroupGeo['bankLabels'] = [];
    const real = ms.filter((p) => !p.n.hub);
    if (real.length >= bankLabelMin) {
      for (const b of [...new Set(real.map((p) => p.n.bank))].sort()) {
        const bs = real.filter((p) => p.n.bank === b);
        const mx = bs.reduce((s, p) => s + p.x, 0) / bs.length;
        const my = bs.reduce((s, p) => s + p.y, 0) / bs.length;
        const a = Math.atan2(my - cy, mx - cx);
        bankLabels.push({ bank: b, x: cx + Math.cos(a) * (R + 13), y: cy + Math.sin(a) * (R + 13) + 4 });
      }
    }
    geo.push({ id: g.id, label: labelOf.get(g.id) ?? g.id, cx, cy, R, bankLabels });
  }
  // bounds incl. room for group labels above each group
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const g of geo) {
    x0 = Math.min(x0, g.cx - g.R - 26);
    x1 = Math.max(x1, g.cx + g.R + 26);
    y0 = Math.min(y0, g.cy - g.R - 30);
    y1 = Math.max(y1, g.cy + g.R + 22);
  }
  return { placed, geo, box: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } };
}

export interface BubbleMapProps {
  nodes: BubbleNode[];
  links?: BubbleLink[];
  groups?: BubbleGroup[];
  /** Height in px; width follows the container. */
  size?: { height: number };
  onSelect?: (n: BubbleNode) => void;
  /** Group click (e.g. open a side panel). */
  onSelectGroup?: (groupId: string) => void;
  selectedGroup?: string | null;
  /** Group highlighted from outside (e.g. hovering a list row). */
  highlightGroup?: string | null;
  tooltip?: (n: BubbleNode) => ReactNode;
  zoomable?: boolean;
  radiusRange?: [number, number];
  /** Groups with at least this many bubbles get direct bank labels. */
  bankLabelMin?: number;
  ariaLabel?: string;
}

function BubbleMapImpl({
  nodes,
  links = [],
  groups = [],
  size = { height: 420 },
  onSelect,
  onSelectGroup,
  selectedGroup = null,
  highlightGroup = null,
  tooltip,
  zoomable = false,
  radiusRange = [4.5, 12],
  bankLabelMin = 8,
  ariaLabel = 'Bubble map',
}: BubbleMapProps) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const H = size.height;
  const aspect = width / H;

  // Layout only depends on the data and the canvas aspect (rounded so resizes do not re-run it constantly).
  const aspectKey = Math.round(aspect * 4) / 4;
  const L = useMemo(() => layout(nodes, groups, aspectKey, radiusRange, bankLabelMin), [nodes, groups, aspectKey, radiusRange[0], radiusRange[1], bankLabelMin]); // eslint-disable-line react-hooks/exhaustive-deps
  const pos = useMemo(() => new Map(L.placed.map((p) => [p.n.id, p])), [L]);
  const banks = useMemo(() => [...new Set(nodes.map((n) => n.bank))].sort(), [nodes]);

  // fit
  const fit = Math.min(width / L.box.w, H / L.box.h, 2.2);
  const ox = (width - L.box.w * fit) / 2 - L.box.x * fit;
  const oy = (H - L.box.h * fit) / 2 - L.box.y * fit;

  // zoom / pan (only when zoomable)
  const [view, setView] = useState({ k: 1, x: 0, y: 0 });
  useEffect(() => setView({ k: 1, x: 0, y: 0 }), [L]);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const el = svgRef.current;
    if (!el || !zoomable) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const mx = e.clientX - r.left;
      const my = e.clientY - r.top;
      setView((v) => {
        const k = Math.max(0.6, Math.min(6, v.k * Math.exp(-e.deltaY * 0.0015)));
        return { k, x: mx - ((mx - v.x) * k) / v.k, y: my - ((my - v.y) * k) / v.k };
      });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [zoomable]);
  const onDown = (e: RPointerEvent<SVGSVGElement>) => {
    if (!zoomable) return;
    drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
  };
  const onMove = (e: RPointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (!d.moved && Math.hypot(dx, dy) < 4) return;
    if (!d.moved) (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    d.moved = true;
    setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
  };
  const wasDrag = useRef(false);
  const onUp = () => {
    wasDrag.current = !!drag.current?.moved;
    drag.current = null;
  };

  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const hoverNode = hover ? pos.get(hover.id)?.n ?? null : null;
  const focusGroup = hoverNode?.group ?? highlightGroup ?? selectedGroup;
  const dimOp = hoverNode || highlightGroup ? 0.3 : 0.55;
  const k = fit * view.k;
  const fs = (px: number) => px / k; // constant on-screen font size

  const click = useCallback(
    (n: BubbleNode) => {
      if (wasDrag.current) return;
      if (n.hub) onSelectGroup?.(n.group);
      else onSelect?.(n);
    },
    [onSelect, onSelectGroup],
  );

  // largest bubbles carry their number permanently
  const bigIds = useMemo(
    () => new Set(nodes.filter((n) => !n.hub).sort((a, b) => b.value - a.value || a.id.localeCompare(b.id)).slice(0, 5).map((n) => n.id)),
    [nodes],
  );

  return (
    <div ref={wrap} className="relative w-full select-none" style={{ height: H }}>
      <svg
        ref={svgRef}
        width={width}
        height={H}
        role="img"
        aria-label={ariaLabel}
        className={zoomable ? 'cursor-grab active:cursor-grabbing' : undefined}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={() => {
          onUp();
          setHover(null);
        }}
        onDoubleClick={() => zoomable && setView({ k: 1, x: 0, y: 0 })}
      >
        <defs>
          <filter id="bm-soft" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="1" stdDeviation="1" floodColor="#16181D" floodOpacity="0.16" />
            <feDropShadow dx="0" dy="3" stdDeviation="3" floodColor="#16181D" floodOpacity="0.08" />
          </filter>
        </defs>
        <g transform={`translate(${view.x},${view.y}) scale(${view.k}) translate(${ox},${oy}) scale(${fit})`}>
          {/* group halos: quiet click targets */}
          {L.geo.map((g) => {
            const dim = focusGroup && focusGroup !== g.id;
            return (
              <g key={g.id} style={{ opacity: dim ? dimOp : 1, transition: 'opacity 160ms' }}>
                <circle
                  cx={g.cx}
                  cy={g.cy}
                  r={g.R + 8}
                  fill={selectedGroup === g.id ? 'rgb(30 56 102 / 0.06)' : 'rgb(22 24 29 / 0.022)'}
                  className={onSelectGroup ? 'cursor-pointer' : undefined}
                  onClick={() => !wasDrag.current && onSelectGroup?.(g.id)}
                />
                <text
                  x={g.cx}
                  y={g.cy - g.R - 14}
                  textAnchor="middle"
                  fontSize={fs(13)}
                  fontWeight={600}
                  fill={selectedGroup === g.id ? 'rgb(30 56 102)' : 'rgb(22 24 29)'}
                  className={onSelectGroup ? 'cursor-pointer' : undefined}
                  onClick={() => !wasDrag.current && onSelectGroup?.(g.id)}
                >
                  {g.label}
                </text>
                {g.bankLabels.map((b) => (
                  <text key={b.bank} x={b.x} y={b.y} textAnchor="middle" fontSize={fs(11.5)} fontWeight={500} fill="rgb(104 107 115)" pointerEvents="none">
                    {b.bank}
                  </text>
                ))}
              </g>
            );
          })}
          {/* links */}
          <g fill="none" strokeLinecap="round">
            {links.map((l) => {
              const s = pos.get(l.source);
              const t = pos.get(l.target);
              if (!s || !t) return null;
              const mx = (s.x + t.x) / 2;
              const my = (s.y + t.y) / 2;
              const dx = t.x - s.x;
              const dy = t.y - s.y;
              const cx = mx - dy * 0.18;
              const cy = my + dx * 0.18;
              const on = focusGroup === s.n.group;
              const dim = focusGroup && !on;
              return (
                <path
                  key={`${l.source}>${l.target}`}
                  d={`M${s.x},${s.y} Q${cx},${cy} ${t.x},${t.y}`}
                  stroke={on ? 'rgb(30 56 102 / 0.45)' : 'rgb(22 24 29 / 0.14)'}
                  strokeWidth={on ? 1.1 / fit : 0.8 / fit}
                  style={{ opacity: dim ? dimOp : 1, transition: 'opacity 160ms' }}
                />
              );
            })}
          </g>
          {/* bubbles */}
          <g filter="url(#bm-soft)">
            {L.placed.map((p) => {
              const n = p.n;
              const tone = n.hub ? 'rgb(22 24 29)' : bankTone(n.bank, banks);
              const isHover = hover?.id === n.id;
              const dim = focusGroup && focusGroup !== n.group;
              return (
                <g
                  key={n.id}
                  transform={`translate(${p.x},${p.y})`}
                  style={{ opacity: dim ? dimOp : 1, transition: 'opacity 160ms' }}
                  className="cursor-pointer"
                  role={n.hub ? undefined : 'link'}
                  tabIndex={n.hub ? undefined : 0}
                  aria-label={n.hub ? undefined : n.label}
                  onPointerEnter={(e) => {
                    const r = wrap.current!.getBoundingClientRect();
                    setHover({ id: n.id, x: e.clientX - r.left, y: e.clientY - r.top });
                  }}
                  onPointerLeave={() => setHover((h) => (h?.id === n.id ? null : h))}
                  onFocus={() => setHover({ id: n.id, x: view.x + view.k * (ox + p.x * fit), y: view.y + view.k * (oy + p.y * fit) })}
                  onBlur={() => setHover(null)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      click(n);
                    }
                  }}
                  onClick={() => click(n)}
                >
                  <circle
                    r={p.r}
                    fill={tone}
                    style={{ transform: `scale(${isHover ? 1.35 : 1})`, transition: 'transform 180ms cubic-bezier(.2,.8,.2,1)' }}
                  />
                  {!n.hub && (bigIds.has(n.id) || isHover) && p.r * k >= 9 && (
                    <text
                      textAnchor="middle"
                      dy="0.35em"
                      fontSize={fs(9.5)}
                      fontWeight={600}
                      fill={isDark(tone) ? '#fff' : 'rgb(22 24 29)'}
                      pointerEvents="none"
                      className="tnum"
                    >
                      {n.value}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </g>
      </svg>
      {hover && hoverNode && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-20 whitespace-nowrap rounded-lg bg-surface px-3 py-1.5 text-[13px] text-ink shadow-raise"
          style={{ left: Math.min(hover.x + 14, width - 260), top: Math.max(4, hover.y - 40) }}
        >
          {tooltip ? tooltip(hoverNode) : hoverNode.label}
        </div>
      )}
    </div>
  );
}

const BubbleMap = memo(BubbleMapImpl);
export default BubbleMap;
