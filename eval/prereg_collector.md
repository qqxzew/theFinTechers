# Pre-registration: Collector (written BEFORE any run that produces results)

Branch `collector`, started 2026-10-20 (night 19→20.10). Status: APPROVED by the owner with the edits below; committed and tagged `collector-prereg`.
Nothing below was produced by running the new code. Items marked **[INTERPRETATION]** are my reading of an under-specified instruction; the owner may overrule them before approving.

## 0. Owner edits before approval (applied; they override the text below where they differ)
1. Seeds: test seeds 707/808/909 replaced by **4101, 4202, 4303** (checked: never generated, not in code, eval outputs or the decision log).
2. Ring size is exactly **6** (2 mules in each of the 3 banks) in every ring cell, shared and rotating.
3. **S1** counts only the collector's own errors: in the crime-free world, customers raised by the network and not flagged by (a) must be ≤ 1 per seed on average, for (c) and for (d). Local false flags of (a) are reported, not part of S1. Flagged buckets and windows are reported too, including those not expanded. The tuning rule uses the same definition.
4. **S2**: in each shared-hub cell, (c) stealth recall ≥ 0.5 AND at least 0.3 above (b). (a) and (b) are reported as they come; no "≈ 0" requirement.
5. **Stealth-set size**: n is reported next to every stealth recall. If n < 10 in a cell (summed over test seeds), that cell is inconclusive for S2/S3 and does not count as a pass.
6. **S5** applies to shared cells with (c) and to rotating none/medium with (d). Rotating-high: reported, no criterion. Secondary metric, no criterion: per-mule first flag day and per-mule CZK passed before that mule is flagged.
7. Interpretations 1, 3, 5, 6, 7 approved as written; 4 approved with the S5 change.
8. Time box: P0 frozen results by **05:00** (2026-10-20), otherwise stop and report. P1 only after P0 is frozen. Hard stop **06:15** with `eval/collector_report.md` written, five-line summary on top. (Supersedes the 03:00 time box in section 8.)
9. Git: collector work is done in the worktree `../staj-collector` (branch `collector`, based on main commit 400907b "wip: pre-collector demo edits (owner)"). `staj/` stays on main.
10. Baseline: the existing suite in the worktree gave 129 passed, 1 skipped, 4 errors; the 4 errors (`tests/integration/test_api.py`) were only the gitignored `data/redteam` worlds missing from the fresh worktree. After copying `data/redteam` from `staj/` they pass. **Baseline = 0 failures** (133 passed, 1 skipped). "Stay green" = no new failures.
11. Process note: the first commit of this file (before these edits) was pushed by mistake; the tag `collector-prereg` was then moved to the commit that contains these edits. No result had been produced in between.

## 1. Question
Does a second shared node, the COLLECTOR, which receives masked counts about ALL customers of ALL banks (never customer-level data), find mule rings that the bank-local score and the existing PSI radar cannot see, and does it find them EARLIER?

## 2. Methods (all run on identical worlds and identical data cut-offs)
| id | name | definition |
|----|------|------------|
| a | bank alone | per-bank node, no sharing (`isolated` in `eval/redteam_eval.py`) |
| b | current radar | (a) + existing DH-PSI radar with the frozen weak-evidence config (`weak_top_frac 0.05`, `min_significance 2.0`); = `staj_psi` |
| c | + collector WHERE | (b) + customers raised by one local expansion of WHERE-flagged buckets |
| d | + collector WHERE+HOW | (c) + customers raised by one local expansion of HOW-flagged windows |
| e | "central register (upper bound)" | the existing pooled baseline, `naive_raw_sharing`. It is NOT a guaranteed bound (D-018 note: thresholds calibrated per bank), and is labelled as such |

Flag definition (all methods): existing operating point, triage REVIEW, route `mule_review`, priority ≥ `cases.fp_max_priority` (30) (D-011). **[INTERPRETATION]** A customer raised by the collector expansion enters the queue with `network_evidence`; it counts as FLAGGED for (c)/(d) when its case is at that operating point OR when it was raised by the collector (the raise is the network's output; the analyst decides afterwards). Both counts are reported (`flag_by_priority`, `flag_by_raise`); success criteria use `flag_by_raise`. Precision therefore reflects raised customers, which is the honest cost of the network.

## 3. Metrics (every method, every cell, every seed)
1. **Stealth recall** = share of low-and-slow ring mules whose local probability under (a) is < `token_export.min_prob` (0.05) that are flagged by the method. The stealth set is computed post hoc in `eval/` from the full-month run of (a) and the labels. The generator never computes it. For (a) itself the stealth recall is 0 by construction; it is reported anyway.
2. Recall, precision (all mules incl. legacy schemes, existing `_metrics`).
3. (Secondary, per mule: first flag day and CZK passed before that mule is flagged.) Honest customers raised by the network per world = clients labelled `honest`/`background`/`victim`-free that are flagged by method m and NOT flagged by (a).
4. False flags in the crime-free world: (i) network-only errors = customers raised by the network and not flagged by (a), per seed, for (b), (c), (d) (this is what S1 uses); (ii) local false flags of (a), reported only; (iii) numbers of flagged buckets/windows, expanded or not.
5. First flag day per ring = smallest replay day t at which at least one mule of the ring is flagged. Never flagged → right-censored at day 32 (reported as "not flagged", with share).
6. CZK passed through ring mules before the first flag = sum of `amount_czk` of mules' outgoing pass-through payments (ground truth from labels and tx, computed in `eval/`) with `ts` before the first-flag day; for a never-flagged ring, the total to month end.
7. Bytes sent per bank (actual size of the masked vectors per round, per month; for (b) existing `exposure.bytes_exchanged` per bank; (a) 0).
8. Records exposed = customer-level records visible outside the owning bank: collector 0 by construction (reported as counted, tested); bank-to-bank = existing `raw_records_exposed` + tokens disclosed by PSI; (e) = all tx.
9. Share of (e)'s detections reached = |mules flagged by m ∩ mules flagged by (e)| / |mules flagged by (e)|, by cell.

## 4. Worlds and seeds
- Dev seeds 1–5: tuning allowed. Test seeds 4101, 4202, 4303: run ONCE, only after tag `collector-where-frozen` (P0) and, for HOW, `collector-how-frozen` (P1).
- Test seeds are fresh (owner edit 1); no reuse disclosure is needed.
- Grid: `hub_mode` {shared, rotating} × `script_jitter` {none, medium, high} = 6 cells, plus 1 crime-free cell = 7 cells per seed. Each ring-bearing world contains the existing legacy schemes and lookalikes (unchanged) plus the new low-and-slow rings. The crime-free world contains NO legacy schemes and no rings, only background, honest personas and decoys.
- Fixed generator values (not tuned): 3 banks, 1000 clients per bank (as now); 2 low-and-slow rings per world; ring size exactly 6 (2 mules per bank); ≤ 2 members per bank per cash-out; 2–4 transfers per mule per wave; waves of 2–4 active days, 1–3 waves per ring; transfer amounts 800–4,000 CZK; base skim per ring drawn from 8–15 %, forwarding delay base 20–90 min. Jitter: none = exact skim and delay for all members; medium = skim ±2 pp, delay × lognormal(σ 0.3); high = skim ±5 pp, delay × lognormal(σ 0.8). Rotating hub: each mule has its own cash-out account; shared: one cash-out account per ring (≤ 2 mules per bank).
- 30 days of history (June 2026) with honest activity and decoys only: DONE unless implementation shows it is too costly; then skipped and stated in the report.
- Decoys always on: crypto-exchange top-up account (many honest payers, some pass-through-like), wholesale supplier paid by many small businesses, own-account transfers (skim 0). Allowlist of institutional accounts = a public registry file written by the generator containing ONLY the existing popular-account pool (utilities, merchants, employers) and no decoy and no label; so decoys must be handled by the statistics and the P ≥ 50 rule.
- The evaluation month is July 2026 (day 1–31). Replay days t = 2, 4, …, 30 (fallback t = 3, 6, …, 30 if total runtime > 2 h, stated in the report). End-of-month metrics (items 1–4, 7–9) use all data (day 31).

## 5. Collector statistics (fixed by the task text)
Pass-through event: out within 72 h after an external in, out/in ∈ [0.70, 1.00], employer/own-account counterparties excluded using existing features. WHERE: HMAC-SHA256 mod 2^18; **[INTERPRETATION]** P, K are accumulated over a trailing 30-day window ending at the replay day (so the June history is used from day 1). `p0 = ΣK/ΣP`, test buckets with banks ≥ 2 and K ≥ 3, `binom.sf(K−1, P, p0)`, BH-FDR q = 0.01. Buckets with P ≥ P_inst or on the allowlist are counted, reported, never expanded; P ≤ 20 marked small. HOW: space-time permutation baseline as in the task, windows of skim width 1 or 3 × one delay bin × one dormant value × 1–3 days; observed ≥ 4 and banks ≥ 2; `poisson.sf`; BH q = 0.01 over all windows. Monte Carlo max-statistic check (999 replicates): done on dev seeds only if time permits, reported as a diagnostic, not a gate.
Secure aggregation: per task text; evaluation uses plain sums justified by the masked-sum = plain-sum test; plaintext-equivalent intersection instead of PSI justified by the existing PSI = plaintext test.

## 6. Tuning rule (dev seeds 1–5 only)
Tunable: only `P_inst` ∈ {30, 50, 80} (default 50). Rule: choose the value maximising dev-mean stealth recall of (c) over the shared-hub cells, subject to mean crime-free network-only errors (S1 definition) ≤ 1 per seed and honest raised ≤ 5 per world on every dev seed; ties → the larger value. HOW (P1) tunable: none beyond what the task fixes; if dev data show the HOW test is mis-calibrated in the crime-free world (more than 1 false window-flag per seed), the only permitted change is raising `observed ≥ 4` to 5 or 6, chosen by the same rule. No generator parameter, detector, or existing threshold is changed after seeing any result. A change after a test run forces new test seeds.

## 7. Success criteria (defaults; owner may edit before approving)
S1. Crime-free world: customers raised by the network and not flagged by (a) ≤ 1 per seed on average, for (c) and for (d).
S2. Shared-hub cells (each jitter level separately): (c) stealth recall ≥ 0.5 and ≥ (b) + 0.3. Cells with stealth n < 10 summed over test seeds are inconclusive, not a pass (same for S3).
S3. Rotating-hub cells with jitter none and medium: (d) stealth recall − (c) stealth recall ≥ 0.4. (high jitter is reported without a criterion; same n < 10 rule.)
S4. Honest raised ≤ 5 per world (cells with rings, (c) and (d), every seed; reported as the mean and the maximum, criterion on the mean).
S5. Median first flag day of (c) in shared cells, and of (d) in rotating none/medium cells, is at least 2 days before (a). Rotating-high: reported, no criterion. If (a) never flags a ring it is censored at day 32; the share never flagged is reported next to every median.
Medians carry 95 % bootstrap intervals (2,000 resamples, fixed RNG seed, resampling rings within seed then seeds). Every cell is reported, including failures. S1–S5 are evaluated separately for P0 (WHERE: S1, S2, S4, S5 shared cells, with (c)) and P1 (HOW: S3, S5 rotating cells, with (d); S1/S4 re-checked for (d)).

## 8. Other commitments
- Eval-only labels; `import-linter` contracts stay green and a contract is added so that the collector package imports nothing from bank data code. Existing tests stay green; new tests per the task text (masked sum = plain sum, chi-square uniformity, no correlation, collector import test).
- No recursion, one expansion round. A bank needs all banks in a round; a missing bank fails loudly.
- Time box: see owner edit 8 (05:00 / 06:15).
- Decisions logged as D-020 onward in `docs/DECISIONS.md`. `pitch_numbers.json` is regenerated only from frozen runs.
- 7b (ČNB sandbox): 3 pseudo-banks by seeded random split, collector run, flags reported, overlap with the 16 rule-C cases reported. No detection claim.
- Known limits stated in advance: synthetic worlds; one team writes generator and detectors; the collector colluding with all but one bank breaks secrecy; no dropout recovery; 30-day baseline; legal status unconfirmed.
