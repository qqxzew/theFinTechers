// "Ask about a rule": a collapsed row that opens a grounded question box.
import { useState } from 'react';
import { askCase } from '../../api';
import type { AskResponse } from '../../types';
import { Button } from '../ui';
import { useElapsed } from './Brief';
import { CitedSentences, violationText } from './refs';

const SUGGESTED = ['Which thresholds did this case cross?', 'Why is the strongest warning sign so strong?', 'What would have to be true to close this case?'];

export default function AskRule({ caseId }: { caseId: string }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [asked, setAsked] = useState('');
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<AskResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const elapsed = useElapsed(busy);

  const ask = async (question: string) => {
    const qq = question.trim();
    if (!qq || busy) return;
    setQ(qq);
    setAsked(qq);
    setBusy(true);
    setRes(null);
    setErr(null);
    try {
      setRes(await askCase(caseId, qq));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card px-6 py-4" aria-label="Ask about a rule">
      <button type="button" className="flex w-full items-baseline justify-between gap-4 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span>
          <span className="text-[15px] font-semibold text-ink">Ask about a rule</span>
          <span className="ml-3 text-[14px] text-muted">Questions are answered only from this case and the bank’s rule settings.</span>
        </span>
        <span className="text-[13px] text-accent">{open ? 'Close' : 'Open'}</span>
      </button>
      {open && (
        <div className="mt-4 space-y-3">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void ask(q);
            }}
          >
            <label htmlFor="ask-q" className="sr-only">
              Your question
            </label>
            <input id="ask-q" className="input min-w-0 flex-1" placeholder="For example: what does rule A measure?" value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} />
            <Button variant="primary" disabled={busy || !q.trim()}>
              Ask
            </Button>
          </form>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {SUGGESTED.map((s) => (
              <button key={s} type="button" className="text-[13px] text-muted underline-offset-4 hover:text-ink hover:underline" disabled={busy} onClick={() => void ask(s)}>
                {s}
              </button>
            ))}
          </div>
          <div aria-live="polite">
            {busy && (
              <p role="status" className="text-[13px] text-muted">
                Looking it up… <span className="tnum">{elapsed} s</span> <span className="text-faint">(can take up to a minute)</span>
              </p>
            )}
            {err && <p className="text-[13px] text-amber">The question could not be answered right now.</p>}
            {res && (
              <div className="space-y-2 pt-1">
                <p className="text-[13px] text-muted">“{asked}”</p>
                {res.answer?.length ? <CitedSentences items={res.answer} className="max-w-[80ch]" /> : <p className="text-[14px] text-muted">No answer.</p>}
                {res.violations?.length ? (
                  <div className="text-[13px] text-muted">
                    <p>Some statements could not be verified:</p>
                    <ul className="mt-1 space-y-0.5 pl-3">
                      {res.violations.map((v, i) => (
                        <li key={i}>{violationText(v)}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="text-[13px] text-muted">Every statement was checked against the case.</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
