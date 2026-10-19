// Plain-English wording for the Case screen: signal groups, signal sentences, key numbers,
// innocent explanations, engine reasons and decision rejections. English only, short words.
import type { CaseDetail, Signal } from '../../types';

/* ------------------------------------------------------------------ number formatting */

const nf0 = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1 });

export const czk = (n: number) => `${nf0.format(n)} CZK`;
export const pct = (x: number) => `${nf0.format(x * 100)}%`;
export const int = (n: number) => nf0.format(n);
export const one = (n: number) => nf1.format(n);
export const hours = (h: number) => (h < 1 ? `${nf0.format(h * 60)} min` : `${nf1.format(h)} h`);
export const times = (x: number) => `${x >= 10 ? nf0.format(x) : nf1.format(x)}×`;

export const ROLE_PLAIN: Record<string, string> = {
  analyst_l1: 'first-line analyst',
  analyst_l2: 'senior analyst',
  aml_officer: 'AML officer',
  mlro: 'MLRO',
};
export const ROLE_WITH_ARTICLE: Record<string, string> = {
  analyst_l1: 'a first-line analyst',
  analyst_l2: 'a senior analyst',
  aml_officer: 'an AML officer',
  mlro: 'the MLRO',
};
export const ROLE_LABEL:Record<string, string> = { analyst_l1: 'Analyst L1', analyst_l2: 'Analyst L2', aml_officer: 'AML officer', mlro: 'MLRO' };

/* ------------------------------------------------------------------ signal groups */

export interface Group {
  key: string;
  title: string;
  ids: string[];
}

export const GROUPS: Group[] = [
  { key: 'victim', title: 'Looks like a scam victim', ids: ['VICTIM'] },
  { key: 'through', title: 'Money passes through quickly', ids: ['D1', 'R-C', 'D7'] },
  { key: 'profile', title: 'Account behaves unlike its profile', ids: ['R-A', 'D3', 'D2'] },
  { key: 'counterparties', title: 'Counterparties look unusual', ids: ['D4', 'D5', 'D6', 'X'] },
  { key: 'rules', title: 'Rules', ids: ['R-B', 'D8'] },
];

export function groupSignals(signals: Signal[]): { group: Group; items: Signal[] }[] {
  const out = GROUPS.map((g) => ({ group: g, items: signals.filter((s) => g.ids.includes(s.detector_id)).sort((a, b) => b.score - a.score) }));
  const known = new Set(GROUPS.flatMap((g) => g.ids));
  const rest = signals.filter((s) => !known.has(s.detector_id));
  if (rest.length) out.push({ group: { key: 'other', title: 'Other checks', ids: [] }, items: rest });
  return out.filter((g) => g.items.length);
}

/* ------------------------------------------------------------------ one plain sentence per signal */

export function signalSentence(s: Signal): string {
  switch (s.detector_id) {
    case 'R-A':
      return 'July payments broke the limits of the client’s own profile.';
    case 'R-B':
      return 'A payment involves a high-risk country, or a politically exposed person sent a large amount.';
    case 'R-C':
      return 'Over 100,000 CZK came in within a day and most of it left within 6 hours.';
    case 'D1':
      return 'Large payments come in and leave within hours, again and again, to rare accounts.';
    case 'D2':
      return 'A new account with almost no history got a large payment and was emptied within a day.';
    case 'D3':
      if (s.template.includes('spending')) return 'July volume is far above the client’s profile, driven mostly by money going out.';
      if (s.template.includes('inflow')) return 'July volume is far above the client’s profile, driven mostly by money coming in.';
      return 'July volume is far above the client’s profile, with money both coming in and going out.';
    case 'D4':
      return 'Many unrelated, never-seen-before senders paid in within a short time.';
    case 'D5':
      return 'Most money goes out to rare accounts, and it did not come from regular income.';
    case 'D6':
      return 'Other clients of this bank pay the same rare accounts, with the same timing and the same cut.';
    case 'D7':
      return 'The client keeps the same small cut of every payment and forwards the rest.';
    case 'D8':
      return 'Amounts pile up just below a threshold.';
    case 'X':
      return 'The accounts this client pays also receive money from clients of other banks.';
    case 'VICTIM':
      return 'The client is sending own savings to new rare accounts, with no large payment coming in.';
    default:
      return 'A detector raised this signal.';
  }
}

export interface Fact {
  label: string;
  value: string;
}

const RA_NOTES: Record<string, Fact> = {
  daily_gt_share_of_projected: { label: 'one day', value: 'above 25% of expected month' },
  daily_gt_mult_of_q2_avg: { label: 'one day', value: 'above 3× the Q2 daily average' },
  single_gt_mult_of_q2_max: { label: 'one payment', value: 'above 2× the Q2 largest' },
};

const KEY_LABEL: Record<string, string> = {
  july_total: 'July volume',
  expected_monthly: 'expected per month',
  inflow_share_of_volume: 'incoming share',
  share_rare: 'sent to rare accounts',
  recurring_income_share: 'from regular income',
  popular_inflow_share: 'from large payers',
  out_total: 'sent out',
  in_total: 'received',
  lag_median_h: 'typical delay',
  retention_median: 'typical cut',
  share_popular: 'to common payees',
  big_in_sender_degree: 'clients paid by the main payer',
  max_single_in: 'largest payment in',
  reciprocity_share: 'two-way volume',
  drained_24h_share: 'sent on within 24 h',
  n_senders: 'senders',
  n_senders_rare: 'rare senders',
  top_exit_share: 'to the largest payee',
  life_payment_share: 'payments to common payees',
  days_since_contract: 'client for',
};

/** Format a single evidence value with a human unit, guessed from its key. */
export function fmtEvidence(key: string, v: unknown): string | null {
  if (v === null || v === undefined) return null;
  if (Array.isArray(v)) {
    if (!v.length) return null;
    if (v.every((x) => typeof x === 'string')) return `${v.length} account${v.length === 1 ? '' : 's'}`;
    if (key === 'hour_hist') return null;
    const nums = v.filter((x): x is number => typeof x === 'number');
    if (/retention|share/.test(key)) return `${pct(nums.reduce((a, b) => a + b, 0) / nums.length)} avg`;
    return nums.map((n) => one(n)).join(', ');
  }
  if (typeof v === 'number') {
    if (/share|retention|rate/.test(key)) return pct(v);
    if (/_h$/.test(key)) return hours(v);
    if (/total|amount|expected|max_single|in_max|_czk/.test(key)) return czk(v);
    if (key === 'days_since_contract') return `${int(v)} days`;
    return one(v);
  }
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  return String(v);
}

function genericFacts(ev: Record<string, unknown>): Fact[] {
  const out: Fact[] = [];
  for (const [k, v] of Object.entries(ev)) {
    const val = fmtEvidence(k, v);
    if (val === null) continue;
    out.push({ label: KEY_LABEL[k] ?? k.replace(/_/g, ' '), value: val });
  }
  return out.slice(0, 3);
}

const noteVal = (notes: string[], k: string): string | undefined => notes.find((n) => n.startsWith(`${k}=`))?.slice(k.length + 1);

/** The 2-3 key evidence numbers of a signal, with units. */
export function signalFacts(s: Signal, c: CaseDetail): Fact[] {
  const ev = s.evidence as Record<string, unknown>;
  const n = (k: string) => (typeof ev[k] === 'number' ? (ev[k] as number) : typeof c.features[k] === 'number' ? (c.features[k] as number) : undefined);
  switch (s.detector_id) {
    case 'R-A': {
      const seen = new Set<string>();
      return s.notes
        .map((x) => RA_NOTES[x])
        .filter((f): f is Fact => !!f && !seen.has(f.value) && !!seen.add(f.value));
    }
    case 'D3': {
      const jt = n('july_total');
      const ex = n('expected_monthly');
      const out: Fact[] = [];
      if (jt !== undefined && ex) out.push({ label: 'July volume', value: `${times(jt / ex)} expected` });
      if (jt !== undefined) out.push({ label: 'July', value: czk(jt) });
      if (ex !== undefined) out.push({ label: 'expected', value: czk(ex) });
      return out;
    }
    case 'D7': {
      const r = (ev.cycle_retentions as number[] | undefined) ?? [];
      const out: Fact[] = [];
      if (r.length) {
        const avg = r.reduce((a, b) => a + b, 0) / r.length;
        const spread = Math.max(...r) - Math.min(...r);
        out.push({ label: 'cut kept', value: pct(avg) });
        out.push({ label: 'cycles', value: int(r.length) });
        out.push({ label: 'varies by', value: spread < 0.001 ? 'under 0.1 pp' : `${one(spread * 100)} pp` });
      } else out.push(...genericFacts(ev));
      return out;
    }
    case 'D6': {
      const out: Fact[] = [];
      const g = noteVal(s.notes, 'group_size');
      if (g) out.push({ label: 'clients alike', value: g });
      const lag = n('lag_median_h');
      if (lag !== undefined) out.push({ label: 'typical delay', value: hours(lag) });
      const ret = n('retention_median');
      if (ret !== undefined) out.push({ label: 'cut kept', value: pct(ret) });
      const lift = noteVal(s.notes, 'lift_vs_shuffled');
      if (lift && out.length < 3) out.push({ label: 'vs. chance', value: `${lift}× more alike` });
      return out.slice(0, 3);
    }
    case 'X': {
      if (!c.cluster) return [];
      return [
        { label: 'other accounts', value: int(c.cluster.n_other_candidates) },
        { label: 'other banks', value: int(c.cluster.n_other_banks) },
      ];
    }
    case 'VICTIM': {
      const out: Fact[] = [];
      const o = n('out_total');
      const i = n('in_total');
      const m = n('max_single_in');
      if (o !== undefined) out.push({ label: 'sent out', value: czk(o) });
      if (i !== undefined) out.push({ label: 'received', value: czk(i) });
      if (m !== undefined) out.push({ label: 'largest in', value: czk(m) });
      return out;
    }
    case 'D5': {
      const out: Fact[] = [];
      const sr = n('share_rare');
      const rr = n('recurring_income_share');
      const ot = n('out_total');
      if (sr !== undefined) out.push({ label: 'to rare accounts', value: pct(sr) });
      if (rr !== undefined) out.push({ label: 'from regular income', value: pct(rr) });
      if (ot !== undefined) out.push({ label: 'sent out', value: czk(ot) });
      return out;
    }
    default:
      return genericFacts(ev);
  }
}

/* ------------------------------------------------------------------ innocent explanations */

export const INNOCENT: Record<string, { means: string; notRuledOut: string; short: string }> = {
  E1: {
    means: 'Regular payments of the same amount to one person, paid from regular income. Looks like family support.',
    notRuledOut: 'A mule paid in regular instalments.',
    short: 'family support payments',
  },
  E2: {
    means: 'A real share of the money goes to shops, utilities and other common payees. Looks like ordinary life.',
    notRuledOut: 'A mule account that is also used for daily spending.',
    short: 'ordinary spending at shops and utilities',
  },
  E3: {
    means: 'The money going out came from regular income such as a salary.',
    notRuledOut: 'Salary-like payments set up by a recruiter.',
    short: 'regular income',
  },
  E4: {
    means: 'The payers are large institutions such as an employer, insurer or platform.',
    notRuledOut: 'An institutional payout being passed on to someone else.',
    short: 'payments from large institutions',
  },
  E5: {
    means: 'Money goes both ways with the same people, as with shared bills.',
    notRuledOut: 'Circular payments set up to look ordinary.',
    short: 'two-way payments with the same people',
  },
  E6: {
    means: 'An established account collects small sums and pays nearly all to one payee, as with a rent split or a collection.',
    notRuledOut: 'A collection account used to pool mule money.',
    short: 'a pooled one-off collection',
  },
  E7: {
    means: 'An established account forwards money to one host after a fixed fee, as with co-hosting.',
    notRuledOut: 'A mule taking a fixed commission.',
    short: 'a co-hosting arrangement',
  },
  E8: {
    means: 'Few payers, and the money is kept and spent in ordinary life, as for a freelancer.',
    notRuledOut: 'A freelancer recruited as a mule.',
    short: 'freelance-style earnings',
  },
};

/* ------------------------------------------------------------------ engine reasons */

export function proposalHeadline(c: CaseDetail): string {
  const role = ROLE_PLAIN[c.escalation.role] ?? c.escalation.role;
  if (c.route === 'victim_protection') return `REVIEW — victim protection, ${role}`;
  if (c.triage === 'FP') return `CLOSE as false positive — ${role} confirms`;
  return `REVIEW — escalate to ${role}`;
}

/** Collapse the engine's raw reason lines into 2-4 plain sentences. */
export function plainReasons(c: CaseDetail): string[] {
  const out: string[] = [];
  let unexplained = 0;
  const explainedBy = new Map<string, number>();
  const other: string[] = [];
  let prio: string | null = null;
  let cluster = false;
  let victim = false;
  for (const raw of c.triage_reasons) {
    const r = raw.replace(/^[A-Z0-9]+-R\d+:\s*/, '');
    let m: RegExpExecArray | null;
    if ((m = /^priority \d+ (>=|<) (\d+)/.exec(r))) {
      prio = m[1] === '>=' ? `Priority is at or above the auto-close limit of ${m[2]}.` : `Priority is below the auto-close limit of ${m[2]}.`;
    } else if (/unexplained$/.test(r)) unexplained++;
    else if ((m = /explained by ([A-Z0-9-]+):/.exec(r))) explainedBy.set(m[1], (explainedBy.get(m[1]) ?? 0) + 1);
    else if (/cluster/.test(r)) cluster = true;
    else if (/victim_protection/.test(r)) victim = true;
    else other.push(r.charAt(0).toUpperCase() + r.slice(1));
  }
  if (victim) out.push('It looks like the client is being scammed, so it goes to victim protection and is never closed automatically.');
  if (cluster) out.push('The client is part of a network seen at other banks, so the case is never closed automatically.');
  if (prio) out.push(prio);
  if (unexplained) out.push(unexplained === 1 ? '1 signal has no normal explanation.' : `${unexplained} signals have no normal explanation.`);
  for (const [e, n] of explainedBy) {
    out.push(`${n === 1 ? '1 signal is' : `${n} signals are`} explained by ${INNOCENT[e]?.short ?? 'normal activity'}.`);
  }
  out.push(...other);
  return out;
}

const MATRIX_ROW: Record<number, string> = {
  0: 'The client is a politically exposed person.',
  1: 'The client is in a cross-bank network and priority is 70 or more.',
  2: 'Priority is 70 or more.',
  3: 'Priority is 40 or more.',
  4: 'Standard case with lower priority.',
};

export function whyThisPerson(c: CaseDetail): string {
  const why = MATRIX_ROW[c.escalation.rule_index];
  return `${why ? `${why} ` : ''}The escalation matrix sends such cases to ${ROLE_WITH_ARTICLE[c.escalation.role] ?? c.escalation.role}.`;
}

/* ------------------------------------------------------------------ decision rejections */

export function violationSentence(code: string, ctx: { self: boolean; decider: string; role: string; target: string }): string {
  const who = ctx.self ? 'You are' : `${ctx.decider} is`;
  const whoDid = ctx.self ? 'You' : ctx.decider;
  switch (code) {
    case 'decider_is_relationship_owner':
      return `${who} the relationship owner of this client, so ${ctx.self ? 'you' : 'they'} cannot decide this case.`;
    case 'decider_is_rule_author':
      return `${whoDid} wrote the rule that raised this alert, so ${ctx.self ? 'you' : 'they'} cannot decide this case.`;
    case 'decider_is_first_triager':
      return `${whoDid} did the first review of this case. A different person must decide.`;
    case 'four_eyes_required':
      return 'This case needs a second person to approve. Pick an approver other than the decider.';
    case 'approver_is_executor':
      return 'The approver cannot be the person who decides.';
    case 'override_requires_written_reason':
    case 'override_reason_required':
      return 'Write a reason of at least 10 characters to override the proposal.';
    case 'role_below_escalation_target':
    case 'decider_role_below_escalation_target':
      return `This case needs ${ctx.target === 'MLRO' ? 'the MLRO' : `an ${ctx.target}`} or higher. The decider’s role is ${ctx.role}.`;
    case 'decider_missing':
      return 'Choose who decides.';
    case 'unknown_role':
      return 'The decider’s role is not known to the server.';
    case 'unknown_action':
      return 'Choose Confirm or Override.';
    default:
      return code.replace(/_/g, ' ');
  }
}

/* ------------------------------------------------------------------ fallback summary */

/** A plain summary computed from the case data, used only when the automatic summary cannot be written. */
export function factSummary(c: CaseDetail): { text: string; refs: string[] }[] {
  const f = c.features;
  const n = (k: string) => (typeof f[k] === 'number' ? (f[k] as number) : undefined);
  const out: { text: string; refs: string[] }[] = [];
  const inT = n('in_total');
  const outT = n('out_total');
  if (inT !== undefined && outT !== undefined)
    out.push({
      text: `In July the client received ${czk(inT)} from ${int(n('n_senders') ?? 0)} sender${n('n_senders') === 1 ? '' : 's'} and sent ${czk(outT)} to ${int(n('n_exits') ?? 0)} account${n('n_exits') === 1 ? '' : 's'}.`,
      refs: ['features.in_total'],
    });
  const sig = [...c.signals].sort((a, b) => b.score - a.score);
  if (sig.length) {
    const top = signalSentence(sig[0]);
    out.push({
      text: `The engine found ${sig.length} warning sign${sig.length === 1 ? '' : 's'}. Strongest: ${top}`,
      refs: [sig[0].signal_id],
    });
  }
  if (c.exculpatory.length) {
    const names = c.exculpatory.map((e) => INNOCENT[e.detector_id]?.short).filter(Boolean);
    out.push({ text: `Normal explanations found: ${names.join(', ')}.`, refs: c.exculpatory.map((e) => e.signal_id) });
  } else out.push({ text: 'No normal explanation was found.', refs: [] });
  if (c.cluster && sig[0]?.detector_id !== 'X')
    out.push({
      text: `The accounts this client pays are also used by ${int(c.cluster.n_other_candidates)} accounts at ${int(c.cluster.n_other_banks)} other banks.`,
      refs: ['cluster'],
    });
  return out;
}

export const NOT_TRIGGERED: Record<string, string> = {
  'R-C': 'Large sum in and out within hours (rule C)',
  D1: 'Repeated fast pass-through',
  D7: 'Same cut kept from every payment',
  'R-A': 'Daily volume above profile (rule A)',
  D3: 'Monthly volume far above profile',
  D2: 'New account emptied on day one',
  D4: 'Many new, unrelated senders',
  D5: 'Money out mostly to rare accounts',
  D6: 'Same pattern as other clients',
  X: 'Accounts shared with other banks',
  'R-B': 'High-risk country or PEP payment (rule B)',
  D8: 'Amounts just below a threshold',
};
