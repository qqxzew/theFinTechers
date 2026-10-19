/*
 * Plain-language derivations for the Results (Metrics) screen. Everything here is computed
 * from /api/metrics; nothing is hard-coded except the wording and the name dictionaries.
 */
import type { MetricsResponse, WeakRun } from '../../types';

export type ModeKey = 'isolated' | 'staj_psi' | 'naive_raw_sharing';

export interface HeadlineMode {
  precision: number;
  recall: number;
  f1?: number;
  raw_records_exposed: number;
  bytes_exchanged: number;
}
export type Headline = Partial<Record<ModeKey, HeadlineMode>>;

export interface CurvePoint {
  tp: number;
  fp: number;
  fn: number;
  precision: number;
  recall: number;
}
export type Curve = Partial<Record<ModeKey, Record<string, CurvePoint>>>;

export interface FailureRow {
  client_id: string;
  label?: string;
  scheme?: string | null;
  persona?: string | null;
  priority?: number;
  triage?: string;
  signals?: string[];
  exculpatory?: string[];
  reasons?: string[];
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export const pct0 = (v: number) => `${Math.round(v * 100)} %`;
export const int = (v: number) => Math.round(v).toLocaleString('en-US');
/** Means over test worlds can be x.5; show one decimal only when needed. */
export const count = (v: number) => (Math.abs(v - Math.round(v)) < 0.05 ? int(v) : v.toFixed(1));

export function headline(d: MetricsResponse): Headline | null {
  const h = d.headline_held_out_mean as Headline | undefined;
  return h && h.staj_psi && isNum(h.staj_psi.recall) ? h : null;
}

export function curve(d: MetricsResponse): Curve | null {
  const c = d.threshold_curve_held_out_mean as Curve | undefined;
  return c && c.staj_psi ? c : null;
}

export function heldOutCount(d: MetricsResponse): number {
  const s = (d as unknown as { held_out_seeds?: unknown[] }).held_out_seeds;
  return Array.isArray(s) ? s.length : 0;
}

/** Operating-point point of the threshold curve (exact key, else the closest one). */
export function atThreshold(c: Curve, mode: ModeKey, t: number): CurvePoint | null {
  const m = c[mode];
  if (!m) return null;
  if (m[String(t)]) return m[String(t)];
  const keys = Object.keys(m).map(Number).filter(isNum).sort((a, b) => a - b);
  const k = keys.find((x) => x >= t) ?? keys[keys.length - 1];
  return k === undefined ? null : m[String(k)];
}

/* ------------------------------------------------------------------ names */

const SCHEME: Record<string, string> = {
  day_zero: 'Day-zero account',
  same_hand: 'Same hand',
  same_hand_stealth: 'Same hand, stealthy',
  ghost_ring: 'Hidden cross-bank ring',
  invoice_mule: 'Invoice mule',
  fixed_skim: 'Fixed skim',
};
const PERSONA: Record<string, string> = {
  freelancer: 'Freelancer',
  students_rent: 'Students splitting rent',
  fundraiser: 'Fundraiser',
  second_hand_seller: 'Second-hand seller',
  group_collection: 'Group collection',
  migrant_remit: 'Migrant sending money home',
  middleman_cohost: 'Co-host middleman',
};
const humanize = (s: string) => s.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
export const schemeName = (s?: string | null) => (s ? SCHEME[s] ?? humanize(s) : 'Unknown scheme');
export const personaName = (s?: string | null) => (s ? PERSONA[s] ?? humanize(s) : '');

const SIGNAL: Record<string, string> = {
  'R-A': 'volume far above its profile',
  'R-B': 'a payment linked to a high-risk country',
  'R-C': 'money passed straight through',
  D1: 'fast pass-through of money',
  D2: 'a new account drained within a day',
  D3: 'volume three times its profile',
  D4: 'many new, unrelated senders',
  D5: 'money sent on to rarely used accounts',
  D6: 'behaving like other accounts run by the same hand',
  D7: 'a fixed cut kept from every inflow',
  D8: 'amounts just below a reporting threshold',
  X: 'a link to suspects at other banks',
};
const detector = (sig: string) => sig.split(':')[0];
const signalText = (d: string) => SIGNAL[d] ?? d;

function joinPlain(xs: string[]): string {
  if (xs.length <= 1) return xs[0] ?? '';
  return `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`;
}

/** Detector ids whose signal was left unexplained, read from the server's reasons. */
function unexplained(r: FailureRow): string[] {
  const out: string[] = [];
  for (const line of r.reasons ?? []) {
    const m = line.match(/:\s*([A-Z0-9-]+):[^\s]+ unexplained/);
    if (m) out.push(m[1]);
  }
  if (!out.length && r.signals?.length && !r.exculpatory?.length) out.push(...r.signals.map(detector));
  return [...new Set(out)];
}

export function whoIs(r: FailureRow): string {
  if (r.label === 'honest' && r.persona) return `Honest ${personaName(r.persona).toLowerCase()}`;
  if (r.label === 'victim') return 'Scam victim';
  if (r.label === 'mule') return schemeName(r.scheme);
  return 'Ordinary account';
}

export function whyFalseAlarm(r: FailureRow): string {
  const u = unexplained(r).map(signalText);
  if (!u.length) return 'Each signal had an innocent explanation, but together they still passed the cut-off.';
  const s = joinPlain(u);
  return `${s.charAt(0).toUpperCase()}${s.slice(1)}, with no innocent explanation found.`;
}

export function whyMissed(r: FailureRow, minPriority: number): string {
  if (!r.signals?.length) return 'No detector fired on this account.';
  if (r.triage && r.triage !== 'REVIEW') return 'Signals fired but were explained away as normal behaviour.';
  if (isNum(r.priority) && r.priority < minPriority) return `Priority ${r.priority} stayed below the cut-off of ${minPriority}.`;
  return 'Not routed to mule review.';
}

/* ------------------------------------------------------------------ takeaways */

export function thresholdTakeaway(c: Curve, t: number): string | null {
  const s = atThreshold(c, 'staj_psi', t);
  const i = atThreshold(c, 'isolated', t);
  if (!s || !i) return null;
  const keys = Object.keys(c.staj_psi ?? {}).map(Number).filter((k) => k > t).sort((a, b) => a - b);
  const next = keys.length ? c.staj_psi![String(keys[0])] : null;
  let txt = `At the cut-off of ${t}, Stáj finds ${pct0(s.recall)} of planted mules; banks alone find ${pct0(i.recall)}.`;
  if (next && next.fp < s.fp) txt += ` Raising it to ${keys[0]} removes ${next.fp === 0 ? 'all' : 'some'} false alarms but finds only ${pct0(next.recall)}.`;
  return txt;
}

type Bd = MetricsResponse['breakdown'][string];
function group(d: MetricsResponse, prefix: string): [string, Bd][] {
  return Object.entries(d.breakdown ?? {})
    .filter(([k]) => k.startsWith(`${prefix}:`))
    .map(([k, v]) => [k.slice(prefix.length + 1), v] as [string, Bd]);
}

export function breakdownTakeaway(d: MetricsResponse): string | null {
  const sch = group(d, 'scheme');
  const per = group(d, 'persona');
  const vic = group(d, 'victim');
  if (!sch.length && !per.length) return null;
  const parts: string[] = [];
  const full = sch.filter(([, v]) => v.flagged_as_mule_case >= v.n);
  if (sch.length) {
    if (full.length === sch.length) parts.push(`All ${sch.length} planted mule schemes are found in full.`);
    else {
      const worst = [...sch].sort((a, b) => a[1].rate - b[1].rate)[0];
      parts.push(`${full.length} of ${sch.length} schemes are found in full; the weakest is ${schemeName(worst[0]).toLowerCase()} (${worst[1].flagged_as_mule_case} of ${worst[1].n}).`);
    }
  }
  if (per.length) {
    const bad = per.filter(([, v]) => v.flagged_as_mule_case > 0);
    if (!bad.length) parts.push(`None of the ${per.length} kinds of honest look-alikes is flagged.`);
    else
      parts.push(
        `Of ${per.length} kinds of honest look-alikes, only ${joinPlain(bad.map(([k, v]) => `the ${personaName(k).toLowerCase()} group (${v.flagged_as_mule_case} of ${v.n})`))} ${bad.length === 1 ? 'raises' : 'raise'} false alarms.`,
      );
  }
  const v = vic.reduce((a, [, x]) => ({ n: a.n + x.n, r: a.r + x.routed_to_victim_protection }), { n: 0, r: 0 });
  if (v.n) parts.push(`${v.r} of ${v.n} scam victims go to victim protection, not mule review.`);
  return parts.join(' ');
}

export interface PrivacyPoint {
  variant: string;
  label: string;
  share: number | null;
  tokens: number;
  ringFound: number;
}

/** Held-out mean per export setting: exported tokens and share of worlds where the hidden ring was found. */
export function privacySweep(d: MetricsResponse): PrivacyPoint[] {
  const ho = d.weak_evidence_experiment?.held_out;
  if (!ho) return [];
  const seeds = Object.values(ho);
  if (!seeds.length) return [];
  const variants = Object.keys(seeds[0]).filter((v) => v === 'baseline' || v.startsWith('weak_'));
  return variants
    .map((v) => {
      const runs = seeds.map((s) => s[v]).filter(Boolean) as WeakRun[];
      const share = v.startsWith('weak_') ? Number(v.slice(5)) : null;
      return {
        variant: v,
        label: share === null ? 'strong suspects only' : `${Math.round(share * 100)} %`,
        share,
        tokens: runs.reduce((a, r) => a + r.exported_tokens, 0) / runs.length,
        ringFound: runs.reduce((a, r) => a + (r.staj_psi.ghost_recall ?? 0), 0) / runs.length,
      };
    })
    .sort((a, b) => (a.share ?? -1) - (b.share ?? -1));
}

export function privacyTakeaway(pts: PrivacyPoint[]): string | null {
  if (!pts.length) return null;
  const base = pts.find((p) => p.share === null);
  const best = [...pts].sort((a, b) => b.ringFound - a.ringFound || a.tokens - b.tokens)[0];
  if (!best || best.ringFound === 0) return 'The hidden ring is not found at any export setting.';
  let s = `Also exporting the weakest ${best.label} of accounts (${int(best.tokens)} blinded tokens${base ? ` instead of ${int(base.tokens)}` : ''}) finds the hidden ring in ${pct0(best.ringFound)} of test worlds`;
  const lost = pts.find((p) => (p.share ?? -1) > (best.share ?? -1) && p.ringFound < best.ringFound);
  if (lost) s += `; at ${lost.label} and above it is lost again`;
  if (base && base.ringFound < best.ringFound) s += `. Without this, it is ${base.ringFound === 0 ? 'never' : `found in only ${pct0(base.ringFound)} of worlds`}`;
  return `${s}.`;
}
