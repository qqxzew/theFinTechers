import type { Day } from "../types";

interface Props {
  days: Day[];
  day: number;
  playing: boolean;
  onSelect: (i: number) => void;
  onTogglePlay: () => void;
}

export function DayRail({ days, day, playing, onSelect, onTogglePlay }: Props) {
  const maxW = Math.max(1, ...days.map((d) => d.windows.length));
  return (
    <nav className="rail" aria-label="Day">
      <h2>July 2026</h2>
      <div className="days">
        {days.map((d, i) => (
          <button key={d.t} className="day" aria-pressed={i === day} onClick={() => onSelect(i)}>
            <span>{String(d.t).padStart(2, "0")}</span>
            <span className="bar" title={`${d.windows.length} flagged windows`}>
              <i style={{ width: `${(100 * d.windows.length) / maxW}%` }} />
            </span>
          </button>
        ))}
      </div>
      <button className="play" type="button" onClick={onTogglePlay}>
        {playing ? "❚❚ PAUSE" : "▶ PLAY"}
      </button>
    </nav>
  );
}
