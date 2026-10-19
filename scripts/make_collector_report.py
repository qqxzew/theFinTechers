"""Assembles eval/collector_report.md from the frozen result files (numbers come from eval/out/collector/*.json and *_tables.md)."""
import json

O = "eval/out/collector/"


def rd(f: str) -> str:
    return open(O + f, encoding="utf-8").read()


def body(f: str) -> str:
    return rd(f).split("\n", 1)[1]


cnb = json.load(open(O + "cnb_control.json"))
cnbl = "; ".join(f"split seed {r['split_seed']}: tested {r['n_tested']}, flagged {r['n_flagged_buckets']}, raised {r['n_raised_customers']}, in Rule C {r['raised_in_rule_c']}" for r in cnb["runs"])
md = f"""# Collector report (night 19-20.10.2026)

**Status: P0 complete (WHERE frozen, test seeds run once). P1 (HOW): frozen on 3 of 5 dev seeds; the test-seed HOW run was NOT executed** (the dev HOW run was killed by the host's low-memory guard, which also forbids an automatic restart). To finish: `python -m eval.collector_run --split test --how --seeds 4101 4202 4303 --workers 4`, then `python -m eval.collector_report report --split test_how --p-inst 30 --methods a b c d --cumulative`. All numbers below are from synthetic worlds and computed by code.

## Five-line summary
1. **Crime-free false flags:** customers raised by the network and not flagged by (a): **0.0 per seed** for (c) (dev 5 seeds, test 3 seeds) and 0.0 for (d) (dev, 3 seeds). Local false flags of (a) in the same world: 6.3 per seed on test (reported, not part of S1).
2. **Stealth recall, (c)/(d) vs (a)/(b):** shared hub, test seeds: (c) **1.00** vs (a) 0.00 and (b) 0.00 at month end (0.00-0.67 if a flag stays in the queue; n = 21/31/36). Rotating hub, dev seeds 1-3, queue-persistent: (d) 0.91 / 0.84 / 0.25 (jitter none/medium/high) vs (c) 0.00 and (b) 0.00; **not yet confirmed on test seeds**.
3. **Median first flag day:** (c) day 8 on test seeds (shared hubs) vs (a) never (censored day 32), (b) 14-32, (e) 24-32; (d) day 7-8 on dev rotating none/medium. Rings never flagged: (a) 6/6, (c) 0/6.
4. **Honest customers raised by the network per world:** (c) mean 1.7 (max 4) shared and 0.7 rotating on test; (d) mean 3.0 (max 7) on dev.
5. **Records exposed:** 0 customer-level records reach the collector (it holds masked vectors and sums). Bytes per bank per month: WHERE 97.5 MB + HOW 0.18 MB masked vectors (dense, 31 daily rounds); existing PSI radar (b) 1.3 MB.

## Pre-registered criteria (S1-S5, with owner edits), test seeds 4101/4202/4303, WHERE (c), non-cumulative end-of-month metrics
S1 pass (0.0 vs <= 1). S2 pass in all 3 shared cells ((c) 1.00 vs (b) 0.00; n = 21, 31, 36, all >= 10). S4 pass (c mean 1.7). S5 pass (median day 8 vs never flagged). **S3 (HOW, rotating hubs): not evaluated on test seeds.** On dev seeds 1-3 (queue-persistent) S3 would pass for none/medium ((d)-(c) = 0.91, 0.84); rotating-high has no criterion.

Under the queue-persistent view (Amendment 2) S2 also passes on test seeds ((c) 1.00 vs (b) 0.67 / 0.29 / 0.00; shared_high difference 0.33 against the 0.30 bar) but on **dev** seeds it FAILS in shared_high ((c) 1.00 vs (b) 0.90). The pre-registered primary table hides that the existing radar does flag stealth mules on some days of the month and then loses them. That contradicts my first reading of "(b) about 0"; both tables are below.

## What the collector learns
Per round: sums P, K, I over 2^18 hash buckets (HMAC under a key the collector never has) and sums C, I over 360 dense cells per day. It learns that some bucket and some skim/delay window are unusual and how many banks contribute (I), nothing about customers or which bank. It returns only flagged bucket ids (with a small mark) and windows (with a strength label). Each bank maps buckets to its own destinations locally. Masked single vectors are uniform (chi-square test), masks cancel exactly (equality test), a missing bank fails the round loudly.

## Deviations and decisions (docs/DECISIONS.md D-020 to D-025; eval/prereg_collector_amendment2.md)
- The prereg was first pushed unedited by mistake; the tag `collector-prereg` was moved to the edited commit (no results existed yet).
- D-021: null-guard in `node/features/build.py` (no detector or threshold changed).
- The node pipeline (a)/(b)/(e) sees the evaluation month only; the history feeds the collector baseline (D-022).
- Evaluation uses plain sums and a plaintext-equivalent intersection (D-024); tests added.
- P_inst tuned on dev: 30 (at 50 and 80 the 45-payer wholesale decoy gives 5.6 network-only errors per seed in the crime-free world).
- HOW scans windows ending in the last 2 days; BH over all enumerated windows; variant d2 (BH over tested windows only) rejected on dev (about 23 honest raised per world).
- HOW frozen on seeds 1-3 only (OOM kill); seeds 4-5 are incomplete and unused.
- Replay days: 2, 4, ..., 30 plus 31 (month end); runtime well below 2 h.
- Caveats: shared-hub detection is near perfect because the planted cash-out account has no honest payers; real hubs mix honest and mule payers. Rotating rings with high jitter are only partly found by HOW (0.25). Stealth n is 21-36 per cell summed over 3 test seeds (dev: 40-59 over 5).

## 7b CNB sandbox as an external control (no detection claim)
3 random pseudo-bank splits, July only (no history), WHERE only: {cnbl}. The collector flags nothing in the CNB data and touches none of the 16 Rule C cases, consistent with D-009.

## Tables
{rd("test_tables.md")}

{rd("test_cum_tables.md").replace("### ", "#### ", 1)}

#### Dev seeds 1-5, WHERE (non-cumulative)
{body("dev_tables.md")}

#### Dev seeds 1-5, WHERE (queue-persistent)
{body("dev_cum_tables.md")}

#### Dev seeds 1-3 only, WHERE+HOW, queue-persistent (d = frozen HOW, d2 = rejected variant)
{body("dev_how_partial_cum_tables.md")}

## Service and UI
`collector/service.py` (POST /rounds/{{id}}/submit, GET /rounds/{{id}}/flags; 409 on a missing bank), `node/collector_cli.py submit|expand`, `make demo-collector` (3 bank processes and the collector; logs show only masked vectors and sums), `outbreak/index.html` (the Outbreak demo view as a standalone page; case cards carry the badge "Raised by network"). The old Stáj UI was not touched, by the owner's instruction.
"""
open("eval/collector_report.md", "w", encoding="utf-8").write(md)
print(len(md))
