import { useCallback, useEffect, useMemo, useState } from "react";
import { DayRail } from "./components/DayRail";
import { Drawer } from "./components/Drawer";
import { Heatmap } from "./components/Heatmap";
import type { Data, Win } from "./types";

export function App() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState(false);
  const [day, setDay] = useState(0);
  const [selId, setSelId] = useState<string | null>(null);
  const [bankTab, setBankTab] = useState<string>("");
  const [playing, setPlaying] = useState(false);
  const [decisions, setDecisions] = useState<Record<string, "open" | "dismissed">>({});

  useEffect(() => {
    fetch("data.json")
      .then((r) => {
        if (!r.ok) throw new Error("no data");
        return r.json() as Promise<Data>;
      })
      .then((d) => {
        setData(d);
        setBankTab(d.banks[0]);
        const first = d.days.findIndex((x) => x.windows.length > 0);
        setDay(first >= 0 ? first : d.days.length - 1);
      })
      .catch(() => setError(true));
  }, []);

  const last = data ? data.days.length - 1 : 0;
  const goTo = useCallback(
    (i: number) => {
      if (!data) return;
      const n = Math.max(0, Math.min(last, i));
      setDay(n);
      setSelId((cur) => (cur && data.days[n].windows.some((w) => w.id === cur) ? cur : null));
    },
    [data, last],
  );

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setDay((d) => {
        if (d >= last) {
          setPlaying(false);
          return d;
        }
        return d + 1;
      });
    }, 900);
    return () => window.clearInterval(id);
  }, [playing, last]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") goTo(day + 1);
      if (e.key === "ArrowLeft") goTo(day - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [day, goTo]);

  const current = data?.days[day];
  const max = useMemo(() => {
    if (!data || !current) return 1;
    return Math.max(1, ...data.banks.flatMap((b) => current.banks[b].flat()), ...current.total.flat());
  }, [data, current]);
  const win: Win | null = current?.windows.find((w) => w.id === selId) ?? null;

  const header = (
    <header>
      <div>
        <h1>
          Out<em>break</em>
        </h1>
        <p className="lede">
          Three banks each see a thin slice of the same skimming pattern. Added together, the slices stand out. Pick a day, then a ringed window, to see which
          customers each bank raises.
        </p>
      </div>
      <div className="stamp" role="note">
        Demo view
        <br />
        Bank panels are shown in plain for illustration. The collector itself only ever holds masked vectors and their sums.
      </div>
    </header>
  );

  return (
    <div className="wrap">
      {header}
      {error && (
        <div id="err" style={{ display: "block" }}>
          data.json not found. Run `make demo-collector` (it writes outbreak/public/data.json), then `npm run dev` in outbreak/.
        </div>
      )}
      {data && current && (
        <main className="stage">
          <DayRail days={data.days} day={day} playing={playing} onSelect={goTo} onTogglePlay={() => setPlaying((p) => !p)} />
          <section aria-label="Heatmaps">
            <div className="sheet">
              {data.banks.map((b) => (
                <Heatmap key={b} title={b} grid={current.banks[b]} max={max} delayLabels={data.delay_labels} />
              ))}
              <Heatmap
                big
                title="Collector total"
                grid={current.total}
                max={max}
                delayLabels={data.delay_labels}
                windows={current.windows}
                selectedId={selId}
                onPick={(w) => {
                  setSelId(w.id);
                  setBankTab(data.banks[0]);
                }}
              />
            </div>
            {current.windows.length === 0 && <p className="quiet">Quiet day. Nothing flagged.</p>}
            <div className="legend" aria-hidden="true">
              <span>customers per cell</span>
              <span>0</span>
              <span className="ramp" />
              <span>{max}</span>
              <span style={{ marginLeft: 14 }}>
                <span className="key-win" /> flagged window
              </span>
            </div>
          </section>
          <Drawer
            day={current}
            win={win}
            banks={data.banks}
            delayLabels={data.delay_labels}
            bankTab={bankTab}
            onTab={setBankTab}
            decisions={decisions}
            onDecide={(k, d) => setDecisions((s) => ({ ...s, [k]: d }))}
          />
        </main>
      )}
      <footer>
        Skim bins are 1&nbsp;pp wide (vertical), delay bins are the six pre-agreed ranges (horizontal). A window is flagged by a space-time permutation test on
        the summed counts (Benjamini–Hochberg, q&nbsp;=&nbsp;0.01). Raised customers are leads for an analyst, never verdicts. Synthetic world; one round, no
        recursion.
      </footer>
    </div>
  );
}
