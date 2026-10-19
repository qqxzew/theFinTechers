import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { useEffect, useRef } from 'react';
import { useApp } from '../state';
import type { LocalGraph } from '../types';

const cssColor = (name: string) => {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v ? `rgb(${v.split(/\s+/).join(',')})` : '#888';
};

const fmtK = (n?: number) => (n === undefined ? '' : n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n));

interface Props {
  graph: LocalGraph;
  height?: number;
  layout?: 'concentric' | 'cose' | 'breadthfirst';
  ariaLabel: string;
  showAmounts?: boolean;
}

export default function Graph({ graph, height = 280, layout = 'concentric', ariaLabel, showAmounts = false }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const { dark } = useApp();

  useEffect(() => {
    if (!ref.current) return;
    const ink = cssColor('--ink');
    const muted = cssColor('--muted');
    const line = cssColor('--line');
    const navy = cssColor('--navy');
    const teal = cssColor('--teal');
    const warn = cssColor('--warn');
    const surface = cssColor('--surface');
    const ids = new Set(graph.nodes.map((n) => n.id));
    const els: ElementDefinition[] = [
      ...graph.nodes.map((n) => ({ data: { id: n.id, label: n.kind === 'client' || n.kind === 'bank' || n.label.length <= 9 ? n.label : n.label.slice(0, 8) + '…', kind: n.kind } })),
      ...graph.edges
        .filter((e) => ids.has(e.source) && ids.has(e.target))
        .map((e, i) => ({ data: { id: `e${i}`, source: e.source, target: e.target, label: showAmounts ? fmtK(e.amount_czk) : '', dir: e.direction ?? '' } })),
    ];
    const cy = cytoscape({
      container: ref.current,
      elements: els,
      autoungrabify: false,
      userZoomingEnabled: false,
      minZoom: 0.3,
      maxZoom: 3,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'font-size': 9,
            'font-family': 'ui-monospace, Consolas, monospace',
            color: muted,
            'text-valign': 'bottom',
            'text-margin-y': 4,
            width: 14,
            height: 14,
            'background-color': surface,
            'border-width': 1.5,
            'border-color': muted,
          },
        },
        { selector: 'node[kind = "client"]', style: { 'background-color': navy, 'border-color': navy, width: 22, height: 22, color: ink, 'font-weight': 600 } },
        { selector: 'node[kind = "counterparty_rare"]', style: { 'border-color': warn, 'background-color': surface } },
        { selector: 'node[kind = "counterparty_popular"]', style: { 'border-color': teal, 'background-color': teal, shape: 'round-rectangle' } },
        { selector: 'node[kind = "bank"]', style: { shape: 'round-rectangle', width: 34, height: 22, 'background-color': navy, 'border-color': navy, color: '#fff', 'text-valign': 'center', 'text-margin-y': 0, 'font-size': 10, 'font-weight': 700 } },
        { selector: 'node[kind = "candidate"]', style: { 'background-color': surface, 'border-color': navy, 'border-width': 2 } },
        { selector: 'node[kind = "token"]', style: { shape: 'diamond', width: 12, height: 12, 'background-color': warn, 'border-color': warn, 'font-size': 8 } },
        {
          selector: 'edge',
          style: {
            width: 1.2,
            'line-color': line,
            'curve-style': 'bezier',
            'target-arrow-shape': showAmounts ? 'triangle' : 'none',
            'target-arrow-color': line,
            'arrow-scale': 0.7,
            label: 'data(label)',
            'font-size': 8,
            color: muted,
            'text-background-color': surface,
            'text-background-opacity': 1,
            'text-background-padding': '1px',
          },
        },
        { selector: 'edge[dir = "in"]', style: { 'line-color': teal, 'target-arrow-color': teal } },
        { selector: 'edge[dir = "out"]', style: { 'line-color': warn, 'target-arrow-color': warn } },
      ],
      layout:
        layout === 'concentric'
          ? ({
              name: 'concentric',
              concentric: (n: cytoscape.NodeSingular) => (n.data('kind') === 'client' || n.data('kind') === 'bank' ? 10 : n.data('kind') === 'candidate' ? 5 : 1),
              levelWidth: () => 1,
              minNodeSpacing: 34,
              padding: 18,
              animate: false,
            } as cytoscape.LayoutOptions)
          : layout === 'cose'
            ? ({ name: 'cose', padding: 18, animate: false, nodeRepulsion: () => 6000, idealEdgeLength: () => 50, randomize: false } as cytoscape.LayoutOptions)
            : { name: 'breadthfirst', padding: 12, spacingFactor: 0.9, animate: false },
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph, layout, showAmounts, dark]);

  return (
    <div
      ref={ref}
      role="img"
      aria-label={ariaLabel}
      className="w-full rounded-md border border-line bg-paper/60"
      style={{ height }}
    />
  );
}
