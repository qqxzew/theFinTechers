// The analyst's decision: confirm or override the engine proposal. Decider and approver fields
// appear only when needed; server rejections are shown as plain sentences.
import { useEffect, useState, type FormEvent } from 'react';
import { postDecision } from '../../api';
import { STAFF, useApp } from '../../state';
import type { CaseDetail } from '../../types';
import { Button, ErrorBox } from '../ui';
import { ROLE_LABEL, violationSentence } from './text';

const ROLES = ['analyst_l1', 'analyst_l2', 'aml_officer', 'mlro'];

export default function Decision({ data, onDone }: { data: CaseDetail; onDone: () => void }) {
  const { identity, meta } = useApp();
  const [action, setAction] = useState<'confirm' | 'override'>('confirm');
  const [reason, setReason] = useState('');
  const [decider, setDecider] = useState(identity.name);
  const [role, setRole] = useState(identity.role);
  const [approver, setApprover] = useState('');
  const [changeWho, setChangeWho] = useState(false);
  const [busy, setBusy] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setDecider(identity.name);
    setRole(identity.role);
  }, [identity]);
  useEffect(() => setViolations(null), [action, decider, role, approver]);

  const minP = meta?.four_eyes_min_priority ?? 70;
  const fourEyes = data.priority >= minP;
  const staff = meta?.staff?.length ? meta.staff : STAFF.map((s) => s.name);
  const proposal = data.triage === 'FP' ? 'close' : 'review';
  const opposite = data.triage === 'FP' ? 'review' : 'close';
  const reasonShort = action === 'override' && reason.trim().length < 10;
  const canSubmit = !busy && !!decider && !reasonShort && (!fourEyes || !!approver);

  if (data.decision) {
    const d = data.decision;
    return (
      <div>
        <p className="label">Decision</p>
        <p className="mt-1 text-[19px] font-semibold tracking-tight text-ink">
          {d.action === 'confirm' ? 'Proposal confirmed' : 'Proposal overridden'}
        </p>
        <p className="mt-1 text-sm text-muted">
          by {d.decider} · {ROLE_LABEL[d.role] ?? d.role}
          {d.approver ? ` · approved by ${d.approver}` : ''} · {new Date(d.ts).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })}
        </p>
        {d.reason && <p className="mt-3 whitespace-pre-wrap text-[15px] text-ink">“{d.reason}”</p>}
      </div>
    );
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setErr(null);
    setViolations(null);
    try {
      const r = await postDecision(data.case_id, { action, decider, role, reason: reason.trim(), approver: approver || null });
      if (r.ok) onDone();
      else setViolations(r.violations ?? []);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  };

  const seg = (a: 'confirm' | 'override', label: string) => (
    <button
      type="button"
      onClick={() => setAction(a)}
      aria-pressed={action === a}
      className={`flex-1 rounded-md px-3 py-1.5 text-sm transition-[box-shadow,background-color] ${
        action === a ? 'bg-surface font-semibold text-ink shadow-rest' : 'font-medium text-muted hover:text-ink'
      }`}
    >
      {label}
    </button>
  );

  const ctx = { self: decider === identity.name, decider, role: ROLE_LABEL[role] ?? role, target: ROLE_LABEL[data.escalation.role] ?? data.escalation.role };

  return (
    <form onSubmit={submit} className="space-y-3" aria-label="Your decision">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[15px] font-semibold text-ink">Your decision</p>
        <p className="text-[13px] text-muted">
          as <span className="font-medium text-ink">{decider}</span> · {ROLE_LABEL[role] ?? role}{' '}
          <button type="button" className="ml-1 text-accent underline-offset-2 hover:underline" onClick={() => setChangeWho((v) => !v)}>
            {changeWho ? 'done' : 'change'}
          </button>
        </p>
      </div>

      <div className="flex gap-1 rounded-lg bg-sunken p-1" role="group" aria-label="Confirm or override">
        {seg('confirm', `Confirm ${proposal}`)}
        {seg('override', `Override to ${opposite}`)}
      </div>

      <div>
        <label htmlFor="d-reason" className="label">
          {action === 'override' ? 'Why you disagree (required, 10 characters or more)' : 'Note (optional)'}
        </label>
        <textarea
          id="d-reason"
          rows={action === 'override' ? 3 : 2}
          className="input mt-1 w-full resize-y"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          aria-required={action === 'override'}
          aria-invalid={reasonShort && reason.length > 0}
          placeholder={action === 'override' ? 'What did the engine miss?' : 'Anything the next reader should know'}
        />
      </div>

      {(changeWho || fourEyes) && (
        <div className="grid grid-cols-2 gap-3">
          {changeWho && (
            <>
              <label className="flex flex-col gap-1">
                <span className="label">Decider</span>
                <select className="input" value={decider} onChange={(e) => setDecider(e.target.value)}>
                  {[...new Set([identity.name, ...staff])].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                <span className="label">Role</span>
                <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
                  {(meta?.roles ?? ROLES).map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABEL[r] ?? r}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          {fourEyes && (
            <label className="col-span-2 flex flex-col gap-1">
              <span className="label">Second approver (needed from priority {minP})</span>
              <select className="input" value={approver} onChange={(e) => setApprover(e.target.value)}>
                <option value="">Choose a person</option>
                {staff
                  .filter((s) => s !== decider)
                  .map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
              </select>
            </label>
          )}
        </div>
      )}

      {violations && (
        <div role="alert" className="rounded-lg bg-ambersoft px-3 py-2.5 text-sm">
          <p className="font-semibold text-amber">The decision was not saved.</p>
          <ul className="mt-1 space-y-1 text-ink">
            {(violations.length ? violations : ['']).map((v) => (
              <li key={v}>{v ? violationSentence(v, ctx) : 'The server refused the decision.'}</li>
            ))}
          </ul>
        </div>
      )}
      {err && <ErrorBox error={err} message="Could not send the decision." />}

      <div className="flex items-center gap-3">
        <Button variant="primary" type="submit" disabled={!canSubmit}>
          {busy ? 'Saving…' : action === 'confirm' ? 'Confirm proposal' : 'Override proposal'}
        </Button>
        {fourEyes && !approver && <span className="text-[13px] text-muted">Choose an approver first.</span>}
        {!fourEyes && reasonShort && <span className="text-[13px] text-muted">Add a reason to override.</span>}
      </div>
    </form>
  );
}
