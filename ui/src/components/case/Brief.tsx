// "In brief": the short auto-written summary with clickable evidence refs.
import { useEffect, useState } from 'react';
import { writeBrief, type CaseBrief } from '../../api';
import type { CaseDetail } from '../../types';
import { Button, Card } from '../ui';
import { CitedSentences, violationText } from './refs';
import { factSummary } from './text';

export function useElapsed(running: boolean) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    setS(0);
    const start = Date.now();
    const h = window.setInterval(() => setS(Math.floor((Date.now() - start) / 1000)), 500);
    return () => window.clearInterval(h);
  }, [running]);
  return s;
}

export function Unverified({ items }: { items: (Record<string, unknown> | string)[] }) {
  if (!items.length) return null;
  return (
    <details className="group mt-4 text-[13px] text-muted">
      <summary className="cursor-pointer list-none hover:text-ink">
        Some statements could not be verified <span className="text-faint group-open:hidden">· show</span>
      </summary>
      <ul className="mt-2 space-y-1 pl-3">
        {items.map((v, i) => (
          <li key={i}>{violationText(v)}</li>
        ))}
      </ul>
    </details>
  );
}

export default function Brief({ data }: { data: CaseDetail & { brief?: CaseBrief | null } }) {
  const [brief, setBrief] = useState<CaseBrief | null>(data.brief ?? null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);
  const elapsed = useElapsed(busy);

  const run = () => {
    setBusy(true);
    setErr(false);
    writeBrief(data.case_id)
      .then((b) => setBrief(b))
      .catch(() => setErr(true))
      .finally(() => setBusy(false));
  };
  useEffect(() => {
    setBrief(data.brief ?? null);
    if (!data.brief) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.case_id]);

  return (
    <Card title="In brief" sub="An automatic summary. Each number points to its evidence below." className="h-full">
      {brief && brief.sentences.length > 0 ? (
        <>
          <CitedSentences items={brief.sentences} size="text-[18px]" className="max-w-[62ch] space-y-0" />
          <Unverified items={brief.violations ?? []} />
        </>
      ) : busy ? (
        <div role="status" aria-live="polite" className="space-y-3">
          <div className="h-4 w-11/12 animate-pulse rounded bg-sunken" />
          <div className="h-4 w-10/12 animate-pulse rounded bg-sunken" />
          <div className="h-4 w-8/12 animate-pulse rounded bg-sunken" />
          <p className="pt-1 text-[13px] text-muted">
            Writing summary… <span className="tnum">{elapsed} s</span>
          </p>
        </div>
      ) : err ? (
        <>
          <CitedSentences items={factSummary(data)} size="text-[18px]" className="max-w-[62ch]" />
          <p className="mt-4 text-[13px] text-muted">
            The automatic summary could not be written, so these are the key facts from the data.{' '}
            <Button variant="quiet" className="!px-1.5 !py-0.5 text-[13px]" onClick={run}>
              Try again
            </Button>
          </p>
        </>
      ) : (
        <p className="text-[14px] text-muted">No summary for this case.</p>
      )}
    </Card>
  );
}
