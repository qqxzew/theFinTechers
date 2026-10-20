import type { Day, Raised, Win } from "../types";

interface Props {
  day: Day;
  win: Win | null;
  banks: string[];
  delayLabels: string[];
  bankTab: string;
  onTab: (b: string) => void;
  decisions: Record<string, "open" | "dismissed">;
  onDecide: (key: string, d: "open" | "dismissed") => void;
}

function inWindow(list: Raised[], w: Win): Raised[] {
  return list.filter((c) => {
    const k = c.evidence.window;
    return !!k && k.skim_lo === w.skim_lo && k.skim_hi === w.skim_hi && k.delay_bin === w.delay_bin && k.dormant === w.dormant && k.day_lo <= w.day_hi && k.day_hi >= w.day_lo;
  });
}

export function Drawer({ day, win, banks, delayLabels, bankTab, onTab, decisions, onDecide }: Props) {
  if (!win) {
    return (
      <aside className="drawer" aria-live="polite">
        <h2>Raised cases</h2>
        <p className="empty">Select a ringed window on the collector total.</p>
      </aside>
    );
  }
  const cards = inWindow(day.raised[bankTab] ?? [], win);
  return (
    <aside className="drawer" aria-live="polite">
      <h2>Window</h2>
      <dl className="kv">
        <dt>skim</dt>
        <dd>{win.skim_lo === win.skim_hi ? `${win.skim_lo} %` : `${win.skim_lo}–${win.skim_hi} %`}</dd>
        <dt>delay</dt>
        <dd>{delayLabels[win.delay_bin]}</dd>
        <dt>accounts</dt>
        <dd>{win.dormant ? "dormant / new" : "established"}</dd>
        <dt>days</dt>
        <dd>
          {win.day_lo - 29}–{win.day_hi - 29} July
        </dd>
        <dt>observed / expected</dt>
        <dd>
          {win.obs} / {win.expected.toFixed(2)}
        </dd>
        <dt>banks seeing it</dt>
        <dd>{win.banks}</dd>
        <dt>p-value</dt>
        <dd>{win.p.toExponential(1)}</dd>
        <dt>strength</dt>
        <dd>{win.strength}</dd>
      </dl>
      <div className="tabs" role="tablist">
        {banks.map((b) => (
          <button key={b} className="tab" role="tab" aria-selected={b === bankTab} onClick={() => onTab(b)}>
            {b} · {inWindow(day.raised[b] ?? [], win).length}
          </button>
        ))}
      </div>
      <div className="cards">
        {cards.length === 0 && <p className="empty">This bank raised nobody for this window.</p>}
        {cards.map((c) => {
          const key = bankTab + c.client;
          const ev = c.evidence;
          const decision = decisions[key];
          return (
            <article key={key} className={"card" + (decision ? " done" : "")}>
              <b>{c.client}</b>
              <span className="badge">Raised by network</span>
              <p>
                Had a pass-through inside this window. The window held {ev.totals.observed} customers across {ev.banks} banks where about{" "}
                {Number(ev.totals.expected).toFixed(1)} would be normal (p {ev.p_value.toExponential(1)}).
              </p>
              <div className="act">
                <button onClick={() => onDecide(key, "open")}>{decision === "open" ? "Queued ✓" : "Open case"}</button>
                <button onClick={() => onDecide(key, "dismissed")}>{decision === "dismissed" ? "Dismissed" : "Dismiss"}</button>
              </div>
            </article>
          );
        })}
      </div>
    </aside>
  );
}
