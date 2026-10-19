import { evidenceKey } from '../../api';
import type { CaseDetail, Sentence } from '../../types';

export interface SourceEntry {
  n: number;
  key: string;
  label: string;
  meaning: string;
  detail: string[];
}

const NAMESPACE: Record<string, string> = {
  features: 'Measured facts about this account',
  cluster: 'Cross-bank match from the radar',
  case: 'Checks made on this case',
  timeline: 'Transaction timeline',
  triage_reasons: 'Why the case was sent to review',
};

/** Strip the "D1 flow-through+: " prefix from a rule definition, keeping the explanation. */
const tail = (s: string) => {
  const i = s.indexOf(': ');
  return i > 0 && i < 40 ? s.slice(i + 2) : s;
};

/**
 * Number the distinct evidence keys of section V in order of first appearance.
 * Signal ids stay as their own entry; dotted refs (features.x, cluster.y) are grouped per namespace.
 */
export function buildSources(sentences: Sentence[], c: CaseDetail | null): { sources: SourceEntry[]; numOf: Map<string, number> } {
  const numOf = new Map<string, number>();
  const sources: SourceEntry[] = [];
  for (const s of sentences) {
    for (const r of s.refs) {
      const key = evidenceKey(r);
      let entry = sources.find((x) => x.key === key);
      if (!entry) {
        const det = key.includes(':') ? key.split(':')[0] : '';
        const def = det ? c?.rule_definitions?.[det] : undefined;
        const sig = det ? [...(c?.signals ?? []), ...(c?.exculpatory ?? [])].find((x) => x.signal_id === key) : undefined;
        entry = {
          n: sources.length + 1,
          key,
          label: key.includes(':') ? key : NAMESPACE[key] ?? key,
          meaning: def ? tail(def) : sig?.source ?? (key.includes(':') ? 'Detector signal on this case' : ''),
          detail: [],
        };
        sources.push(entry);
        numOf.set(key, entry.n);
      }
      if (!r.includes(':') && r.includes('.') && key !== 'triage_reasons') {
        const field = r.slice(r.indexOf('.') + 1);
        if (!entry.detail.includes(field)) entry.detail.push(field);
      }
    }
  }
  return { sources, numOf };
}

/** Numbers (sorted, unique) to print after a sentence. */
export function sentenceNumbers(s: Sentence, numOf: Map<string, number>): number[] {
  return [...new Set(s.refs.map((r) => numOf.get(evidenceKey(r))).filter((n): n is number => !!n))].sort((a, b) => a - b);
}

/** Sentence index a server QA finding points at, if any. */
export function violationIndex(v: Record<string, unknown>): number | null {
  for (const k of ['sentence_index', 'index', 'idx', 'sentence', 'i']) {
    const x = v[k];
    if (typeof x === 'number' && Number.isInteger(x)) return x;
  }
  return null;
}

/** One plain line for a QA finding. */
export function violationText(v: Record<string, unknown>): string {
  const detail = v.detail ?? v.message ?? v.reason;
  const check = v.check ?? v.kind ?? v.code ?? v.type;
  const parts = [typeof check === 'string' ? check.replace(/_/g, ' ') : null, typeof detail === 'string' ? detail : null].filter(Boolean);
  return parts.length ? parts.join(': ') : JSON.stringify(v);
}
