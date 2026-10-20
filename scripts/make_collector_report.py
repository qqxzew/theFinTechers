"""Assembles eval/collector_report.md from the frozen result files (numbers come from eval/out/collector/*.json and *_tables.md)."""
import json

OUT = "eval/out/collector/"


def rd(f: str) -> str:
    return open(OUT + f, encoding="utf-8").read()


def body(f: str) -> str:
    return rd(f).split("\n", 1)[1]


cnb = json.load(open(OUT + "cnb_control.json"))
cnbl = "; ".join(f"split seed {r['split_seed']}: tested {r['n_tested']}, flagged {r['n_flagged_buckets']}, raised {r['n_raised_customers']}, in Rule C {r['raised_in_rule_c']}" for r in cnb["runs"])
md = f"""# Collector report (night 19-20.10.2026)

**Status: P0 and P1 complete. WHERE was frozen (`collector-where-frozen`) and HOW was frozen on 3 of 5 dev seeds (`collector-how-frozen`, Amendment 2: the first dev HOW run was killed by the host memory guard); both were run once on test seeds 4101/4202/4303. P2 (service, CLI, demo, Outbreak page) is built.** All numbers are from synthetic worlds and computed by code.

## Five-line summary
1. **Crime-free false flags:** customers raised by the network and not flagged by (a): **0.0 per seed** for (c) and for (d) (test, 3 seeds; dev 0.0 as well). Local false flags of (a) in the same world: 6.3 per seed (reported, not part of S1).
2. **Stealth recall, (c)/(d) vs (a)/(b), test seeds:** shared hub (c) **1.00** vs (a) 0.00, (b) 0.00 at month end (0.00-0.67 if a flag stays in the queue; n = 21/31/36). Rotating hub, queue-persistent: (d) **0.81 / 0.61 / 0.00** (jitter none/medium/high) vs (c) 0.00 and (b) 0.00; **with the pre-registered end-of-month snapshot (no queue persistence) (d) is 0.00 in all three, so S3 passes only under the Amendment 2 definition (see below).**
3. **Median first flag day, test seeds:** (c) day 8 (shared) and (d) day 8 / 13 / never (rotating none/medium/high) vs (a) never (censored day 32), (b) 14-32, (e) 24-32. Rings never flagged: (a) 6/6, (c) 0/6 shared, (d) 1/6 rotating none and medium, 6/6 rotating high.
4. **Honest customers raised by the network per world:** (c) mean 1.7 (max 4) shared, 0.7 rotating; (d) mean 2.7 (max 4) shared, 1.7 (max 2) rotating.
5. **Records exposed:** 0 customer-level records reach the collector (it holds masked vectors and sums). Bytes per bank per month: WHERE 97.5 MB + HOW 0.18 MB masked vectors (dense, 31 daily rounds); existing PSI radar (b) 1.3 MB.

## Pre-registered criteria (S1-S5, with owner edits), test seeds 4101/4202/4303
| criterion | result |
|---|---|
| S1 crime-free network-only errors <= 1 per seed | pass for (c) and (d): 0.0 |
| S2 shared cells, (c) >= 0.5 and >= (b) + 0.3 | pass in all 3 cells (n = 21, 31, 36), non-cumulative: (b) 0.00; queue-persistent: (b) 0.00 / 0.29 / 0.67 (shared_high margin 0.33 vs the 0.30 bar) |
| S3 rotating none/medium, (d) - (c) >= 0.4 | **queue-persistent (Amendment 2): pass, 0.81 (n = 21), 0.61 (n = 31). Pre-registered non-cumulative snapshot: FAIL, (d) - (c) = 0.00 in both cells.** rotating-high 0.00, no criterion |
| S4 honest raised <= 5 mean | pass for (c) and (d) in every ring cell |
| S5 median first flag >= 2 days before (a) | pass in all 5 cells (day 8, 8, 8, 8 and 13 vs never flagged by (a)); rotating-high reported without criterion |

**Timeline (git, local clock).** WHERE test result files 00:54, committed 00:59 (`e5b90e4`). Amendment 2 committed 01:17:37 together with the tag `collector-how-frozen` (`a3a0c29`); the dev HOW run ran 01:08-01:14. The first HOW test result file is 08:23 and the last 08:38. So Amendment 2 was written **after** the WHERE test results and **before** any HOW test result. Consequence: the queue-persistent accounting was introduced after I had seen the WHERE test numbers, and it is the reason S3 passes. The non-cumulative (d) table is printed next to it below. It shows (d) = 0.00 because a HOW window only covers the last 2 days, so the snapshot at day 31 has forgotten an outbreak of day 8; S5 (first flag day) is the same under both definitions and passes. Treat S3 as **passed only under a definition chosen after seeing P0 test results**.

S3 is judged on the queue-persistent table (Amendment 2). On **dev** seeds S2 fails in shared_high under queue persistence ((c) 1.00 vs (b) 0.90): the existing radar (b) does flag stealth mules on some days of the month and then loses them. The pre-registered non-cumulative table hides this, so both tables are below.

## What the collector learns
Per round: sums P, K, I over 2^18 hash buckets (HMAC under a key the collector never has) and sums C, I over 360 dense cells per day. It learns that some bucket and some skim/delay window are unusual and how many banks contribute (I), nothing about customers or which bank. It returns only flagged bucket ids (with a small mark) and windows (with a strength label). Each bank maps buckets to its own destinations locally. Masked single vectors are uniform (chi-square test), masks cancel exactly (equality test), a missing bank fails the round loudly.

## Deviations and decisions (docs/DECISIONS.md D-020 to D-025; eval/prereg_collector_amendment2.md)
- The prereg was first pushed unedited by mistake; the tag `collector-prereg` was moved to the edited commit (no results existed yet).
- D-021: null-guard in `node/features/build.py` (no detector or threshold changed).
- The node pipeline (a)/(b)/(e) sees the evaluation month only; the history feeds the collector baseline (D-022).
- Evaluation uses plain sums and a plaintext-equivalent intersection (D-024); tests added.
- P_inst tuned on dev: 30 (at 50 and 80 the 45-payer wholesale decoy gives 5.6 network-only errors per seed in the crime-free world).
- HOW scans windows ending in the last 2 days; BH over all enumerated windows; variant d2 (BH over tested windows only) rejected on dev (about 23 honest raised per world).
- HOW frozen on dev seeds 1-3 only (the first dev HOW run was killed by the host memory guard); seeds 4-5 are incomplete and unused. The test HOW run used 3 workers.
- Replay days: 2, 4, ..., 30 plus 31 (month end); runtime well below 2 h.
- Caveats: shared-hub detection is near perfect because the planted cash-out account has no honest payers; real hubs mix honest and mule payers. Rotating rings with high jitter are not found by HOW on the test seeds (0.00; dev 0.25). Stealth n is 21-36 per cell summed over 3 test seeds (dev: 40-59 over 5).

## 7b CNB sandbox as an external control (no detection claim)
3 random pseudo-bank splits, July only (no history), WHERE only: {cnbl}. The collector flags nothing in the CNB data and touches none of the 16 Rule C cases, consistent with D-009.

## Tables
#### Test seeds, WHERE+HOW, NON-cumulative (the pre-registered snapshot; here S3 fails)
{body("test_how_tables.md")}

#### Test seeds, WHERE+HOW (queue-persistent; this is the table behind S3)
{body("test_how_cum_tables.md")}

#### Test seeds, WHERE only (non-cumulative, the pre-registered primary view)
{rd("test_tables.md")}

{rd("test_cum_tables.md").replace("### ", "#### ", 1)}

#### Dev seeds 1-5, WHERE (non-cumulative)
{body("dev_tables.md")}

#### Dev seeds 1-5, WHERE (queue-persistent)
{body("dev_cum_tables.md")}

#### Dev seeds 1-3 only, WHERE+HOW, queue-persistent (d = frozen HOW, d2 = rejected variant)
{body("dev_how_partial_cum_tables.md")}

## pitch_numbers.json
The existing keys are unchanged from main (weak-evidence radar, held-out seeds 707/808, from the earlier frozen radar experiment). The new `collector` block is written by `scripts/collector_pitch.py` and reads only the frozen test runs (`eval/out/collector/test_how_summary.json` and `test_how_cum_summary.json`, seeds 4101/4202/4303). It contains both the non-cumulative and the queue-persistent (d) numbers. No dev number is in it.

## Service and UI
`collector/service.py` (POST /rounds/{{id}}/submit, GET /rounds/{{id}}/flags; 409 on a missing bank), `node/collector_cli.py submit|expand`, `make demo-collector` (3 bank processes and the collector; logs show only masked vectors and sums), `outbreak/` (the Outbreak demo view, React + TypeScript + Vite; case cards carry the badge "Raised by network"). The old Stáj UI was not touched, by the owner's instruction.
"""
open("eval/collector_report.md", "w", encoding="utf-8").write(md)
print(len(md))
