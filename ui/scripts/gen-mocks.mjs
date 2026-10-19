// Generates MOCK JSON files in public/mock/ for UI development without the backend.
// Every number here is MOCK and invented for layout purposes only. Run: node scripts/gen-mocks.mjs
import { createHash } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'mock');
mkdirSync(OUT, { recursive: true });
const write = (name, obj) =>
  writeFileSync(join(OUT, name), typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2), 'utf8');

// deterministic PRNG
let s = 20261019;
const rnd = () => {
  s |= 0; s = (s + 0x6d2b79f5) | 0;
  let t = Math.imul(s ^ (s >>> 15), 1 | s);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const pick = (a) => a[Math.floor(rnd() * a.length)];
const int = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const hex = (n) => Array.from({ length: n }, () => Math.floor(rnd() * 16).toString(16)).join('');
const cref = () => 'c-' + hex(8);
const sha = (x) => createHash('sha256').update(x).digest('hex');

// ---------------------------------------------------------------- meta
write('meta.json', {
  data_label: 'SYNTHETIC',
  fx_placeholder: true,
  matrix_placeholder: true,
  models: {
    agent_primary: 'eu.anthropic.claude-sonnet-4-5',
    fallback: 'eu.anthropic.claude-haiku-4-5',
    bulk: 'eu.anthropic.claude-haiku-4-5',
    active: { agent_primary: 'eu.anthropic.claude-sonnet-4-5' },
  },
  chain: { ok: true, length: 0, head: '' }, // filled below
  roles: ['analyst_l1', 'analyst_l2', 'aml_officer', 'mlro'],
  four_eyes_min_priority: 70,
});

// ---------------------------------------------------------------- shared definitions
const RULE_DEFS = {
  'R-A': 'Rule A (CNB pilot): inflow followed by >= 80 % outflow within 48 h, aggregated per unit.',
  'R-B': 'Rule B (CNB pilot): first incoming payment above 50 000 CZK within 30 days of account opening.',
  'R-C': 'Rule C (CNB pilot): monthly turnover exceeds 3x declared income.',
  D1: 'D1 flow-through: money passes through with low retention and short lag.',
  D2: 'D2 day-zero: activity starts within days of contract opening.',
  D3: 'D3 profile gap: volume far above declared profile.',
  D4: 'D4 fan-in: many rare senders to one account.',
  D5: 'D5 rare exit: outflows go to counterparties rarely seen in the bank.',
  D6: 'D6 same hand: timing/retention fingerprint shared with other candidates.',
  D7: 'D7 fixed skim: constant retained share per cycle.',
  D8: 'D8 structuring: outgoing amounts cluster just below a threshold.',
  X: 'X cross-bank cluster: blinded-token overlap with candidates in other banks (disclosed only if >= 2 banks and >= 3 candidates).',
};
const RULES_POOL = ['R-A', 'R-B', 'R-C', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8'];
const ROLE_FOR = (p, pep) => (pep ? 'mlro' : p >= 85 ? 'mlro' : p >= 70 ? 'aml_officer' : p >= 40 ? 'analyst_l2' : 'analyst_l1');

const SRC = {
  D1: 'node/detectors/d1_flow_through.py@1.2 · config/thresholds.yaml#d1',
  D2: 'node/detectors/d2_day_zero.py@1.0 · config/thresholds.yaml#d2',
  D3: 'node/detectors/d3_profile_gap.py@1.1 · config/thresholds.yaml#d3',
  D4: 'node/detectors/d4_fan_in.py@1.0 · config/thresholds.yaml#d4',
  D5: 'node/detectors/d5_rare_exit.py@1.3 · config/thresholds.yaml#d5',
  D6: 'node/detectors/d6_same_hand.py@0.9 · radar/clustering.py',
  D7: 'node/detectors/d7_fixed_skim.py@1.0 · config/thresholds.yaml#d7',
  D8: 'node/detectors/d8_structuring.py@1.0 · config/thresholds.yaml#d8',
  E1: 'node/innocence/e1_mom.py@1.1 · config/thresholds.yaml#e1',
  E2: 'node/innocence/e2_life.py@1.0',
  E3: 'node/innocence/e3_source.py@1.0',
  E5: 'node/innocence/e5_reciprocity.py@1.0',
  VICTIM: 'node/innocence/victim.py@1.0 · config/thresholds.yaml#victim',
};

const sig = (det, rid, score, evidence, template, notes = []) => ({
  signal_id: `${det}:${rid}`,
  detector_id: det,
  score,
  evidence,
  notes,
  template,
  source: SRC[det] ?? 'node/rules/cnb_rules.py@1.0',
});

// ---------------------------------------------------------------- timeline + graph builders
function buildTimeline(rid, pattern, n = 48) {
  const start = Date.UTC(2026, 6, 1, 8, 0);
  const cps = {
    in: Array.from({ length: 6 }, () => cref()),
    out: Array.from({ length: 3 }, () => cref()),
    remit: [cref()],
  };
  const out = [];
  let t = start;
  for (let i = 0; i < n; i++) {
    t += int(2, 30) * 3600 * 1000;
    let direction, amount, cp;
    if (pattern === 'mule') {
      direction = i % 3 === 2 ? 'out' : 'in';
      amount = direction === 'in' ? int(18, 49) * 1000 + int(0, 999) : int(40, 95) * 1000;
      cp = direction === 'in' ? pick(cps.in) : pick(cps.out);
    } else if (pattern === 'mom') {
      direction = i % 4 === 0 ? 'in' : i % 4 === 1 ? 'remit_out' : 'out';
      amount = direction === 'in' ? 38500 : direction === 'remit_out' ? 8000 + int(-300, 300) : int(150, 2400);
      cp = direction === 'in' ? cps.in[0] : direction === 'remit_out' ? cps.remit[0] : pick(['m-albert', 'm-cez', 'm-o2', 'm-lidl', 'm-dpp']);
    } else if (pattern === 'victim') {
      direction = i < 4 ? 'in' : 'out';
      amount = i === 2 ? 420000 : direction === 'in' ? int(20, 40) * 1000 : int(30, 120) * 1000;
      cp = direction === 'in' ? (i === 2 ? 'c-pension-fund' : cps.in[0]) : pick(cps.out);
    } else {
      direction = rnd() < 0.5 ? 'in' : 'out';
      amount = direction === 'out' && rnd() < 0.6 ? 14000 + int(500, 900) : int(2, 30) * 1000;
      cp = direction === 'in' ? pick(cps.in) : pick(cps.out);
    }
    out.push({ ts: new Date(t).toISOString().replace('.000', ''), direction, amount_czk: amount, counterparty: cp });
  }
  return out;
}

function graphFromTimeline(client, tl) {
  const agg = new Map();
  for (const e of tl) {
    const k = e.counterparty + '|' + (e.direction === 'in' ? 'in' : 'out');
    agg.set(k, (agg.get(k) ?? 0) + e.amount_czk);
  }
  const counts = new Map();
  for (const e of tl) counts.set(e.counterparty, (counts.get(e.counterparty) ?? 0) + 1);
  const nodes = [{ id: client, label: client, kind: 'client' }];
  const edges = [];
  for (const [k, amt] of agg) {
    const [cp, dir] = k.split('|');
    if (!nodes.find((n) => n.id === cp))
      nodes.push({ id: cp, label: cp, kind: cp.startsWith('m-') || cp.includes('pension') ? 'counterparty_popular' : 'counterparty_rare' });
    edges.push(dir === 'in' ? { source: cp, target: client, amount_czk: amt, direction: 'in' } : { source: client, target: cp, amount_czk: amt, direction: 'out' });
  }
  return { nodes, edges };
}

// ---------------------------------------------------------------- the 6 full cases
const now = '2026-10-19T09:12:00Z';
const S = (text, refs) => ({ text, refs });
const full = [];

// 1. Cluster mule, high priority
{
  const id = 'B1-R00123', rid = 'R00123', client = 'c-9f2a1b3c';
  const tl = buildTimeline(rid, 'mule', 54);
  const signals = [
    sig('D1', rid, 0.91, { retention_median: 0.04, lag_median_h: 5.5, n_cycles: 11 }, 'Median retention {retention_median} and median lag {lag_median_h} h over {n_cycles} in/out cycles.'),
    sig('D2', rid, 0.74, { days_since_contract: 6, first_in_czk: 31200 }, 'First inflow of {first_in_czk} CZK arrived {days_since_contract} days after the contract was opened.'),
    sig('D5', rid, 0.88, { share_rare: 0.93, recurring_income_share: 0.0, popular_inflow_share: 0.02, out_total: 612000 }, '{share_rare} of outflows ({out_total} CZK) go to counterparties rarely seen in the bank; recurring income share {recurring_income_share}.'),
    sig('D6', client, 0.81, { exit_tokens_low: 3, lag_median_h: 5.5, retention_median: 0.04, hour_hist: '21-23 h', n_peers: 4 }, 'Timing and retention fingerprint matches {n_peers} other candidates (peak {hour_hist}).', ['Fingerprint compared on blinded tokens only.']),
  ];
  full.push({
    case_id: id, client_ref: client, bank_id: 'B1', priority: 92, triage: 'REVIEW', route: 'mule_review',
    signals, exculpatory: [
      sig('E2', rid, 0.12, { share_popular: 0.05 }, 'Only {share_popular} of spending goes to popular merchants (weak life-activity signal).', ['Below threshold, shown for completeness.']),
    ],
    features: { in_total_czk: 655300, out_total_czk: 612000, n_tx: 54, days_since_contract: 6, declared_income_czk: 24000, is_pep: false, age_band: '18-24', segment: 'retail' },
    triage_reasons: ['D1 and D5 both above threshold', 'No exculpatory signal above 0.5', 'Cross-bank cluster K1 disclosed (3 banks, 5 candidates)'],
    cluster: { cluster_id: 'K1', n_other_banks: 2, n_other_candidates: 4, lag_ret_concentration: 0.87 },
    rule_definitions: RULE_DEFS, timeline: tl, local_graph: graphFromTimeline(client, tl),
    explanation: {
      cs: [
        S('Účet přijal od 6 různých odesílatelů celkem 655 300 Kč a během mediánu 5,5 hodiny z nich odeslal dál 96 %.', ['D1:R00123']),
        S('Odchozí platby míří z 93 % na protistrany, které banka téměř nezná.', ['D5:R00123']),
        S('První příchozí platba přišla 6 dní po založení účtu.', ['D2:R00123']),
        S('Stejný časový a retenční otisk sdílí 4 další kandidáti ve 2 dalších bankách (shluk K1).', ['D6:c-9f2a1b3c', 'cluster:K1']),
      ],
      en: [
        S('The account received 655,300 CZK from 6 different senders and forwarded 96 % of it within a median of 5.5 hours.', ['D1:R00123']),
        S('93 % of outgoing payments go to counterparties the bank barely knows.', ['D5:R00123']),
        S('The first incoming payment arrived 6 days after the account was opened.', ['D2:R00123']),
        S('The same timing and retention fingerprint is shared by 4 other candidates in 2 other banks (cluster K1).', ['D6:c-9f2a1b3c', 'cluster:K1']),
      ],
      not_a_mom: {
        cs: [S('Nejde o pravidelné rodinné remitence: chybí opakovaný příjem i stálý příjemce.', ['E2:R00123'])],
        en: [S('This is not a recurring family remittance pattern: there is no recurring income and no stable recipient.', ['E2:R00123'])],
      },
      triage_justification: {
        cs: S('Návrh REVIEW: dva silné detektory a zveřejněný přeshraniční shluk, bez vyvracejícího signálu.', ['D1:R00123', 'D5:R00123', 'cluster:K1']),
        en: S('Proposed REVIEW: two strong detectors and a disclosed cross-bank cluster, no exculpatory signal.', ['D1:R00123', 'D5:R00123', 'cluster:K1']),
      },
    },
    explanation_violations: [],
    escalation: { role: 'mlro', rule_index: 1, matrix_is_placeholder: true },
    proposals: [
      { triage: 'REVIEW', reason: 'D1+D5 above threshold; no exculpatory signal > 0.5', agent: 'triage-agent@0.4', ts: '2026-10-19T07:41:10Z' },
      { triage: 'REVIEW', reason: 'Cluster K1 disclosed, priority raised 78 -> 92', agent: 'radar-coordinator@0.3', ts: '2026-10-19T08:02:44Z' },
    ],
    decision: null,
    _mock: { relationship_owner: 'Karel Beneš', rule_authors: ['Ondřej Malý'], first_triager: 'Tomáš Svoboda' },
  });
}

// 2. Other cluster member, no explanation yet (to test Generate)
{
  const id = 'B2-R00087', rid = 'R00087', client = 'c-41d7e0a2';
  const tl = buildTimeline(rid, 'mule', 40);
  full.push({
    case_id: id, client_ref: client, bank_id: 'B2', priority: 81, triage: 'REVIEW', route: 'mule_review',
    signals: [
      sig('D4', rid, 0.84, { n_senders_rare: 14, in_total: 388000, n_in: 22 }, '{n_in} inflows totalling {in_total} CZK from {n_senders_rare} rare senders.'),
      sig('D7', rid, 0.77, { cycle_retentions: [0.05, 0.05, 0.049, 0.051, 0.05] }, 'Constant retained share per cycle: {cycle_retentions}.'),
      sig('D6', client, 0.79, { exit_tokens_low: 2, lag_median_h: 6.1, retention_median: 0.05, n_peers: 4 }, 'Fingerprint matches {n_peers} other candidates.'),
    ],
    exculpatory: [],
    features: { in_total_czk: 388000, out_total_czk: 368600, n_tx: 40, days_since_contract: 21, declared_income_czk: 31000, is_pep: false, segment: 'retail' },
    triage_reasons: ['D4 fan-in above threshold', 'D7 fixed skim 5 %', 'Cluster K1 disclosed'],
    cluster: { cluster_id: 'K1', n_other_banks: 2, n_other_candidates: 4, lag_ret_concentration: 0.87 },
    rule_definitions: RULE_DEFS, timeline: tl, local_graph: graphFromTimeline(client, tl),
    explanation: null, explanation_violations: [],
    escalation: { role: 'aml_officer', rule_index: 3, matrix_is_placeholder: true },
    proposals: [{ triage: 'REVIEW', reason: 'D4 + D7 + cluster K1', agent: 'triage-agent@0.4', ts: '2026-10-19T07:43:51Z' }],
    decision: null,
    _mock: { relationship_owner: 'Eva Horáková', rule_authors: [], first_triager: 'Tomáš Svoboda' },
  });
}

// 3. FP auto-closed "mom"
{
  const id = 'B1-R00311', rid = 'R00311', client = 'c-7be05d19';
  const tl = buildTimeline(rid, 'mom', 52);
  full.push({
    case_id: id, client_ref: client, bank_id: 'B1', priority: 18, triage: 'FP', route: 'mule_review',
    signals: [
      sig('D5', rid, 0.58, { share_rare: 0.21, recurring_income_share: 0.71, popular_inflow_share: 0.69, out_total: 154000 }, '{share_rare} of outflows go to rare counterparties.'),
    ],
    exculpatory: [
      sig('E1', rid, 0.86, { remit_top_recipient_count: 12, remit_amount_cv: 0.03, recurring_income_share: 0.71 }, 'Remittances: {remit_top_recipient_count} payments to the same recipient with amount variation {remit_amount_cv}.'),
      sig('E3', rid, 0.79, { recurring_income_share: 0.71 }, '{recurring_income_share} of inflow is recurring income (salary-like).'),
    ],
    features: { in_total_czk: 462000, out_total_czk: 441000, n_tx: 52, days_since_contract: 1460, declared_income_czk: 38500, is_pep: false, segment: 'retail' },
    triage_reasons: ['Rule C hit explained by recurring salary', 'E1 recurring remittance to one recipient (CV 0.03)', 'E3 recurring income 71 %'],
    cluster: null,
    rule_definitions: RULE_DEFS, timeline: tl, local_graph: graphFromTimeline(client, tl),
    explanation: {
      cs: [
        S('Pravidlo C se spustilo kvůli obratu, ale 71 % příjmů tvoří pravidelná mzda.', ['E3:R00311', 'R-C']),
        S('Odchozí platby do zahraničí jdou 12krát stejnému příjemci s téměř stejnou částkou.', ['E1:R00311']),
      ],
      en: [
        S('Rule C fired on turnover, but 71 % of income is a recurring salary.', ['E3:R00311', 'R-C']),
        S('Outgoing foreign payments go 12 times to the same recipient with nearly the same amount.', ['E1:R00311']),
      ],
      not_a_mom: null,
      triage_justification: {
        cs: S('Návrh FP: vzorec odpovídá rodinným remitencím ze mzdy, nikoli průtoku.', ['E1:R00311', 'E3:R00311']),
        en: S('Proposed FP: the pattern matches family remittances from salary, not flow-through.', ['E1:R00311', 'E3:R00311']),
      },
    },
    explanation_violations: [],
    escalation: { role: 'analyst_l1', rule_index: 7, matrix_is_placeholder: true },
    proposals: [{ triage: 'FP', reason: 'E1 + E3 above 0.75; auto-close proposed', agent: 'triage-agent@0.4', ts: '2026-10-19T07:40:02Z' }],
    decision: { action: 'confirm', decider: 'Tomáš Svoboda', role: 'analyst_l1', reason: 'Souhlasím, remitence matce, mzda od stejného zaměstnavatele 4 roky.', approver: null, ts: '2026-10-19T08:30:12Z' },
    _mock: { relationship_owner: 'Karel Beneš', rule_authors: [], first_triager: 'triage-agent' },
  });
}

// 4. Victim protection route
{
  const id = 'B3-R00045', rid = 'R00045', client = 'c-2c8e66f0';
  const tl = buildTimeline(rid, 'victim', 22);
  full.push({
    case_id: id, client_ref: client, bank_id: 'B3', priority: 74, triage: 'REVIEW', route: 'victim_protection',
    signals: [
      sig('D3', rid, 0.69, { july_total: 512000, expected_monthly: 26000, inflow_share_of_volume: 0.52 }, 'July volume {july_total} CZK vs expected {expected_monthly} CZK.'),
      sig('VICTIM', rid, 0.83, { max_single_in: 420000, out_total: 455000, in_total: 498000, share_rare: 0.97 }, 'A single large inflow of {max_single_in} CZK (own savings) was followed by {out_total} CZK sent to rare counterparties.', ['Pattern consistent with a safe-account / investment scam victim.']),
    ],
    exculpatory: [
      sig('E3', rid, 0.64, { recurring_income_share: 0.38 }, '{recurring_income_share} of inflow is recurring income (pension).'),
    ],
    features: { in_total_czk: 498000, out_total_czk: 455000, n_tx: 22, days_since_contract: 6200, declared_income_czk: 21000, is_pep: false, age_band: '70+', segment: 'retail' },
    triage_reasons: ['Victim-pattern signal 0.83', 'Long-standing client with pension income', 'Routed to victim protection, not mule review'],
    cluster: null,
    rule_definitions: RULE_DEFS, timeline: tl, local_graph: graphFromTimeline(client, tl),
    explanation: {
      cs: [
        S('Klient s dlouholetým účtem a důchodem převedl úspory 420 000 Kč a během dvou dnů je odeslal neznámým příjemcům.', ['VICTIM:R00045']),
        S('Vzorec odpovídá spíše oběti podvodu než mule; případ jde na ochranu klienta.', ['VICTIM:R00045', 'E3:R00045']),
      ],
      en: [
        S('A long-standing client with pension income moved 420,000 CZK of savings and sent it to unknown recipients within two days.', ['VICTIM:R00045']),
        S('The pattern fits a fraud victim rather than a mule; the case goes to client protection.', ['VICTIM:R00045', 'E3:R00045']),
      ],
      not_a_mom: null,
      triage_justification: {
        cs: S('Návrh: REVIEW v trase ochrany oběti.', ['VICTIM:R00045']),
        en: S('Proposed: REVIEW on the victim-protection route.', ['VICTIM:R00045']),
      },
    },
    explanation_violations: [],
    escalation: { role: 'aml_officer', rule_index: 2, matrix_is_placeholder: true },
    proposals: [{ triage: 'REVIEW', reason: 'VICTIM 0.83 -> victim_protection route', agent: 'triage-agent@0.4', ts: '2026-10-19T07:44:30Z' }],
    decision: null,
    _mock: { relationship_owner: 'Lucie Černá', rule_authors: [], first_triager: 'triage-agent' },
  });
}

// 5. PEP case
{
  const id = 'B2-R00210', rid = 'R00210', client = 'c-d03f9a71';
  const tl = buildTimeline(rid, 'struct', 44);
  full.push({
    case_id: id, client_ref: client, bank_id: 'B2', priority: 88, triage: 'REVIEW', route: 'mule_review',
    signals: [
      sig('D3', rid, 0.72, { july_total: 940000, expected_monthly: 120000, inflow_share_of_volume: 0.49 }, 'July volume {july_total} CZK vs expected {expected_monthly} CZK.'),
      sig('D8', rid, 0.81, { out_amounts: [14800, 14650, 14900, 14700, 14850, 14600] }, 'Outgoing amounts cluster just below 15 000 CZK: {out_amounts}.'),
    ],
    exculpatory: [
      sig('E5', rid, 0.31, { reciprocity_share: 0.22 }, '{reciprocity_share} of flows are reciprocal with the same counterparties.'),
    ],
    features: { in_total_czk: 940000, out_total_czk: 902000, n_tx: 44, days_since_contract: 2900, declared_income_czk: 120000, is_pep: true, pep_category: 'domestic, municipal', segment: 'premium' },
    triage_reasons: ['Client is a PEP (escalation matrix row 0)', 'D8 structuring below 15 000 CZK', 'Profile gap 7.8x'],
    cluster: null,
    rule_definitions: RULE_DEFS, timeline: tl, local_graph: graphFromTimeline(client, tl),
    explanation: {
      cs: [
        S('Odchozí platby se opakovaně drží těsně pod 15 000 Kč.', ['D8:R00210']),
        S('Objem v červenci je 7,8násobek očekávaného měsíčního profilu.', ['D3:R00210']),
        S('Klient je politicky exponovaná osoba, proto případ eskaluje na MLRO.', ['feature:is_pep']),
      ],
      en: [
        S('Outgoing payments repeatedly stay just below 15,000 CZK.', ['D8:R00210']),
        S('July volume is 7.8 times the expected monthly profile.', ['D3:R00210']),
        S('The client is a politically exposed person, so the case escalates to the MLRO.', ['feature:is_pep']),
      ],
      not_a_mom: null,
      triage_justification: {
        cs: S('Návrh REVIEW: strukturování a PEP status.', ['D8:R00210', 'feature:is_pep']),
        en: S('Proposed REVIEW: structuring and PEP status.', ['D8:R00210', 'feature:is_pep']),
      },
    },
    explanation_violations: [],
    escalation: { role: 'mlro', rule_index: 0, matrix_is_placeholder: true },
    proposals: [{ triage: 'REVIEW', reason: 'PEP + D8', agent: 'triage-agent@0.4', ts: '2026-10-19T07:45:12Z' }],
    decision: null,
    _mock: { relationship_owner: 'Petr Dvořák', rule_authors: ['Ondřej Malý'], first_triager: 'triage-agent' },
  });
}

// 6. Medium case, already confirmed, explanation with a QA violation
{
  const id = 'B3-R00167', rid = 'R00167', client = 'c-5a19c4e8';
  const tl = buildTimeline(rid, 'struct', 36);
  full.push({
    case_id: id, client_ref: client, bank_id: 'B3', priority: 55, triage: 'REVIEW', route: 'mule_review',
    signals: [
      sig('D8', rid, 0.66, { out_amounts: [14500, 14900, 14700, 14800] }, 'Outgoing amounts cluster just below 15 000 CZK: {out_amounts}.'),
      sig('D1', rid, 0.52, { retention_median: 0.21, lag_median_h: 30.0, n_cycles: 6 }, 'Median retention {retention_median} and lag {lag_median_h} h over {n_cycles} cycles.'),
    ],
    exculpatory: [
      sig('E5', rid, 0.58, { reciprocity_share: 0.47 }, '{reciprocity_share} of flows are reciprocal with the same counterparties.', ['Possible shared-flat settling.']),
    ],
    features: { in_total_czk: 214000, out_total_czk: 168000, n_tx: 36, days_since_contract: 410, declared_income_czk: 29000, is_pep: false, segment: 'retail' },
    triage_reasons: ['D8 above threshold', 'E5 partially exculpatory (0.58)'],
    cluster: null,
    rule_definitions: RULE_DEFS, timeline: tl, local_graph: graphFromTimeline(client, tl),
    explanation: {
      cs: [
        S('Čtyři odchozí platby leží mezi 14 500 a 14 900 Kč.', ['D8:R00167']),
        S('Klient pravděpodobně pere peníze pro organizovanou skupinu.', []),
        S('Část toků je oboustranná se stejnými protistranami, což může znamenat sdílené bydlení.', ['E5:R00167']),
      ],
      en: [
        S('Four outgoing payments lie between 14,500 and 14,900 CZK.', ['D8:R00167']),
        S('The client is probably laundering money for an organised group.', []),
        S('Part of the flows is reciprocal with the same counterparties, which may indicate a shared flat.', ['E5:R00167']),
      ],
      not_a_mom: null,
      triage_justification: {
        cs: S('Návrh REVIEW s nízkou jistotou.', ['D8:R00167', 'E5:R00167']),
        en: S('Proposed REVIEW with low confidence.', ['D8:R00167', 'E5:R00167']),
      },
    },
    explanation_violations: [
      { check: 'unreferenced_claim', sentence_index: 1, lang: 'cs', detail: 'Sentence has no refs and makes an accusation not supported by any signal.' },
      { check: 'speculative_intent', sentence_index: 1, lang: 'en', detail: 'Attributes criminal intent; only observable facts allowed.' },
    ],
    escalation: { role: 'analyst_l2', rule_index: 5, matrix_is_placeholder: true },
    proposals: [{ triage: 'REVIEW', reason: 'D8 0.66 vs E5 0.58', agent: 'triage-agent@0.4', ts: '2026-10-19T07:46:00Z' }],
    decision: { action: 'override', decider: 'Lucie Černá', role: 'analyst_l2', reason: 'Spolubydlící potvrzeni z popisů plateb (nájem a energie); struktura částek odpovídá rozpočítání nájmu. Uzavírám jako FP.', approver: null, ts: '2026-10-19T08:55:40Z' },
    _mock: { relationship_owner: 'Eva Horáková', rule_authors: [], first_triager: 'triage-agent' },
  });
}

for (const c of full) write(`case_${c.case_id}.json`, c);

// explain mock for B2-R00087 (generate on demand) - includes a QA violation, never hidden
write('explain_B2-R00087.json', {
  cs: [
    S('Účet přijal 22 plateb v celkové výši 388 000 Kč od 14 odesílatelů, které banka téměř nezná.', ['D4:R00087']),
    S('Z každého cyklu si ponechá téměř přesně 5 %, zbytek pošle dál.', ['D7:R00087']),
    S('Otisk sdílí 4 kandidáti ve 2 dalších bankách (shluk K1).', ['D6:c-41d7e0a2', 'cluster:K1']),
  ],
  en: [
    S('The account received 22 payments totalling 388,000 CZK from 14 senders the bank barely knows.', ['D4:R00087']),
    S('It keeps almost exactly 5 % of each cycle and forwards the rest.', ['D7:R00087']),
    S('The fingerprint is shared by 4 candidates in 2 other banks (cluster K1).', ['D6:c-41d7e0a2', 'cluster:K1']),
  ],
  not_a_mom: {
    cs: [S('Nejde o rodinné remitence: odesílatelé se nestřídají pravidelně a chybí příjem ze mzdy.', [])],
    en: [S('Not family remittances: senders do not repeat regularly and there is no salary income.', [])],
  },
  triage_justification: {
    cs: S('Návrh REVIEW: fan-in, pevná marže a zveřejněný shluk.', ['D4:R00087', 'D7:R00087', 'cluster:K1']),
    en: S('Proposed REVIEW: fan-in, fixed skim and a disclosed cluster.', ['D4:R00087', 'D7:R00087', 'cluster:K1']),
  },
  violations: [{ check: 'missing_refs', sentence_index: 0, lang: 'not_a_mom.cs', detail: 'Sentence in not_a_mom has no refs.' }],
  model_id: 'eu.anthropic.claude-sonnet-4-5',
  cached: false,
});

// ---------------------------------------------------------------- queue (48 items)
const items = full.map((c) => ({
  case_id: c.case_id, bank_id: c.bank_id, client_ref: c.client_ref, priority: c.priority, triage: c.triage, route: c.route,
  rules: [...new Set([...(c.case_id === 'B1-R00123' ? ['R-A'] : c.case_id === 'B1-R00311' ? ['R-C'] : c.case_id === 'B3-R00045' ? ['R-B'] : []),
    ...c.signals.map((x) => x.detector_id).filter((d) => d.startsWith('D')), ...(c.cluster ? ['X'] : [])])],
  cluster_id: c.cluster?.cluster_id ?? null, escalation_role: c.escalation.role,
  decision_status: c.decision ? (c.decision.action === 'confirm' ? 'confirmed' : 'overridden') : 'open',
}));
const clusterOf = { K1: ['B1', 'B2', 'B3'], K2: ['B1', 'B3'] };
let k1extra = 2, k2 = 2;
for (let i = 0; i < 42; i++) {
  const bank = pick(['B1', 'B1', 'B2', 'B2', 'B3']);
  const pr = Math.max(3, Math.min(99, Math.round(rnd() ** 1.3 * 100)));
  const fp = pr < 35 ? rnd() < 0.85 : rnd() < 0.12;
  const rules = [...new Set(Array.from({ length: int(1, 3) }, () => pick(RULES_POOL)))].sort();
  let cluster = null;
  if (!fp && pr > 60 && k1extra > 0 && clusterOf.K1.includes(bank)) { cluster = 'K1'; k1extra--; }
  else if (!fp && pr > 45 && k2 > 0 && clusterOf.K2.includes(bank)) { cluster = 'K2'; k2--; }
  if (cluster) rules.push('X');
  const victim = !fp && i % 13 === 5;
  const status = fp ? (rnd() < 0.7 ? 'confirmed' : 'open') : pick(['open', 'open', 'open', 'confirmed', 'overridden']);
  items.push({
    case_id: `${bank}-R${String(int(130, 990)).padStart(5, '0')}`, bank_id: bank, client_ref: cref(), priority: pr,
    triage: fp ? 'FP' : 'REVIEW', route: victim ? 'victim_protection' : 'mule_review', rules, cluster_id: cluster,
    escalation_role: ROLE_FOR(pr, false), decision_status: status,
  });
}
const nReview = items.filter((x) => x.triage === 'REVIEW').length;
write('queue.json', {
  counts: {
    alerts_before_triage: 137,
    cases: items.length,
    review: nReview,
    fp_auto_closed: items.length - nReview,
    victim_protection: items.filter((x) => x.route === 'victim_protection').length,
  },
  items,
});

// ---------------------------------------------------------------- OPO drafts
function opo(c, sentences) {
  return {
    title: `Oznámení podezřelého obchodu – NÁVRH – ${c.case_id}`,
    sections: [
      { no: 'I', title: 'Oznamující povinná osoba', text: `Banka ${c.bank_id} (syntetická), IČO 00000000 – údaje z nastavení povinné osoby.` },
      { no: 'II', title: 'Subjekt podezřelého obchodu', text: `Klient ${c.client_ref} (pseudonym). Identifikační údaje doplní systém banky při odeslání; v návrhu se nezobrazují.` },
      { no: 'III', title: 'Popis obchodu', text: `Příchozí a odchozí platby v období 1. 7. – 31. 7. 2026, celkem ${c.features.in_total_czk} Kč příchozích a ${c.features.out_total_czk} Kč odchozích.` },
      { no: 'IV', title: 'Časový rámec a objem', text: `Počet transakcí: ${c.features.n_tx}. Podrobný výpis viz příloha (export z jádrového systému).` },
      { no: 'V', title: 'Důvody podezření', text: '' },
      { no: 'VI', title: 'Přijatá opatření', text: '' },
      { no: 'VII', title: 'Související účty a protistrany', text: `Pseudonymní protistrany: ${c.local_graph.nodes.filter((n) => n.kind !== 'client').slice(0, 5).map((n) => n.id).join(', ')}.` },
      { no: 'VIII', title: 'Podklady a přílohy', text: 'Případová karta, auditní záznam (hash hlavy řetězce), výpis transakcí.' },
      { no: 'IX', title: 'Další skutečnosti', text: '' },
      { no: 'X', title: 'Kontaktní údaje', text: 'Kontaktní osoba povinné osoby dle nastavení (bank_settings). Jméno analytika se do oznámení neuvádí.' },
    ],
    section_v_sentences: sentences,
    section_v_violations: [],
  };
}
const c1 = full[0], c5 = full[4];
write(`opo_${c1.case_id}.json`, opo(c1, c1.explanation.cs));
const opo5 = opo(c5, c5.explanation.cs);
opo5.section_v_violations = [{ check: 'mentions_internal_role', sentence_index: 2, detail: 'Sentence refers to internal escalation (MLRO); FAÚ report should state facts only.' }];
write(`opo_${c5.case_id}.json`, opo5);
for (const [c, o] of [[c1, opo(c1, c1.explanation.cs)], [c5, opo5]]) {
  const md = [`# ${o.title}`, '', '> NÁVRH – syntetická data. Rozhoduje člověk.', '']
    .concat(o.sections.flatMap((sec) => [`## ${sec.no}. ${sec.title}`, '', sec.no === 'V' ? o.section_v_sentences.map((x) => x.text).join(' ') : sec.text || '_(doplní člověk)_', '']))
    .join('\n');
  write(`opo_${c.case_id}.md`, md);
}

// ---------------------------------------------------------------- radar
const bankGraph = (bank, n) => {
  const nodes = [], edges = [];
  for (let i = 0; i < n; i++) {
    const id = `${bank}:${cref()}`;
    nodes.push({ id, label: id.slice(3, 9), kind: i < 2 ? 'client' : 'counterparty_rare' });
    if (i > 0) edges.push({ source: nodes[int(0, i - 1)].id, target: id });
  }
  return { nodes, edges };
};
const tokens = Array.from({ length: 6 }, () => 't-' + hex(6));
const cg = { nodes: [], edges: [] };
for (const b of ['B1', 'B2', 'B3']) cg.nodes.push({ id: b, label: b, kind: 'bank' });
const cands = [['B1', 'c-9f2a1b3c'], ['B1', 'c-0a7d2e11'], ['B2', 'c-41d7e0a2'], ['B2', 'c-b6f3c810'], ['B3', 'c-e1924d5a']];
cands.forEach(([b, c]) => { cg.nodes.push({ id: c, label: c, kind: 'candidate', bank: b }); cg.edges.push({ source: b, target: c }); });
tokens.forEach((t) => cg.nodes.push({ id: t, label: t, kind: 'token' }));
const tokEdges = [[0, 0], [0, 1], [1, 0], [1, 2], [2, 1], [2, 3], [3, 2], [3, 3], [4, 3], [4, 4], [0, 5], [4, 5]];
tokEdges.forEach(([ci, ti]) => cg.edges.push({ source: cands[ci][1], target: tokens[ti] }));
const wire = [];
for (const sess of ['B1xB2', 'B1xB3', 'B2xB3']) {
  const [a, b] = sess.split('x');
  const na = int(380, 720), nb = int(380, 720);
  const steps = [
    ['A->B blind', a, na], ['B->A double_blind', b, na], ['B->A blind', b, nb], ['A->B back', a, nb],
  ];
  for (const [msg, from, n] of steps) wire.push({ session: sess, msg, from, n, sample: Array.from({ length: 4 }, () => hex(64)) });
}
const blinded = wire.reduce((a, w) => a + w.n, 0);
write('radar.json', {
  banks: [
    { bank_id: 'B1', n_cases: 19, n_review: 12, n_candidates_exported: 7, local_graph: bankGraph('B1', 7) },
    { bank_id: 'B2', n_cases: 17, n_review: 10, n_candidates_exported: 5, local_graph: bankGraph('B2', 5) },
    { bank_id: 'B3', n_cases: 12, n_review: 7, n_candidates_exported: 4, local_graph: bankGraph('B3', 4) },
  ],
  clusters: [
    { cluster_id: 'K1', banks: ['B1', 'B2', 'B3'], n_candidates: 5, tokens: 6, score: 0.87, disclosed: true, same_hand_global: true, lag_ret_concentration: 0.87 },
    { cluster_id: 'K2', banks: ['B1', 'B3'], n_candidates: 2, tokens: 2, score: 0.61, disclosed: false, same_hand_global: false, lag_ret_concentration: null },
    { cluster_id: 'K3', banks: ['B2'], n_candidates: 3, tokens: 3, score: 0.55, disclosed: false, same_hand_global: false, lag_ret_concentration: 0.41 },
  ],
  cluster_graph: cg,
  wire,
  exposure: {
    isolated: { raw_records_exposed: 0, bytes_exchanged: 0 },
    staj_psi: { raw_records_exposed: 0, blinded_elements: blinded, bytes_exchanged: blinded * 32, match_rows_to_coordinator: 14 },
    naive_raw_sharing: { raw_records_exposed: 48210, bytes_exchanged: 9843120 },
  },
  disclosure_rule: 'A cluster is disclosed only if it spans >= 2 banks and >= 3 candidates.',
  refused: { K2: 'only 2 candidates (< 3)', K3: 'only 1 bank (< 2)' },
});

// ---------------------------------------------------------------- metrics
const conf = (tp, fp, fn) => {
  const p = tp / (tp + fp), r = tp / (tp + fn);
  return { tp, fp, fn, precision: +p.toFixed(3), recall: +r.toFixed(3), f1: +((2 * p * r) / (p + r)).toFixed(3) };
};
write('metrics.json', {
  dataset: 'staj-synth-v0.3 (MOCK)',
  seed: 20261019,
  synthetic: true,
  modes: {
    isolated: { overall: { ...conf(17, 9, 19), n_mules: 36, n_accounts: 3000 }, exposure: { raw_records_exposed: 0 } },
    staj_psi: { overall: { ...conf(29, 7, 7), n_mules: 36, n_accounts: 3000 }, exposure: { raw_records_exposed: 0, blinded_elements: blinded } },
    naive_raw_sharing: { overall: { ...conf(31, 7, 5), n_mules: 36, n_accounts: 3000 }, exposure: { raw_records_exposed: 48210 } },
  },
  breakdown: {
    'scheme:fan_in_star': { n: 12, flagged_as_mule_case: 11, routed_to_victim_protection: 0, rate: 0.917 },
    'scheme:chain_relay': { n: 10, flagged_as_mule_case: 8, routed_to_victim_protection: 0, rate: 0.8 },
    'scheme:same_hand_ring': { n: 8, flagged_as_mule_case: 7, routed_to_victim_protection: 0, rate: 0.875 },
    'scheme:slow_mule': { n: 6, flagged_as_mule_case: 3, routed_to_victim_protection: 0, rate: 0.5 },
    'persona:mom_remitter': { n: 120, flagged_as_mule_case: 3, routed_to_victim_protection: 0, rate: 0.025 },
    'persona:shared_flat': { n: 80, flagged_as_mule_case: 4, routed_to_victim_protection: 0, rate: 0.05 },
    'persona:airbnb_cohost': { n: 40, flagged_as_mule_case: 3, routed_to_victim_protection: 0, rate: 0.075 },
    'persona:gig_earner': { n: 60, flagged_as_mule_case: 2, routed_to_victim_protection: 0, rate: 0.033 },
    'persona:new_job': { n: 50, flagged_as_mule_case: 1, routed_to_victim_protection: 0, rate: 0.02 },
    'victim:safe_account_scam': { n: 9, flagged_as_mule_case: 1, routed_to_victim_protection: 7, rate: 0.778 },
    'victim:investment_scam': { n: 6, flagged_as_mule_case: 0, routed_to_victim_protection: 4, rate: 0.667 },
  },
  ablations: {
    full: conf(29, 7, 7),
    without_innocence_layer: conf(30, 41, 6),
    without_radar: conf(17, 9, 19),
    without_d6_d7: conf(23, 8, 13),
  },
  failures: {
    worst_false_positives: [
      { case_id: 'B2-R00544', client_ref: 'c-88a1f0d2', persona: 'airbnb_cohost', priority: 77, signals: ['D4', 'D5'], why: 'Many one-off guest payments look like fan-in; E7 co-host signal below threshold.' },
      { case_id: 'B1-R00602', client_ref: 'c-13c9be47', persona: 'shared_flat', priority: 71, signals: ['D1', 'D8'], why: 'Rent split just below 15 000 CZK looks like structuring.' },
      { case_id: 'B3-R00718', client_ref: 'c-f04e7a3b', persona: 'mom_remitter', priority: 64, signals: ['D5'], why: 'Remittance recipient changed bank mid-period; E1 lost the recurring recipient.' },
    ],
    false_negatives: [
      { client_ref: 'c-6b0d92e5', bank_id: 'B3', scheme: 'slow_mule', max_priority: 31, missed_because: 'Lag 9 days and 30 % retention; D1 lag threshold is 72 h.' },
      { client_ref: 'c-c27a4f18', bank_id: 'B2', scheme: 'slow_mule', max_priority: 28, missed_because: 'Exits to popular exchange (not rare), D5 silent.' },
      { client_ref: 'c-90ef1d6c', bank_id: 'B1', scheme: 'chain_relay', max_priority: 44, missed_because: 'Single-bank chain; no radar overlap, below operating point.' },
    ],
  },
  cnb: {
    n_clients: 3000,
    n_tx: 214503,
    rule_a_alerts_per_unit: { per_calendar_month: 41, per_rolling_30d: 57, per_calendar_week: 12 },
    rule_b_alerts: 23,
    rule_c_alerts: 64,
    rule_c_triage: { FP: 38, REVIEW: 26 },
    priority_hist: ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-100'].map((bin, i) => ({ bin, count: [14, 22, 19, 11, 9, 8, 7, 6, 4, 3][i] })),
    mom_persona: { n: 120, fp_rate: 0.025 },
    sample_sheet_url: '/mock/review_sheet_30.csv',
  },
  operating_point: { definition: 'Case counts as flagged when priority >= min_priority and triage = REVIEW.', min_priority: 40 },
});
write('review_sheet_30.csv', 'case_id,client_ref,priority,triage,reviewer_verdict,notes\n' +
  items.slice(0, 30).map((x) => `${x.case_id},${x.client_ref},${x.priority},${x.triage},,`).join('\n') + '\n');

// ---------------------------------------------------------------- audit (real hash chain over mock entries)
const actors = ['pipeline', 'triage-agent@0.4', 'explain-agent@0.5', 'radar-coordinator@0.3', 'Tomáš Svoboda', 'Lucie Černá', 'Petr Dvořák'];
const actions = { pipeline: 'pipeline_run', 'triage-agent@0.4': 'triage_proposal', 'explain-agent@0.5': 'explain', 'radar-coordinator@0.3': 'radar_session' };
let prev = '0'.repeat(64);
const entries = [];
let t = Date.UTC(2026, 9, 19, 7, 30);
for (let seq = 0; seq < 137; seq++) {
  t += int(5, 90) * 1000;
  const actor = seq === 0 ? 'pipeline' : pick(actors);
  const action = actions[actor] ?? pick(['decision', 'opo_draft_saved', 'decision']);
  const caseId = pick(items).case_id;
  const why = action === 'pipeline_run' ? 'Nightly batch over staj-synth-v0.3' : action === 'triage_proposal' ? `Proposed triage for ${caseId}` :
    action === 'explain' ? `Generated explanation for ${caseId}` : action === 'radar_session' ? `PSI session ${pick(['B1xB2', 'B1xB3', 'B2xB3'])}` :
    action === 'decision' ? `Human decision on ${caseId}` : `Section V edited for ${caseId}`;
  const input_hash = sha(`${seq}|${caseId}|${action}`);
  const e = { seq, ts: new Date(t).toISOString().replace('.000', ''), actor, action, why, rule_version: 'rules@1.3.0',
    model_version: ['explain', 'triage_proposal'].includes(action) ? 'eu.anthropic.claude-sonnet-4-5' : null, input_hash, prev_hash: prev };
  e.hash = sha(prev + JSON.stringify(e));
  prev = e.hash;
  entries.push(e);
}
write('audit.json', { total: entries.length, entries });
write('audit_verify.json', { ok: true, bad_index: null, length: entries.length, head: prev });
const meta = JSON.parse(JSON.stringify({ chain: { ok: true, length: entries.length, head: prev } }));
// patch meta
import('node:fs').then(({ readFileSync }) => {
  const m = JSON.parse(readFileSync(join(OUT, 'meta.json'), 'utf8'));
  m.chain = meta.chain;
  write('meta.json', m);
});

// ---------------------------------------------------------------- honesty
write('honesty.json', {
  sources: [
    { name: 'staj-synth generator', description: 'Synthetic retail population (3 banks, 3 000 clients) with honest personas and planted mule schemes.', kind: 'real-synthetic' },
    { name: 'Planted mule schemes', description: 'Fan-in stars, relay chains, same-hand rings, slow mules, scam victims inserted by the generator with known labels.', kind: 'planted' },
    { name: 'CNB pilot rules A/B/C', description: 'Generic rule shapes inspired by public supervisory discussion; thresholds are our assumptions.', kind: 'generic' },
    { name: 'FX rates', description: 'Fixed placeholder rates, not market data.', kind: 'generic' },
  ],
  planted: ['36 mule accounts across 4 schemes', '15 scam victims (safe-account, investment)', '1 cross-bank same-hand ring (cluster K1)'],
  limitations: [
    'All metrics are measured on synthetic data generated by the same team that wrote the detectors; real-world performance is unknown.',
    'Escalation matrix is a placeholder, not a bank policy.',
    'FX conversion uses placeholder rates.',
    'Slow mules (lag > 72 h) are mostly missed.',
    'LLM explanations are checked by rule-based QA, which can miss subtle errors; a human must read them.',
  ],
  legal_note: 'PSI (private set intersection) minimises what banks reveal to each other; it is not a legal basis for sharing. Any cross-bank exchange needs its own legal basis and legal review.',
  not_found_in_public_sources: ['Exact CNB thresholds for rules A/B/C', 'Official FAÚ field-level schema for the report draft'],
});

console.log('mock files written to', OUT);
