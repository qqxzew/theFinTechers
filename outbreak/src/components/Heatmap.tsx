import { useState } from "react";
import { heat } from "../color";
import type { Win } from "../types";

interface Props {
  title: string;
  grid: number[][];
  max: number;
  big?: boolean;
  delayLabels: string[];
  windows?: Win[];
  selectedId?: string | null;
  onPick?: (w: Win) => void;
}

const W = 6;
const H = 30;

export function Heatmap({ title, grid, max, big = false, delayLabels, windows = [], selectedId = null, onPick }: Props) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const cw = big ? 54 : 40;
  const ch = big ? 11 : 9;
  const ml = 28;
  const mt = 4;
  const mb = 28;
  const show = (e: React.MouseEvent, text: string) => setTip({ x: e.clientX + 12, y: e.clientY + 12, text });

  return (
    <div className={"panel" + (big ? " total" : "")}>
      {big && <span className="eq">B1 + B2 + B3 =</span>}
      <h2>{title}</h2>
      <svg viewBox={`0 0 ${ml + W * cw} ${mt + H * ch + mb}`} role="img" aria-label={`${title} heatmap, skim by delay`}>
        {grid.map((row, s) =>
          row.map((v, d) => (
            <rect
              key={`${s}-${d}`}
              className="cell"
              x={ml + d * cw}
              y={mt + s * ch}
              width={cw}
              height={ch}
              fill={heat(v, max)}
              onMouseMove={(e) => show(e, `${v} customer${v === 1 ? "" : "s"} · skim ${s + 1}% · ${delayLabels[d]}`)}
              onMouseLeave={() => setTip(null)}
            />
          )),
        )}
        {[1, 10, 20, 30].map((s) => (
          <text key={s} x={ml - 5} y={mt + (s - 1) * ch + ch * 0.8} textAnchor="end">
            {s}%
          </text>
        ))}
        {delayLabels.map((l, d) => (
          <text key={l} x={ml + d * cw + cw / 2} y={mt + H * ch + 14} textAnchor="middle">
            {big ? l : l.replace(" min", "m").replace(" h", "h")}
          </text>
        ))}
        {windows.map((w) => {
          const pick = () => onPick?.(w);
          return (
            <rect
              key={w.id}
              className={"win" + (selectedId === w.id ? " sel" : "")}
              x={ml + w.delay_bin * cw + 1}
              y={mt + (w.skim_lo - 1) * ch + 1}
              width={cw - 2}
              height={(w.skim_hi - w.skim_lo + 1) * ch - 2}
              tabIndex={0}
              role="button"
              aria-label={`Flagged window: skim ${w.skim_lo} to ${w.skim_hi} percent, ${delayLabels[w.delay_bin]}, ${w.dormant ? "dormant" : "active"} accounts, days ${w.day_lo - 29} to ${w.day_hi - 29}`}
              onClick={pick}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  pick();
                }
              }}
              onMouseMove={(e) => show(e, `observed ${w.obs} · expected ${w.expected.toFixed(2)} · p ${w.p.toExponential(1)}`)}
              onMouseLeave={() => setTip(null)}
            />
          );
        })}
      </svg>
      <div className="cap">
        <span>skim % ↓ · delay →</span>
        <span>{big ? "last 3 days · sum of the three" : "3 days · this bank"}</span>
      </div>
      {tip && (
        <div className="tip" style={{ display: "block", left: tip.x, top: tip.y }}>
          {tip.text}
        </div>
      )}
    </div>
  );
}
