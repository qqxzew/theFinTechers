# Methodology – decision logic (synthetic data throughout)

**The decision path is deterministic and transparent. No black-box model decides.** The LLM verbalises and drafts; humans decide.

## 1. Pipeline
1. **Canonical features per client** (one bank only): windowed turnover, distinct/rare/popular counterparties (degree within the bank: rare ≤ 3 clients, popular ≥ 100), inflow→outflow lag, retention ratio per inflow cycle, drain share after the largest inflow, remittance regularity, active-hour profile, profile gap. Config: `config/thresholds.yaml`.
2. **FINREG rules** (`config/thresholds.yaml`, regulator-fixed values): A profile discrepancy (client level), B high-risk jurisdiction/PEP (transaction level), C flow-through (client level). Unit interpretation of the profile columns is a config option; **no interpretation gives a plausible alert rate** (rule A fires on 60–99.9 % of clients), recorded in `docs/DECISIONS.md` D-008.
3. **Detectors** (pure functions `detect(features, ctx) → [Signal]`): D1 flow-through+, D2 day-zero handover, D3 profile discrepancy+, D4 new-sender fan-in, D5 rare-exit concentration, D6 same hand (group, scored against a shuffled baseline), D7 fixed skim, D8 structuring (thresholds discovered empirically from pile-ups, none hard-coded). Each carries its source ("own design" unless a regulation is cited).
4. **Innocence layer** (exculpatory signals shown next to the suspicion): E1 mom (recurring stable remittances), E2 life, E3 source of funds, E4 institutional counterparty, E5 reciprocity, E6 pooled one-off, E7 co-host middleman, E8 earner. The **victim route** sends own-savings draining to victim protection, never to "mule".
5. **Case score** = additive log-odds: `logit = bias + Σ weight(detector) × signal.score − Σ weight(exculpatory) × score`, `prob = sigmoid(logit)`. Weights and bias are in `config/thresholds.yaml`.
6. **Priority 0–100** = `60 × prob` + factor points: AML risk (0/5/12), PEP 10, high-risk country 10, new client (< 90 d: 8; < 365 d: 4), distant contract 4, multiple distinct detectors (2: 4; ≥ 3: 8), radar cluster 15, amount (log scale up to 15).
7. **Triage**: FP only if priority < 30 **and** every suspicious signal is explained by an exculpatory signal (mapping `cases.explains`). Everything else is REVIEW. Victim-route cases and members of a disclosed cluster are never auto-closed.
8. **Radar**: candidates = cases with prob ≥ 0.05 on the mule route (includes weakly suspicious ones); their rare/low-degree exit tokens go into pairwise DH-PSI; matches are clustered; disclosure needs ≥ 2 banks and ≥ 3 candidates; cluster membership adds signal `X` (weight 3.5) to the score and +15 priority points.

## 2. Why these weights (honest status)
The weights are **hand-set, not fitted**. Rationale: a detector that is specific to a scheme (D2, D6, D7) gets 3.0–3.5 points, a broad one (D3) 1.0, regulator rules A/B/C 0.5/1.0/2.0 (A is known to be noisy); exculpatory signals are negative with E1 and E6 strongest (−3) because they match a complete honest story. The bias −4 puts a single weak rule near prob 0.02. No sensitivity analysis has been done; thresholds for D6 and the radar candidate band were set while looking at dev seed 7. **Any claim about generalisation to real portfolios is unsupported.**

## 3. Fairness
Client nationality and country never raise a score on their own; country matters only through the EU/FATF high-risk lists (rule B) and `high_risk_country` priority points. Age is not in the data and is not inferred. "Distant contract" and "recent account" are modifiers, never verdicts.

## 4. Governance
Every decision needs a named human role at or above the escalation target; overrides need a written reason; the decider must not be relationship owner, rule author or first triager; priority ≥ 70 needs an approver different from the decider; approver ≠ executor. Every case build, model call, tool call, PSI session and decision is an entry in the hash-chained audit log.

## 5. Evaluation protocol
`eval/run_all.py`: dev seeds (7, 101) while building; held-out seeds (202, 303) never used for tuning; modes isolated / staj_psi / naive_raw_sharing; ablations; rank metrics (AP, P@K); failures listed. See `eval/report.md`.
