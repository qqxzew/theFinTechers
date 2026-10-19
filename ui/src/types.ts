// Types mirror the API contract agreed with the backend (FastAPI). Keep in sync.

export type Scalar = number | string | boolean | null;

export interface Meta {
  data_label: string;
  fx_placeholder: boolean;
  matrix_placeholder: boolean;
  models: {
    agent_primary: string;
    fallback: string;
    bulk: string;
    active: { agent_primary: string };
  };
  chain: { ok: boolean; length: number; head: string };
  roles: string[];
  four_eyes_min_priority: number;
}

export type Triage = 'FP' | 'REVIEW';
export type Route = 'mule_review' | 'victim_protection';
export type DecisionStatus = 'open' | 'confirmed' | 'overridden';

export interface QueueItem {
  case_id: string;
  bank_id: string;
  client_ref: string;
  priority: number;
  triage: Triage;
  route: Route;
  rules: string[];
  cluster_id: string | null;
  escalation_role: string;
  decision_status: DecisionStatus;
}

export interface QueueCounts {
  alerts_before_triage: number;
  cases: number;
  review: number;
  fp_auto_closed: number;
  victim_protection: number;
}

export interface QueueResponse {
  counts: QueueCounts;
  items: QueueItem[];
}

export interface QueueFilters {
  rule?: string;
  min_priority?: number;
  max_priority?: number;
  triage?: string;
  cluster?: string;
  bank?: string;
}

export interface Signal {
  signal_id: string;
  detector_id: string;
  score: number;
  evidence: Record<string, Scalar | Scalar[]>;
  notes: string[];
  template: string;
  source: string;
}

export interface Sentence {
  text: string;
  refs: string[];
}

export interface Explanation {
  en: Sentence[];
  cs: Sentence[];
  not_a_mom: { en: Sentence[]; cs: Sentence[] } | null;
  triage_justification: { en: Sentence; cs: Sentence };
}

export interface ExplainResponse extends Explanation {
  violations: Record<string, unknown>[];
  model_id: string;
  cached: boolean;
}

export interface TimelineEntry {
  ts: string;
  direction: 'in' | 'out' | 'remit_out';
  amount_czk: number;
  counterparty: string;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: string;
  bank?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  amount_czk?: number;
  direction?: string;
}

export interface LocalGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Decision {
  action: 'confirm' | 'override';
  decider: string;
  role: string;
  reason: string;
  approver: string | null;
  ts: string;
}

export interface Proposal {
  triage: string;
  reason: string;
  agent: string;
  ts: string;
}

export interface CaseDetail {
  case_id: string;
  client_ref: string;
  bank_id: string;
  priority: number;
  triage: Triage;
  route: Route;
  signals: Signal[];
  exculpatory: Signal[];
  features: Record<string, number | string | boolean>;
  triage_reasons: string[];
  cluster: {
    cluster_id: string;
    n_other_banks: number;
    n_other_candidates: number;
    lag_ret_concentration: number | null;
  } | null;
  rule_definitions: Record<string, string>;
  timeline: TimelineEntry[];
  local_graph: LocalGraph;
  explanation: Explanation | null;
  explanation_violations: Record<string, unknown>[];
  escalation: { role: string; rule_index: number; matrix_is_placeholder: boolean };
  proposals: Proposal[];
  decision: Decision | null;
}

export interface DecisionRequest {
  action: 'confirm' | 'override';
  decider: string;
  role: string;
  reason: string;
  approver?: string | null;
}

export interface DecisionResponse {
  ok: boolean;
  violations: string[];
  decision?: Decision | Record<string, unknown>;
}

export interface OpoSection {
  no: string;
  title: string;
  text: string;
}

export interface OpoDraft {
  title: string;
  sections: OpoSection[];
  section_v_sentences: Sentence[];
  section_v_violations: Record<string, unknown>[];
}

export interface RadarBank {
  bank_id: string;
  n_cases: number;
  n_review: number;
  n_candidates_exported: number;
  local_graph: LocalGraph;
}

export interface RadarCluster {
  cluster_id: string;
  banks: string[];
  n_candidates: number;
  tokens: number;
  score: number;
  disclosed: boolean;
  same_hand_global: boolean;
  lag_ret_concentration: number | null;
}

export interface WireMsg {
  session: string;
  msg: string;
  from: string;
  n: number;
  sample: string[];
}

export interface Exposure {
  isolated: { raw_records_exposed: number; bytes_exchanged: number };
  staj_psi: {
    raw_records_exposed: number;
    blinded_elements: number;
    bytes_exchanged: number;
    match_rows_to_coordinator: number;
  };
  naive_raw_sharing: { raw_records_exposed: number; bytes_exchanged: number };
}

export interface RadarResponse {
  banks: RadarBank[];
  clusters: RadarCluster[];
  cluster_graph: LocalGraph;
  wire: WireMsg[];
  exposure: Exposure;
  disclosure_rule: string;
  refused: Record<string, string>;
}

export interface Confusion {
  tp: number;
  fp: number;
  fn: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface ModeResult {
  overall: Confusion & { n_mules: number; n_accounts: number };
  exposure: Record<string, unknown>;
}

export interface CnbSection {
  n_clients: number;
  n_tx: number;
  rule_a_alerts_per_unit: Record<string, number>;
  rule_b_alerts: number;
  rule_c_alerts: number;
  rule_c_triage: { FP: number; REVIEW: number };
  priority_hist: { bin: string; count: number }[];
  mom_persona: { n: number; fp_rate: number } | null;
  sample_sheet_url: string | null;
}

export interface MetricsResponse {
  dataset: string;
  seed: number;
  synthetic: true;
  modes: Partial<Record<'isolated' | 'staj_psi' | 'naive_raw_sharing', ModeResult>>;
  breakdown: Record<string, { n: number; flagged_as_mule_case: number; routed_to_victim_protection: number; rate: number }>;
  ablations: Record<string, Confusion>;
  failures: { worst_false_positives: Record<string, unknown>[]; false_negatives: Record<string, unknown>[] };
  cnb: CnbSection | null;
  operating_point: { definition: string; min_priority: number };
}

export interface AuditEntry {
  seq: number;
  ts: string;
  actor: string;
  action: string;
  why: string;
  rule_version: string;
  model_version: string | null;
  input_hash: string;
  prev_hash: string;
  hash: string;
}

export interface AuditResponse {
  total: number;
  entries: AuditEntry[];
}

export interface AuditVerify {
  ok: boolean;
  bad_index: number | null;
  length: number;
  head: string;
}

export interface HonestyResponse {
  sources: { name: string; description: string; kind: 'real-synthetic' | 'planted' | 'generic' }[];
  planted: string[];
  limitations: string[];
  legal_note: string;
  not_found_in_public_sources: string[];
}
