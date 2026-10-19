/* Plain-English "why" for a queue row, from its detector ids. */
import type { QueueItem } from '../../types';

/** Scoring weights from config/thresholds.yaml (cases.weights.points): the order in which signals count most. */
const WEIGHT: Record<string, number> = { D2: 3.5, D1: 3, D6: 3, D7: 3, X: 2.5, D4: 2, D5: 2, 'R-C': 2, D8: 1.5, D3: 1, 'R-B': 1, 'R-A': 0.5 };

const PHRASE: Record<string, string> = {
  D1: 'money passes through within hours',
  D2: 'new account drains a large inflow in a day',
  D3: 'volume far above profile',
  D4: 'many new senders at once',
  D5: 'pays almost only to rare accounts',
  D6: 'behaves like other own clients',
  D7: 'keeps a fixed cut of each payment',
  D8: 'amounts kept just below a threshold',
  'R-A': 'volume above profile',
  'R-B': 'high-risk country or PEP',
  'R-C': 'large inflow forwarded within hours',
  X: 'shares exit accounts with other banks',
  VICTIM: 'possible victim: drains own savings',
};

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function whyText(it: QueueItem): string {
  if (it.route === 'victim_protection') return 'Victim protection';
  // R-A and D3 say the same thing; keep the stronger one.
  const rules = it.rules.includes('D3') ? it.rules.filter((r) => r !== 'R-A') : it.rules;
  const top = rules
    .filter((r) => PHRASE[r])
    .sort((a, b) => (WEIGHT[b] ?? 0) - (WEIGHT[a] ?? 0))
    .slice(0, 2)
    .map((r) => PHRASE[r]);
  if (!top.length) return 'Unusual activity';
  return `${cap(top.join(', '))}.`;
}

export const ROLE_WORDS: Record<string, string> = {
  analyst_l1: 'Analyst',
  analyst_l2: 'Senior analyst',
  aml_officer: 'AML officer',
  mlro: 'MLRO',
};
export const roleWords = (r: string) => ROLE_WORDS[r] ?? r.replace(/_/g, ' ');
