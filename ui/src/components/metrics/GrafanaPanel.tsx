import { useEffect, useState, type ReactNode } from 'react';
import { grafanaPanelUrl, grafanaReachable } from '../../api';

/** null while checking, then true/false. Checked once per mount of the screen. */
export function useGrafanaUp(): boolean | null {
  const [up, setUp] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    grafanaReachable().then((ok) => alive && setUp(ok));
    return () => {
      alive = false;
    };
  }, []);
  return up;
}

/** Grafana's own panel title row is cropped off; our heading above the chart replaces it. */
const TITLE_ROW_PX = 58;

/**
 * One embedded Grafana panel: our plain title, a one-line "how to read", the chart in a
 * fixed-ratio shadowed frame, and one computed takeaway sentence.
 */
export function GrafanaPanel({
  panelId,
  title,
  howToRead,
  takeaway,
  up,
  ratio = '16 / 7',
}: {
  panelId: number;
  title: string;
  howToRead: ReactNode;
  takeaway?: ReactNode;
  up: boolean | null;
  ratio?: string;
}) {
  return (
    <figure className="min-w-0 space-y-3">
      <div>
        <h3 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h3>
        <p className="mt-0.5 text-[13px] text-muted">{howToRead}</p>
      </div>
      <div className="card relative overflow-hidden" style={{ aspectRatio: ratio }}>
        {up === null ? (
          <div className="absolute inset-0 animate-pulse bg-sunken/50" aria-label="Loading chart" />
        ) : up ? (
          <iframe
            title={title}
            src={grafanaPanelUrl(panelId)}
            className="absolute left-0 w-full"
            style={{ top: -TITLE_ROW_PX, height: `calc(100% + ${TITLE_ROW_PX}px)`, border: 0 }}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-sunken/40 px-6 text-center text-[13px] text-muted">
            Charts unavailable: Grafana is not running.
          </div>
        )}
      </div>
      {takeaway && <figcaption className="max-w-3xl text-[14px] leading-snug text-ink">{takeaway}</figcaption>}
    </figure>
  );
}
