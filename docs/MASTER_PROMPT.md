# STÁJ — Master Build Prompt for Autonomous Agents

You are a team of autonomous senior engineers building **Stáj**: a privacy-preserving, cross-bank money-mule radar with an analyst copilot. Build the best possible version. Do not cut scope because something is "hard". Do cut anything that is fake, unverifiable or dishonest.

Read this whole document before writing any code. When this document and your own judgement disagree, follow this document unless it is factually wrong about the data; then record the conflict in `docs/DECISIONS.md` and proceed with the correct behaviour.

---

## 0. Mission in one sentence

Every bank sees only a fragment of a money-mule network, and recruiters rely on that. Stáj lets banks see the whole network — the "stable" (*stáj*) behind the mules (*bílí koně*) — **without exchanging a single customer record**, and gives the analyst an explainable, auditable case plus a draft suspicious-transaction report for the Czech FIU (FAÚ).

---

## 1. Context you must understand

### 1.1 Event
- Fintech hackathon "$ hackathon_" by The FinTechers, Prague, 19–20 Oct 2026.
- Track 5 — Compliance & RegTech. Challenge: **Transaction monitoring copilot**.
- Hackathon rules: synthetic data only, no real PII. Mark the start of work with a git tag `hackathon-start`. README must state "Built during the hackathon". Commit small and often.

### 1.2 Jury (design for them)
| Juror | What they will probe |
|---|---|
| Director of ICT & AML/CFT supervision, Czech National Bank (CISA auditor) | Auditability, data minimisation, governance, no self-review, honest limits |
| CTO, Partners Banka (passwordless multicloud bank, member of the planned Czech interbank mule-sharing scheme Safe-D) | "Is this a wrapper?", production realism, identity, cloud architecture |
| Mastercard cyber security lead CZ/SK | Attacks on the system itself (probing, poisoning), threat-intel thinking |
| Deloitte consulting partners (core banking, AI & cloud) | Integration as a sidecar, delivery realism, AI architecture |
| AWS | Meaningful use of AWS (Bedrock), architecture quality |
| KB SmartSolutions (bank venture arm), Elevator Ventures (Raiffeisen fintech VC) | Business model, network effects, market |

### 1.3 Judging criteria (weights)
- Impact & relevance 25 %
- Technical execution 25 %
- Innovation beyond a thin GPT wrapper 20 %
- Responsible AI & compliance-readiness 15 %
- Business viability & pitch 15 %

**Implication:** the core engine must be deterministic, explainable logic plus real cryptography. The LLM explains, drafts and navigates rules. It never scans raw rows and never makes the final decision.

### 1.4 What already exists (do not claim to be first)
- Device/behaviour mule detection: ThreatMark (Brno, used by 12 banks in CZ), BioCatch.
- Generic AML copilots: Hawk, Lucinity (SAR drafting).
- Cross-bank sharing in readable form: Salv Bridge, Czech Safe-D (planned, needs banking-secrecy change).
- Privacy-preserving pilots: Swift + 13 banks (PETs + federated learning, synthetic data), Feedzai (federated learning).

**Our defensible gap (state it as "not found in public sources as of 19 Oct 2026"):**
1. A catalogue of Czech/CEE mule schemes encoded as detectors.
2. Explicit honest look-alike personas with a separator per persona ("mom or mule").
3. "Same hand" (one operator) detection from transactions alone.
4. PSI-based cross-bank matching of mule exit tokens.
5. A draft FAÚ report structured by FAÚ Methodological Guideline No. 4.

### 1.5 Regulatory anchors (use exactly, do not embellish)
- Czech AML Act 253/2008 Coll.: § 18 reporting to FAÚ; § 18(3) the report must not name the employee who detected the transaction.
- FAÚ Methodological Guideline No. 4 (Aug 2025): 10-section structure of a suspicious-transaction report (OPO). Attempts must be reported too.
- Czech banking secrecy: § 38 of Act 21/1992 Coll.
- EU AMLR (Regulation 2024/1624): in force 9 July 2024; Art. 75 information-sharing partnerships apply from 10 July 2027, require notifying the supervisor and a DPIA, and allow sharing only where strictly necessary.
- EU PSR: political agreement 27 Nov 2025, final texts April 2026; mandatory fraud-data sharing between PSPs; PSP liability when fraud prevention is inadequate.
- **PSI minimises what is shared. It does not replace a legal basis.** Never write that PSI "makes sharing legal" or "bypasses banking secrecy".

---

## 2. Non-negotiable rules

1. **Raw transactions never leave a bank node.** Between nodes travel only blinded PSI messages and, after a match, minimal case context defined in §6.4.
2. **Humans decide.** The system proposes triage, priority, escalation and drafts. A named human role confirms. Four-eyes for high-priority cases.
3. **No self-review.** The person deciding a case must not be the relationship owner of the client, nor the author of the rule that fired, nor the person who first triaged it.
4. **Everything is logged** in an append-only, hash-chained audit log: who, when, what, why, rule version, model version, input hash.
5. **Fairness.** Client nationality and client country never raise a score on their own. Country raises risk only through the EU/FATF high-risk jurisdiction lists (rule B). Age is not in the data and must not be inferred.
6. **No tipping-off.** Any customer-facing text must never reveal that a report was or may be filed.
7. **The FAÚ draft never contains the analyst's name.** The contact person is a separate block from bank settings.
8. **LLM grounding.** The LLM receives only a structured case JSON. Every factual sentence it writes must reference a signal ID or field from that JSON. It must say "not available" rather than invent.
9. **Honesty.** Synthetic data is labelled as synthetic everywhere. Planted schemes are labelled as planted. Every metric is computed by code and written to a generated report. No hand-typed numbers in the UI or slides. Show errors, not only successes.
10. **Red/blue separation.** The scheme generator (red team) and the detectors (blue team) are separate packages. Detector code must not import, read or inspect generator code, parameters or labels. Labels are used only by the evaluation harness.

---

## 3. Data

### 3.0 Data acquisition (do this first)
Agents fetch data themselves, but credentials come from the human. If a credential is missing, **stop and ask the human**. Never invent or simulate a dataset that is supposed to be downloaded.

Prerequisites the human provides once:
- AWS: an SSO profile already logged in (`aws sso login --profile <PROFILE>`), exported as `AWS_PROFILE` in `.env`.
- Kaggle: `~/.kaggle/kaggle.json` (API token from the human's Kaggle account).

Commands:
```bash
# ČNB (shared hackathon bucket, eu-central-1)
aws s3 cp s3://ai-hackathon-datasets-422928733782/CNB/ data/raw/cnb --recursive --profile "$AWS_PROFILE"

# IBM AMLworld (smallest high-illicit variant + its patterns file)
pip install kaggle
kaggle datasets download -d ealtman2019/ibm-transactions-for-anti-money-laundering-aml \
  -f HI-Small_Trans.csv -p data/raw/ibm --unzip
kaggle datasets download -d ealtman2019/ibm-transactions-for-anti-money-laundering-aml \
  -f HI-Small_Patterns.txt -p data/raw/ibm --unzip
```
If the Kaggle file names differ, list the dataset files first (`kaggle datasets files ealtman2019/ibm-transactions-for-anti-money-laundering-aml`) and pick the smallest high-illicit transactions file and its patterns file.

After download:
- Write `data/MANIFEST.json`: file, size, SHA-256, row count, column list, download time.
- Verify the ČNB row counts against §3.1 (397,853 transactions, 5,493 clients). If they differ, record it in `docs/DECISIONS.md`.
- Add `data/` to `.gitignore`. Raw data is never committed.
- The red-team dataset (§3.4) is generated locally, never downloaded.

### 3.1 ČNB dataset (primary, Czech context)
Location: `s3://ai-hackathon-datasets-422928733782/CNB/` (eu-central-1). Two semicolon-separated files, UTF-8 with BOM (`encoding="utf-8-sig"`). Dates `dd.mm.yyyy`, times `HH:MM:SS`.

**transactions** (397,853 rows, 1–31 July 2026). Header:
`transaction ID;client ID;date;time;volume;currency;country of payer;country of payee;account of payer;account of payee;type of transaction`

Facts established by analysis (verify, then rely on them):
- Types: `outgoing payment` (187,152), `incoming payment` (170,986), `remittance` (39,715).
- The client's own account is written as the client ID (`K003797`). External accounts look like `A` + ISO country + 5 digits (`ACZ00172`).
- Incoming: payer = external, payee = client. Outgoing: payer = client, payee = external.
- **Remittance = outgoing cross-border transfer**: payer account empty, payer country = client country in 100 % of rows, payee country ≠ client country, payee account external.
- Clients never pay each other directly. All links between clients go through shared external accounts.
- ~5,380 external accounts. Clients per external account: median 9, p99 ~1,311, max 1,372. High-degree accounts behave like utilities/merchants/employers.
- Network tests: client→external→client relay matches are at shuffled-baseline level (79 real vs 62 shuffled). **The dataset contains no mule networks.** Do not pretend otherwise.
- Currencies: CZK, EUR, USD, PLN, CNY, HUF, RON, GBP, SEK, DKK, CHF, JPY, TRY, NOK, KRW, AUD, BRL, CAD, INR, ISK, MXN, SGD, ZAR. Convert all to CZK.

**clients** (5,493 rows). Header:
`client ID;country of client;date of contract;contract concluded;PEP;type of client;expected volume of transactions at thetime of contract conclusion [CZK];expected number of transactions at the time of contract conclusion;real volume of transactions in 2Q2026 [CZK];real number of transactions in 2Q2026;maximal volume of transaction in 2Q2026 [CZK];AML risk score`

Values: `contract concluded` ∈ {in person, distant form}; `PEP` ∈ {Y, N}; `type of client` ∈ {natural person, legal entity, enterpreneur} (keep the source spelling in data, display correct spelling); `AML risk score` ∈ {low, medium, high}. Contract dates 13 Jan 2020 to 30 Jun 2026 (428 contracts in 2026, 67 in June 2026, none in July).

**Known ambiguity:** with "expected volume" read as monthly and Q2 values as quarterly totals, rule A fires on all clients. July activity per client is roughly 3× a Q2 month. Make the unit interpretation of these columns a config option (`monthly | quarterly | yearly`), implement all, log alert counts for each, and default to the one that yields a plausible alert rate. Record the choice in `docs/DECISIONS.md`.

### 3.2 FINREG rules on the ČNB data (implement exactly, all thresholds configurable)
- **Rule A — profile discrepancy (one alert per client):** daily July volume > 25 % of projected monthly volume, OR > 3× average daily Q2 volume, OR a single transaction > 2× Q2 maximum. Clients inactive in Q2 compared with projected volume only. Client volume = sum of all transactions regardless of direction.
- **Rule B — high-risk jurisdiction / PEP (one alert per transaction):** a transaction > CZK 10,000 where payer, payee or client country is on the EU or FATF high-risk lists; or an outgoing (or direction-unclear) transaction > CZK 100,000 by a PEP.
- **Rule C — flow-through (one alert per client):** incoming > CZK 100,000 within 24 h, and within 6 h outgoing ≥ 80 % of that amount to accounts other than the payers. Make the 6 h anchor configurable (`threshold_crossing | first_inflow`), default `threshold_crossing`.
- FX: config file `config/fx.yaml`. Ship ČNB-style rates for July 2026 as clearly marked placeholders; the UI shows "FX: placeholder" until replaced.
- High-risk lists: `config/high_risk_jurisdictions.yaml` with source URL and date per list.

### 3.3 IBM AMLworld (network ground truth)
- Source: Kaggle `ealtman2019/ibm-transactions-for-anti-money-laundering-aml` (Altman et al., NeurIPS 2023 Datasets & Benchmarks). Start with the smallest high-illicit variant (`HI-Small`) and its patterns file.
- Expected columns (verify on download): timestamp, from bank, from account, to bank, to account, amounts and currencies paid/received, payment format, is-laundering label. The patterns file groups laundering transactions into attempts with a pattern type (fan-out, fan-in, gather-scatter, scatter-gather, cycle, random, bipartite, stack).
- **Bank split:** map bank IDs into N simulated banks (default N = 5) by stable hashing, keeping each bank's accounts together. Each bank node receives only transactions where one side is its own account. The counterparty at another bank appears as an external token `bank_id:account_id`, exactly as an IBAN would appear in reality.
- Labels go only to `eval/`. Bank nodes never see them.
- These are generic laundering patterns, not Czech mules. Say exactly that in docs and UI.

### 3.4 Czech scheme generator (red team, isolated package `redteam/`)
Purpose: show the Czech mule-scheme library on data with known answers. Built from the ČNB distributions so the "normal life" background is theirs.
- Generates K synthetic banks (default 3) with shared external accounts, normal clients sampled from ČNB distributions (amounts, times, counterparty-degree structure, client attributes), plus planted schemes and honest look-alikes.
- **Planted schemes (each with a source citation in its docstring):**
  1. Day-zero handover account: opened recently (often in person), no life before a large third-party inflow, ≥ 90 % out within 24 h.
  2. Same hand: 5–30 accounts across banks with the same inflow→outflow lag, the same retention ratio k (fixed "commission"), shared rare exits, the same active hours.
  3. Fixed skim chain: outflow ≈ inflow × (1 − k), k stable over cycles.
  4. Business-to-personal invoice mule: company payers into a fresh personal account, fast onward transfers abroad.
  5. Victim draining own savings (fake-banker scheme): must be routed to victim protection, not labelled a mule.
- **Honest look-alikes to plant:** migrant with monthly remittances to the same recipient; students splitting rent; second-hand seller with many small irregular inflows; group collection paying one organiser; fixed-commission middleman (co-host); freelancer on a personal account; fundraiser for a relative.
- Parameters randomised within documented ranges. Seeded. Writes data and a hidden `labels.parquet`.
- The detector team must never read this package. Enforce with an import-linter rule and a CI check.

### 3.5 Canonical internal schema
All sources normalise to:
`tx_id, bank_id, client_id (pseudonymous), ts (UTC), amount_czk, amount_orig, currency, direction {in, out, remit_out}, own_account, counterparty_token, payer_country, payee_country, channel_type, source_dataset`
and a client table:
`client_id, bank_id, client_country, contract_date, contract_form, pep, client_type, expected_volume, expected_count, q2_volume, q2_count, q2_max, aml_risk, source_dataset`
(IBM has no client table; derive minimal pseudo-profiles from the first part of the time range and mark them as derived.)

---

## 4. Architecture

```
            ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
            │  Bank node A │     │  Bank node B │     │  Bank node C │   (one process each,
            │  data stays  │     │  data stays  │     │  data stays  │    own storage, own key)
            │  detectors   │     │  detectors   │     │  detectors   │
            │  case builder│     │  case builder│     │  case builder│
            └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
                   │  blinded PSI messages only (pairwise)   │
                   └──────────────┬─────────────────────────┘
                          ┌───────┴────────┐
                          │ Radar          │  orchestrates PSI sessions, holds only
                          │ coordinator    │  match results and cluster IDs, no records
                          └───────┬────────┘
                   ┌──────────────┴──────────────┐
          ┌────────┴────────┐          ┌─────────┴────────┐
          │ Copilot service │          │ Audit service    │  append-only,
          │ (AWS Bedrock)   │          │ hash-chained     │  per bank + radar
          └────────┬────────┘          └─────────┬────────┘
                   └──────────────┬──────────────┘
                          ┌───────┴────────┐
                          │ Web UI         │  analyst workspace, radar view,
                          │                │  metrics, audit viewer
                          └────────────────┘
```

**Stack**
- Python 3.12, FastAPI, Pydantic v2, Polars (or pandas where simpler), DuckDB for analytics, SQLite per node for state, NetworkX for graphs.
- Crypto: Python `cryptography` / `hashlib` plus your own audited DH-PSI implementation (§6.1). No unvetted crypto libraries.
- LLM: AWS Bedrock, region `eu-central-1`, Converse API via boto3 (including tool use). All model IDs live in `config/models.yaml`, never in code:
  - `agent_primary`: `global.moonshotai.kimi-k3` (default for the investigation agents and narratives).
  - `fallback`: a Claude Sonnet 4.5 `eu.` inference profile.
  - `bulk`: a Claude Haiku 4.5 `eu.` inference profile (short explanations at volume).
  - On startup, verify every configured ID with `aws bedrock list-inference-profiles` / `list-foundation-models` and a one-call smoke test including tool use. If `agent_primary` is unavailable or fails tool use, switch to `fallback`, log it to the audit chain and show it in the UI. Never guess an ID.
- Frontend: React + TypeScript + Vite + Tailwind, Cytoscape.js for graphs, Recharts for charts.
- Orchestration: `docker compose up` starts 3 bank nodes, radar, copilot, audit, UI. A `make demo` target seeds data and runs the full pipeline.
- Tests: pytest, hypothesis (property tests), ruff, mypy (strict on core packages), import-linter.

**Repository layout**
```
stáj/
  README.md  ARCHITECTURE.md  METHODOLOGY.md  DATA.md  LIMITATIONS.md  docs/DECISIONS.md
  config/            fx.yaml, high_risk_jurisdictions.yaml, thresholds.yaml, escalation_matrix.yaml, units.yaml, models.yaml
  ingest/            cnb.py, ibm.py, redteam_loader.py, normalise.py, bank_split.py
  redteam/           (ISOLATED) generator, schemes/, lookalikes/, labels writer
  node/              features/, rules/ (A, B, C), detectors/, innocence/, cases/, tokens/, api.py
  radar/             psi/, sessions.py, clustering.py, guards.py, api.py
  copilot/           agents/ (triage, investigation, narrative, qa), tools/ (case-scoped, read-only + proposals),
                     prompts/, schemas/, bedrock_client.py, model_registry.py, budgets.py, explain.py, opo_draft.py
  audit/             log.py (hash chain), verify.py, api.py
  escalation/        matrix.py, conflicts.py
  export/            finreg_csv.py, opo_export.py
  eval/              harness.py, metrics.py, ablations.py, report.py
  ui/                React app
  tests/             unit/, property/, integration/, fixtures/
  infra/             docker-compose.yml, Makefile, .env.example
```

---

## 5. Bank node (blue team)

### 5.1 Features (per client, computed locally)
Turnover in/out by window (1 h, 6 h, 24 h, 7 d, month); counts; distinct and **new** counterparties; inflow→outflow lag distribution; retention ratio per inflow cycle; share of outflow to rare (degree ≤ 3), mid and popular (degree ≥ 100) counterparties; remittance regularity (same recipient count, interval regularity); profile gap (July vs expected and vs Q2 under the configured units); days since contract; contract form; PEP; client type; AML risk; just-below-threshold amount pile-ups found empirically (do not hard-code 9,999).

Counterparty degree is computed within each bank only (a bank cannot see others' customers). The radar adds cross-bank context later.

### 5.2 Detectors
Every detector is a pure function with a fixed interface:
`detect(client_features, context) -> list[Signal]` where `Signal = {signal_id, detector_id, version, client_id, score 0–1, evidence: list[field refs], explanation_template_key, source}`.
Thresholds are percentiles of the bank's own population unless a regulator rule fixes them. Each detector has its source citation (or "own design") in its docstring and in `METHODOLOGY.md`.

| ID | Detector | Core logic |
|---|---|---|
| R-A, R-B, R-C | FINREG rules A, B, C | Exactly §3.2 |
| D1 | Flow-through+ | Rule C plus: senders mostly new, exits rare, repetition, lag tightness |
| D2 | Day-zero handover | Recent contract, few "life" events before first material third-party inflow, ≥ 90 % drained within 24 h; contract form as a modifier, not a verdict |
| D3 | Profile discrepancy+ | Rule A plus direction of the gap (inflow-driven vs spending-driven) |
| D4 | New-sender fan-in | ≥ N new unrelated senders in a short window, amounts not item-like |
| D5 | Rare-exit concentration | High share of outflow to rare counterparties after third-party inflows |
| D6 | Same hand (local) | Groups of own clients sharing rare exits **and** similar lag **and** similar retention ratio **and** similar active hours; scored against a shuffled baseline |
| D7 | Fixed skim | Outflow ≈ inflow × (1 − k), k stable (± 1–2 pp) over ≥ 3 cycles, k ≥ 1 % |
| D8 | Structuring | Amount pile-ups just below empirically found thresholds |

Card, ATM, merchant, device and IP detectors are out of scope for the data we have. Define the interface and list them in `LIMITATIONS.md` as production extensions; do not fake them.

### 5.3 Innocence layer ("Máma, nebo kůň?")
Produces `Exculpatory` signals that lower a score and are shown next to the suspicion:
- E1 Mom: recurring remittances or transfers to the same recipient(s), stable amounts, funded by recurring inflows.
- E2 Life: a meaningful share of outflow to popular counterparties (relative, not "any").
- E3 Source of funds: money leaving to a risky exit came from the client's recurring income, not from new third parties hours earlier.
- E4 Institutional counterparty: high-degree payer or payee (employer, insurer, platform).
- E5 Reciprocity: flows in both directions with the same counterparties.
- Victim route: own-savings draining with no third-party inflow → `VictimProtection` case, never `Mule`.

### 5.4 Case builder, scoring, triage
- Cluster signals per client into one case. One alert per FINREG rule type for the export, one case per client for the analyst.
- Score: transparent additive log-odds (points per signal, minus points per exculpatory signal), weights in `config/thresholds.yaml`, each weight justified in `METHODOLOGY.md`. No black-box model in the decision path. An optional ML model may be trained on red-team labels **for evaluation only**, reported separately.
- **Priority 0–100** uses the FINREG factors: AML risk score, PEP, country, amount/volume, conduct discrepancy, relationship length, form of contract, multiple flags on the same client, plus radar cluster membership.
- **Triage:** `FP` or `REVIEW` with a reason list (every reason references signal IDs). A case is auto-closed as FP only if its priority is below a threshold **and** at least one exculpatory signal explains every suspicious signal. Everything else goes to REVIEW.

### 5.5 Token export to the radar
- Candidate set: clients in a configurable score band, including sub-threshold ("weakly suspicious") ones. Never the whole customer base.
- Tokens: exit counterparty tokens of the candidate's suspicious outflows, optionally coarse time buckets (day). Optionally source tokens of suspicious inflows.
- Minimum candidate-set size to blunt inference; rate limits per session.

---

## 6. Radar (cross-bank, privacy-preserving)

### 6.1 PSI protocol
- Diffie-Hellman PSI over the RFC 3526 2048-bit MODP group (safe prime p). Hash tokens with a domain-separated SHA-256 to an integer mod p, then square to land in the prime-order subgroup.
- Per session, each node draws a fresh secret exponent. Node A sends shuffled `H(x)^a`. Node B returns `(H(x)^a)^b` in received order plus shuffled `H(y)^b`. A computes `(H(y)^b)^a` and intersects. Then symmetric so both learn the intersection, or cardinality-only mode.
- Security model: semi-honest. Document what a malicious party could do and the mitigations (§6.3).
- Property test: for random sets, PSI output equals the plain set intersection. Benchmark messages and time for 1k, 10k, 100k tokens.
- Production note in docs: AWS Clean Rooms (cryptographic computing) or Nitro Enclaves as hardened alternatives. Do not claim they are used if they are not.

### 6.2 Clustering
- Build a cross-bank graph whose nodes are (bank, pseudonymous candidate) and matched exit tokens. Clusters are connected components with edge weights by token rarity.
- **Cluster score** combines: number of banks, number of candidates, token rarity, and, after the minimal exchange in §6.4, cross-bank lag and retention-ratio similarity (Same hand, global).
- Disclosure threshold: reveal a cluster only if it spans ≥ 2 banks and ≥ 3 candidates.

### 6.3 Guards against abuse
Rate limits; candidate sets only from scored clients; per-query audit entries at both ends; no free-text search; refusal to answer singleton probes; detection of suspicious query patterns (a bank submitting many unscored tokens). Write a threat model in `ARCHITECTURE.md` (probing, poisoning with fake tokens, replay, collusion, coordinator compromise) with a mitigation per threat.

### 6.4 Minimal post-match exchange
For disclosed clusters only, each involved bank receives: cluster ID, number of other banks, number of other candidates, the matched token(s), and coarse lag/ratio statistics. Never names, never raw transactions, never other banks' client IDs.

### 6.5 Baselines for the metric
Implement three modes, the same pipeline: `isolated` (no sharing), `stáj_psi`, `naive_raw_sharing` (an upper bound that ships raw data, used only to show we lose little and expose far less). Report records and bytes exposed per mode.

---

## 7. Copilot and autonomous investigation agents (AWS Bedrock)

### 7.0 Agent design
Each bank node runs its **own** investigation agent inside its perimeter. The agent sees only that bank's cases and only through tools. There is no agent with access to more than one bank.

Agents (Bedrock Converse with tool use, model from `config/models.yaml`):
| Agent | Job | Tools it may call |
|---|---|---|
| Triage agent | Works through the alert queue, groups alerts into cases, proposes triage and priority | `get_case`, `get_signals`, `get_exculpatory`, `get_features`, `explain_rule`, `propose_triage` |
| Investigation agent | For REVIEW cases: builds the story, checks honest look-alikes, asks the radar for cluster context | `get_case`, `get_timeline`, `get_local_graph`, `get_cluster_context`, `check_lookalike(persona)` |
| Narrative agent | Writes the Czech/English explanation and the OPO draft | `get_case`, `get_cluster_context`, `draft_opo_section` |
| QA agent | Checks every draft against the case JSON: unsupported claims, missing signal references, analyst name present, tipping-off wording | `get_case`, `validate_draft` |

Hard limits for all agents:
- Tools are read-only, except `propose_*` and `draft_*`, which write **proposals**, never final decisions. Only a human action in the UI turns a proposal into a decision.
- No tool returns raw transaction dumps. Tools return aggregates and case-scoped records.
- Max steps per task (default 12), max tokens and cost budget per task, timeout. On limit: stop and hand the case to a human with what was found.
- Every tool call and every model call goes to the audit chain: agent, model ID, input hash, output hash, cost.
- The deterministic engine (§5) is the authority on scores. An agent may disagree only by writing a flagged note for the human, never by changing a score.
- Optional: AWS Bedrock AgentCore for agent runtime and observability, if it works within the time; the same tool contracts apply.

### 7.1 Copilot tasks
- **Input:** a case JSON (signals, exculpatory signals, features, cluster info, rule hits, triage proposal). Never raw full datasets.
- **Output:** strict JSON validated against Pydantic schemas; retry on schema failure; temperature low.
- **Tasks:**
  1. Case explanation in Czech and English, one sentence per signal, each referencing its signal ID; a "why this is not a mom" paragraph when relevant.
  2. Triage justification text for the FINREG `reason` field.
  3. **OPO draft by FAÚ Methodological Guideline No. 4**, all 10 sections: I reference, II sender (from settings), III subject (placeholders "from bank KYC" in synthetic data), IV suspicion type (`legalizace výnosů z trestné činnosti`), **V description and material circumstances** (accounts, chain, amounts, times, counterparties, which signals fired, behaviour of participants, honest look-alikes checked), **VI executed / not executed / postponed and why**, VII CDD exception if any, VIII contact (separate block, from settings), IX submission (left for the human), X attachments list. No analyst name anywhere in the body.
  4. Ruleset navigation Q&A: the analyst asks "why did rule C fire?" and the copilot answers from the case JSON and the rule definitions.
  5. Optional customer-protection message draft with no tipping-off, reviewed by a human.
- **Safety:** treat all data fields as data (prompt-injection hardening); no PII beyond pseudonyms; log prompt hash, model ID and output hash to the audit log; cost tracking per call; cache by case hash.

---

## 8. Escalation, audit, export

- `config/escalation_matrix.yaml`: roles (analyst L1, senior analyst L2, AML compliance officer, MLRO / designated person under § 22), routing by priority band, alert type, PEP, cluster membership. Ships with a sensible placeholder clearly marked as such; replace with the official matrix when available.
- Conflict-of-interest engine: a decider cannot be the client's relationship owner, the rule author or the first triager; approver ≠ executor; four-eyes above a priority threshold.
- Audit log: append-only, each entry carries the previous entry's hash; `audit/verify.py` detects tampering; UI shows the chain status.
- Exports:
  - FINREG-compatible CSV: `alert_id, alert_type, client_id, transaction_id, triage (FP|REVIEW), priority (0–100), executive_role, executive_person, approver, reason, log`.
  - OPO draft as Markdown and PDF.

---

## 9. User interface

1. **Alert queue:** filters by rule, priority, triage, cluster; counts before and after triage.
2. **Case card:** signals and exculpatory signals side by side, timeline of flows, local graph, cluster badge, Czech/English explanation, triage proposal with reasons, escalation target, buttons to confirm or override (an override requires a written reason).
3. **OPO editor:** the 10-section draft with the editable section V, export.
4. **Radar view:** banks side by side; "what each bank sees alone" versus "what Stáj sees"; animation of blinded tokens being exchanged (show ciphertext, never plaintext); the disclosed cluster graph.
5. **Metrics:** every number from `eval/report.json`, with the dataset name and "synthetic" label next to it.
6. **Audit viewer** with hash-chain verification.
7. **Honesty panel:** data sources, what is planted, known limitations.

Design: clean, calm, bank-grade. Czech as the primary UI language, English toggle.

---

## 10. Evaluation (generated, reproducible, seeded)

- **IBM AMLworld split:** precision, recall and F1 of laundering-account detection for `isolated` (best single bank and average), `stáj_psi`, `naive_raw_sharing`; patterns found per type; records and bytes exposed per mode.
- **Czech red-team data:** detection per planted scheme; false-positive rate per honest-look-alike persona; victim cases correctly routed.
- **ČNB data:** rule A/B/C alert counts per unit interpretation; share of rule-C alerts triaged FP vs REVIEW; false-positive rate on the "mom" persona (recurring remittances to the same recipient, 232 clients by our analysis); distribution of priorities; 30-case sample sheet for manual review.
- **Ablations:** without the innocence layer, without the radar, without D6/D7.
- **Show failures:** list the worst false positives and false negatives with their explanations.
- Output: `eval/report.json` and `eval/report.md`. The UI and the pitch read only from these files.

---

## 11. Testing and quality bar

- Unit tests per detector on tiny hand-built fixtures, including one honest look-alike per detector that must not fire.
- Property tests for PSI correctness and for the hash chain.
- Integration test: `make demo` end to end on a small seed, asserting that no raw transaction crosses a node boundary (inspect radar traffic).
- Determinism: same seed, same report.
- Lint, type-check, import-linter (blue team cannot import `redteam/`).
- Performance target: the full ČNB pipeline under 2 minutes on a laptop; PSI on 10k tokens per bank pair under 30 seconds.

---

## 12. Agent roles and workflow

| Role | Owns | Must not |
|---|---|---|
| Architect | Interfaces, schemas, ARCHITECTURE.md, DECISIONS.md | Change a frozen interface without a decision record |
| Data engineer | `ingest/`, canonical schema, FX/units config, bank split | Touch `redteam/` |
| Red team (isolated agent) | `redteam/` generator and labels | Share parameters with anyone except `eval/` |
| Detection engineer | `node/` features, rules, detectors, innocence, cases | Read `redteam/` or labels |
| Crypto engineer | `radar/` PSI, clustering, guards, threat model | Ship plaintext tokens |
| Copilot engineer | `copilot/`, prompts, schemas, OPO | Let the LLM decide triage |
| Governance engineer | `escalation/`, `audit/`, `export/` | Allow self-review paths |
| Frontend engineer | `ui/` | Hard-code any metric |
| QA / evaluation | `tests/`, `eval/`, report | Tune thresholds on labels used for the final report (use a held-out seed) |
| Docs | README, METHODOLOGY (≤ 2 pages of decision logic), DATA, LIMITATIONS | Claim anything the report does not show |

**Order of work**
1. Architect freezes the canonical schema, Signal/Case/Token/PSI message schemas and the API contracts.
2. In parallel: data ingestion (ČNB, IBM, bank split); red-team generator; PSI core with property tests; audit chain.
3. FINREG rules A/B/C on ČNB with unit-interpretation report.
4. Detectors D1–D8 and the innocence layer; case builder; triage; priority.
5. Radar sessions, clustering, guards; three sharing modes.
6. Copilot explanations, triage text, OPO draft.
7. Escalation and conflict engine; FINREG CSV export.
8. Evaluation harness and report.
9. UI on top of the APIs and the report.
10. Hardening: threat model, failure list, docs, `make demo`.

**Definition of done for any component:** tests pass, documented in its module README, logged to the audit chain where it makes decisions, reachable through `make demo`, and its numbers appear in `eval/report.json`.

---

## 13. Deliverables

- Running system via `docker compose up` and `make demo`.
- FINREG-format CSV for the ČNB alerts.
- OPO drafts for the top REVIEW cases (Markdown and PDF).
- `eval/report.md` with all metrics, ablations and failure cases.
- README (quick start, architecture picture, "Built during the hackathon", data and synthetic disclosure).
- METHODOLOGY.md (decision logic, ≤ 2 pages, every rule and weight justified, sources cited).
- LIMITATIONS.md (no networks in the ČNB data; synthetic data; IBM patterns are generic laundering; PSI is not a legal basis; production extensions: device, card, merchant data; Safe-D and AMLR Art. 75 prerequisites).
- `pitch_numbers.json`: the 5–7 headline numbers, generated from the report.

---

## 14. Open items (config, not blockers)

| Item | Default until confirmed |
|---|---|
| Official FX rates for July 2026 | Placeholder rates, labelled in UI |
| Units of expected volume and Q2 columns | All interpretations computed; default chosen by plausible alert rate, logged |
| Escalation matrix and conflict rules | Placeholder matrix, labelled |
| High-risk jurisdiction lists | EU and FATF lists with source URL and date |
| Rule C 6-hour anchor | `threshold_crossing` |

When an item is confirmed, change the config only, never the code, and add a decision record.
