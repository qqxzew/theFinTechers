# Stáj – architecture and threat model

All data is synthetic. "Implemented" below means: present in this repository and exercised by a test or by `eval/`. "Planned" means described, not built.

## 1. Components

| Component | Where | State |
|---|---|---|
| Bank node (per bank: features → FINREG rules A/B/C → detectors D1–D8 → innocence layer → case builder → token export) | `node/` | implemented; **3 banks run in one process** in `eval/` and `api/` (the data separation is real: each node receives only its own bank's rows) |
| Radar coordinator (pairwise DH-PSI sessions, clustering, guards) | `radar/` | implemented in-process; **HTTP node/radar services and `docker compose` are planned** |
| Audit (append-only SHA-256 hash chain) | `audit/` | implemented, tamper detection tested |
| Copilot (Bedrock Converse: explanation CS/EN, OPO section V, 4 tool-using agents) | `copilot/` | implemented; agents tested with a scripted client, live runs recorded in `orchestrator/runs/` |
| Governance (conflict-of-interest, four-eyes, escalation routing, FINREG CSV) | `escalation/`, `export/`, `api/` | implemented |
| API + UI | `api/`, `ui/` | implemented (FastAPI; React/Vite) |
| Red team (scheme generator) | `redteam/` | implemented, isolated from the blue side |

```
 bank node B1 ─┐                       ┌─ Copilot (Bedrock, read-only tools, proposals only)
 bank node B2 ─┼─ blinded PSI msgs ─►  Radar coordinator ─► cluster ids, counts  ─► nodes
 bank node B3 ─┘   (hex group elements) └─ Audit chain (every model call, tool call, decision, PSI session)
                                         API ─► UI (analyst workspace; humans confirm or override)
```

## 2. What crosses a node boundary
Only (a) blinded DH-PSI group elements, (b) after a match: keyed token ids (HMAC under an epoch key the coordinator does not hold), bank-local pseudonymous candidate refs, a rarity value and coarse lag/retention buckets, (c) the coordinator's answer: cluster id, number of other banks, number of other candidates, matched token ids. Never names, raw transactions or other banks' client ids. `tests/integration/test_radar_e2e.py` asserts that no plaintext token appears in any message that crossed.

## 3. PSI protocol (radar/psi/dh_psi.py)
Diffie-Hellman PSI over the RFC 3526 2048-bit MODP group: `H(x)` = domain-separated, SHA-256-expanded hash reduced mod p and squared (lands in the order-q subgroup). Per session each party draws a fresh secret exponent. A sends shuffled `H(x)^a`; B returns `(H(x)^a)^b` in received order and shuffled `H(y)^b`; A computes `(H(y)^b)^a` and intersects; A returns its double-blinding so B learns the intersection too (or cardinality-only mode). Elements outside the prime-order subgroup are rejected. Property tests: output equals the plain set intersection for random sets; blinded messages differ per session and contain no plaintext.
**Security model: semi-honest.** A malicious party can (1) submit arbitrary tokens to probe whether a target account is a candidate elsewhere, (2) poison with fake tokens, (3) abort after learning. PSI minimises what is shared; **it is not a legal basis** for sharing (banking secrecy § 38 Act 21/1992; EU AMLR Art. 75 partnerships apply from 10 July 2027 and need supervisor notification and a DPIA). AWS Clean Rooms (cryptographic computing) or Nitro Enclaves are hardened alternatives and are **not used here**.

## 4. Threat model

| Threat | Attack | Mitigation | State |
|---|---|---|---|
| Probing | A bank submits one or few tokens to learn whether a specific account is flagged elsewhere | minimum candidate-set size (5), refusal of singleton probes, per-bank rate limit, disclosure only for clusters with ≥ 2 banks and ≥ 3 candidates, per-query audit entry at both ends | implemented (`radar/guards.py`, `radar/sessions.py`) |
| Poisoning | A bank injects fake tokens to frame an account or create a cluster | candidate sets only from scored cases (refusal if > 20 % of tokens are unscored); cluster disclosure needs ≥ 3 candidates across ≥ 2 banks; humans decide, a cluster never decides alone; audit trail names the submitting bank | partly implemented; cross-checking submitted scores against the bank's own case log is planned |
| Replay | Re-sending an old blinded set | fresh exponent per session; session ids and epoch key rotation | per-session exponent implemented; epoch rotation is a config value in the demo |
| Collusion | Two banks pool their view to learn a third bank's candidates | pairwise sessions; coordinator never forwards another bank's tokens; matches are reported as keyed ids | pairwise design implemented; formal analysis not done |
| Coordinator compromise | Coordinator tries to learn plaintext tokens or customers | sees only blinded elements and keyed token ids, no customer ids; epoch key held by banks | implemented (design); a compromised coordinator can still mount traffic analysis |
| Model abuse / prompt injection | Crafted counterparty strings try to steer the LLM | LLM receives only a structured case JSON with whitelisted aggregate features, treats all fields as data, every sentence must cite a signal id or field, validator rejects unsupported numbers/refs | implemented (`copilot/qa.py`, prompts) |
| LLM overreach | Agent changes a score or closes a case | tools are read-only except `propose_*` / `draft_*`; engine owns scores; only a human decision (API/UI) changes status; hard step/token/cost/time limits | implemented and tested |
| Tipping-off | Customer-facing text reveals a report | no customer-facing generator in the product; the QA validator blocks reporting vocabulary in customer-facing mode | implemented |
| Insider self-review | Decider is relationship owner / rule author / first triager | conflict engine + four-eyes above a priority threshold, every rejection audited | implemented (`escalation/conflicts.py`, `api/server.py`) |
| Audit tampering | Edit or delete a log entry | hash chain; `GET /api/audit/verify` and `audit.log.verify_chain` | implemented; the log file itself is not write-protected storage |

## 5. Production notes (not implemented)
Per-bank processes with mutual TLS and the bank's own key store, passwordless service identities, AWS Clean Rooms or Nitro Enclaves for the PSI step, write-once audit storage (e.g. S3 Object Lock), Bedrock AgentCore for agent runtime and observability, data-flow lineage into the bank's AML case-management system as a sidecar.
