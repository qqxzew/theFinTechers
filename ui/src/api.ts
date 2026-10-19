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
