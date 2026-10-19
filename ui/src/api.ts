// Single fetch layer. With VITE_API_BASE set, calls the real FastAPI backend.
// Without it, reads MOCK JSON files from /mock/ and simulates write endpoints in memory.
import type {
  AskResponse, AuditResponse, AuditVerify, CaseDetail, DecisionRequest, DecisionResponse, ExplainResponse,
  HonestyResponse, Meta, MetricsResponse, OpoDraft, QueueFilters, QueueResponse, RadarResponse, Sentence,
} from './types';

const RAW_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.trim();
export const API_BASE = RAW_BASE ? RAW_BASE.replace(/\/$/, '') : '';
export const USING_MOCKS = !API_BASE;
const MOCK = `${import.meta.env.BASE_URL}mock`;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new ApiError(r.status, `${r.status} ${r.statusText} – ${url}`);
  const ct = r.headers.get('content-type') ?? '';
  // Vite dev server returns index.html for missing files; treat that as 404.
  if (!ct.includes('json')) throw new ApiError(404, `Not found – ${url}`);
  return (await r.json()) as T;
}

async function sendJson<T>(method: 'POST' | 'PUT', path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  // Decision rejections may come back as 4xx with a JSON body containing violations.
  const ct = r.headers.get('content-type') ?? '';
  if (ct.includes('json')) {
    const data = await r.json();
    if (!r.ok && !(data && typeof data === 'object' && 'violations' in data)) {
      throw new ApiError(r.status, JSON.stringify(data));
    }
    return data as T;
  }
  if (!r.ok) throw new ApiError(r.status, `${r.status} ${r.statusText}`);
  return (await r.text()) as unknown as T;
}

const qs = (params: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : '';
};

// ------------------------------------------------------------------ mock state (in memory)
const mockDecisions = new Map<string, Record<string, unknown>>();
const mockSectionV = new Map<string, Sentence[]>();
const mockExplanations = new Map<string, ExplainResponse>();

const ROLE_RANK: Record<string, number> = { analyst_l1: 1, analyst_l2: 2, aml_officer: 3, mlro: 4 };

// ------------------------------------------------------------------ endpoints
export function getMeta(): Promise<Meta> {
  return USING_MOCKS ? getJson(`${MOCK}/meta.json`) : getJson(`${API_BASE}/api/meta`);
}

// Short-lived cache so identical queue requests (StrictMode double effects, filter-option lookup)
// share one network call. Decisions invalidate it.
const queueCache = new Map<string, { at: number; p: Promise<QueueResponse> }>();
export function invalidateQueue() {
  queueCache.clear();
}

export async function getQueue(f: QueueFilters = {}): Promise<QueueResponse> {
  if (!USING_MOCKS) {
    const url = `${API_BASE}/api/queue${qs({ ...f })}`;
    const hit = queueCache.get(url);
    if (hit && Date.now() - hit.at < 15000) return hit.p;
    const p = getJson<QueueResponse>(url);
    p.catch(() => queueCache.delete(url));
    queueCache.set(url, { at: Date.now(), p });
    return p;
  }
  const data = await getJson<QueueResponse>(`${MOCK}/queue.json`);
  const items = data.items
    .map((it) => {
      const d = mockDecisions.get(it.case_id);
      return d ? { ...it, decision_status: d.action === 'confirm' ? ('confirmed' as const) : ('overridden' as const) } : it;
    })
    .filter((it) => {
      if (f.rule && !it.rules.includes(f.rule)) return false;
      if (f.min_priority !== undefined && it.priority < f.min_priority) return false;
      if (f.max_priority !== undefined && it.priority > f.max_priority) return false;
      if (f.triage && it.triage !== f.triage) return false;
      if (f.cluster && it.cluster_id !== f.cluster) return false;
      if (f.bank && it.bank_id !== f.bank) return false;
      return true;
    });
  return { counts: data.counts, items };
}

export async function getCase(id: string): Promise<CaseDetail> {
  if (!USING_MOCKS) return getJson(`${API_BASE}/api/cases/${encodeURIComponent(id)}`);
  const c = await getJson<CaseDetail>(`${MOCK}/case_${id}.json`);
  const d = mockDecisions.get(id);
  const ex = mockExplanations.get(id);
  return {
    ...c,
    decision: (d as unknown as CaseDetail['decision']) ?? c.decision,
    explanation: ex ? { en: ex.en, cs: ex.cs, not_a_mom: ex.not_a_mom, triage_justification: ex.triage_justification } : c.explanation,
    explanation_violations: ex ? ex.violations : c.explanation_violations,
  };
}

export async function explainCase(id: string): Promise<ExplainResponse> {
  if (!USING_MOCKS) return sendJson('POST', `/api/cases/${encodeURIComponent(id)}/explain`);
  await new Promise((r) => setTimeout(r, 1400)); // simulate model latency
  let res: ExplainResponse;
  try {
    res = await getJson<ExplainResponse>(`${MOCK}/explain_${id}.json`);
  } catch {
    const c = await getJson<CaseDetail>(`${MOCK}/case_${id}.json`);
    if (!c.explanation) throw new ApiError(503, 'Mock: no explanation available for this case');
    res = { ...c.explanation, violations: c.explanation_violations, model_id: 'mock-cached', cached: true };
  }
  mockExplanations.set(id, res);
  return res;
}

export async function askCase(id: string, question: string): Promise<AskResponse> {
  if (!USING_MOCKS) return sendJson('POST', `/api/cases/${encodeURIComponent(id)}/ask`, { question });
  await new Promise((r) => setTimeout(r, 1200));
  try {
    return await getJson<AskResponse>(`${MOCK}/ask_${id}.json`);
  } catch {
    return await getJson<AskResponse>(`${MOCK}/ask_default.json`);
  }
}

export async function postDecision(id: string, body: DecisionRequest): Promise<DecisionResponse> {
  if (!USING_MOCKS) {
    const r = await sendJson<DecisionResponse>('POST', `/api/cases/${encodeURIComponent(id)}/decision`, body);
    if (r.ok) invalidateQueue();
    return r;
  }
  // MOCK of the server-side checks (the real server is the authority).
  const c = await getJson<CaseDetail & { _mock?: { relationship_owner: string; rule_authors: string[]; first_triager: string } }>(
    `${MOCK}/case_${id}.json`,
  );
  const meta = await getMeta();
  const v: string[] = [];
  const m = c._mock;
  if (!body.decider.trim()) v.push('decider_missing');
  if (m && body.decider === m.relationship_owner) v.push('decider_is_relationship_owner');
  if (m && m.rule_authors.includes(body.decider)) v.push('decider_is_rule_author');
  if (m && body.decider === m.first_triager) v.push('decider_is_first_triager');
  if (body.action === 'override' && body.reason.trim().length < 10) v.push('override_requires_written_reason');
  if ((ROLE_RANK[body.role] ?? 0) < (ROLE_RANK[c.escalation.role] ?? 0)) v.push('role_below_escalation_target');
  if (c.priority >= meta.four_eyes_min_priority && (!body.approver || body.approver === body.decider)) v.push('four_eyes_required');
  if (v.length) return { ok: false, violations: v };
  const decision = { ...body, approver: body.approver ?? null, ts: new Date().toISOString() };
  mockDecisions.set(id, decision);
  return { ok: true, violations: [], decision };
}

// The first GET of an OPO draft runs an LLM on the server (~1-2 min). De-duplicate concurrent
// requests (React StrictMode mounts effects twice in dev) so only one draft call is made.
const opoInflight = new Map<string, Promise<OpoDraft>>();

export async function getOpo(id: string): Promise<OpoDraft> {
  if (!USING_MOCKS) {
    const hit = opoInflight.get(id);
    if (hit) return hit;
    const p = getJson<OpoDraft>(`${API_BASE}/api/opo/${encodeURIComponent(id)}`).finally(() => opoInflight.delete(id));
    opoInflight.set(id, p);
    return p;
  }
  const o = await getJson<OpoDraft>(`${MOCK}/opo_${id}.json`);
  const sv = mockSectionV.get(id);
  return sv ? { ...o, section_v_sentences: sv, section_v_violations: [] } : o;
}

export async function putSectionV(id: string, sentences: Sentence[]): Promise<OpoDraft> {
  if (!USING_MOCKS) return sendJson('PUT', `/api/opo/${encodeURIComponent(id)}/section-v`, { sentences });
  mockSectionV.set(id, sentences);
  const o = await getOpo(id);
  // mock QA: flag sentences without refs
  const viol = sentences
    .map((s, i) => (s.refs.length ? null : { check: 'missing_refs', sentence_index: i, detail: 'Sentence has no refs (mock QA).' }))
    .filter(Boolean) as Record<string, unknown>[];
  return { ...o, section_v_violations: viol };
}

export function opoExportUrl(id: string): string {
  return USING_MOCKS ? `${MOCK}/opo_${id}.md` : `${API_BASE}/api/opo/${encodeURIComponent(id)}/export.md`;
}

export function getRadar(): Promise<RadarResponse> {
  return USING_MOCKS ? getJson(`${MOCK}/radar.json`) : getJson(`${API_BASE}/api/radar`);
}

export function getMetrics(): Promise<MetricsResponse> {
  return USING_MOCKS ? getJson(`${MOCK}/metrics.json`) : getJson(`${API_BASE}/api/metrics`);
}

export async function getAudit(offset: number, limit: number): Promise<AuditResponse> {
  if (!USING_MOCKS) return getJson(`${API_BASE}/api/audit${qs({ offset, limit })}`);
  const a = await getJson<AuditResponse>(`${MOCK}/audit.json`);
  return { total: a.total, entries: a.entries.slice(offset, offset + limit) };
}

export function verifyAudit(): Promise<AuditVerify> {
  return USING_MOCKS ? getJson(`${MOCK}/audit_verify.json`) : getJson(`${API_BASE}/api/audit/verify`);
}

export function getHonesty(): Promise<HonestyResponse> {
  return USING_MOCKS ? getJson(`${MOCK}/honesty.json`) : getJson(`${API_BASE}/api/honesty`);
}

/** Resolve a URL coming from the API (e.g. sample_sheet_url) against the API base. */
export function resolveApiUrl(u: string): string {
  if (/^https?:\/\//.test(u)) return u;
  return USING_MOCKS ? u : `${API_BASE}${u.startsWith('/') ? '' : '/'}${u}`;
}

// ------------------------------------------------------------------ text helpers (Report, Limits)

/** Split prose at sentence boundaries without breaking "et al.,", "Coll.;" or decimals. */
export function splitSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+(?=[A-Z0-9ČŘŠŽÚÁÉÍÓÝĎŤŇ("'])/u)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** The first `n` sentences of a text, unchanged (used only to shorten, never to rephrase). */
export function firstSentences(text: string, n: number): string {
  return splitSentences(text).slice(0, n).join(' ');
}

export type LimitGroup = 'data' | 'method' | 'deployment' | 'legal';

/** Group limitation strings by what they are about; order is data, method, deployment, legal. */
export function groupLimitations(items: string[]): { group: LimitGroup; items: string[] }[] {
  const pick = (x: string): LimitGroup => {
    if (/legal|high-risk list|FATF|EUR-Lex|AMLR|§|banking-secrecy/i.test(x)) return 'legal';
    if (/column|dataset|ČNB data contain/i.test(x)) return 'data';
    if (/\bPSI\b|placeholder|out of scope|production/i.test(x)) return 'deployment';
    return 'method';
  };
  const order: LimitGroup[] = ['data', 'method', 'deployment', 'legal'];
  return order.map((group) => ({ group, items: items.filter((x) => pick(x) === group) })).filter((g) => g.items.length);
}

/** "As of ... we did not find in public sources: a; b; c" -> ["a", "b", "c"] (the date lives in the heading). */
export function splitNotFound(text: string): string[] {
  const i = text.indexOf(':');
  if (i < 0) return [text];
  return text
    .slice(i + 1)
    .split(';')
    .map((s) => s.trim().replace(/\.$/, ''))
    .filter(Boolean)
    .map((s) => s.replace(/^(['"‘“]?)(\p{L})/u, (_m, q: string, c: string) => q + c.toUpperCase()));
}

/** Human-readable label for an evidence reference key ("D1:R03028", "features", "cluster", "case"). */
export function evidenceKey(ref: string): string {
  const colon = ref.indexOf(':');
  if (colon >= 0) {
    const dot = ref.indexOf('.', colon);
    return dot < 0 ? ref : ref.slice(0, dot);
  }
  return ref.split(/[.[]/)[0];
}

// ------------------------------------------------------------------ queue slices (Queue + Radar redesign)

export interface QueueSliceParams {
  triage?: string;
  route?: string;
  cluster?: string;
  limit?: number;
  offset?: number;
}

/** GET /api/queue with route/limit/offset. In mock mode the mock queue is filtered and sliced locally. */
export async function getQueueSlice(p: QueueSliceParams = {}): Promise<QueueResponse> {
  if (!USING_MOCKS) {
    const url = `${API_BASE}/api/queue${qs({ ...p })}`;
    const hit = queueCache.get(url);
    if (hit && Date.now() - hit.at < 15000) return hit.p;
    const pr = getJson<QueueResponse>(url);
    pr.catch(() => queueCache.delete(url));
    queueCache.set(url, { at: Date.now(), p: pr });
    return pr;
  }
  const all = await getQueue({ triage: p.triage, cluster: p.cluster });
  const items = all.items.filter((i) => !p.route || i.route === p.route);
  const off = p.offset ?? 0;
  return { counts: all.counts, items: items.slice(off, off + (p.limit ?? 500)), total_matching: items.length };
}

/** Members of several radar clusters, keyed by cluster id (one request per cluster). */
export async function getClusterMembers(clusterIds: string[]): Promise<Record<string, QueueResponse['items']>> {
  const res = await Promise.all(clusterIds.map((c) => getQueueSlice({ cluster: c, limit: 2000 })));
  return Object.fromEntries(clusterIds.map((c, i) => [c, res[i].items]));
}

// ------------------------------------------------------------------ Grafana (Metrics screen panels)
/** Grafana instance with the provisioned `staj-eval` dashboard (infra/grafana). Override with VITE_GRAFANA_URL. */
export const GRAFANA_BASE = ((import.meta.env.VITE_GRAFANA_URL as string | undefined)?.trim() || 'http://127.0.0.1:3000').replace(/\/$/, '');

/** Solo-panel embed URL for one panel of the evaluation dashboard. */
export function grafanaPanelUrl(panelId: number): string {
  return `${GRAFANA_BASE}/d-solo/staj-eval/eval?orgId=1&panelId=${panelId}&theme=light&kiosk`;
}

/** True when Grafana answers. Uses an opaque (no-cors) request, so only reachability is checked. */
export async function grafanaReachable(timeoutMs = 2500): Promise<boolean> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    await fetch(`${GRAFANA_BASE}/api/health`, { mode: 'no-cors', cache: 'no-store', signal: ctl.signal });
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** Fetch the Markdown export and hand it to the browser as a file (works across the API origin). */
export async function downloadOpoMarkdown(id: string): Promise<void> {
  const r = await fetch(opoExportUrl(id));
  if (!r.ok) throw new ApiError(r.status, `${r.status} ${r.statusText}`);
  const blob = new Blob([await r.text()], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `report_draft_${id}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ------------------------------------------------------------------ case brief (Case screen)
/** The short auto-written case summary. Pre-generated for top cases; otherwise written on demand (up to ~60 s). */
export interface CaseBrief {
  sentences: Sentence[];
  violations: (Record<string, unknown> | string)[];
  model_id?: string;
  attempts?: number;
  cached?: boolean;
}

const briefInflight = new Map<string, Promise<CaseBrief>>();

/** POST /api/cases/{id}/brief, de-duplicated so StrictMode double effects make one model call. */
export function writeBrief(id: string): Promise<CaseBrief> {
  if (USING_MOCKS) return Promise.reject(new ApiError(503, 'Summary is not available in mock mode'));
  const hit = briefInflight.get(id);
  if (hit) return hit;
  const p = sendJson<CaseBrief>('POST', `/api/cases/${encodeURIComponent(id)}/brief`).finally(() => briefInflight.delete(id));
  briefInflight.set(id, p);
  return p;
}
