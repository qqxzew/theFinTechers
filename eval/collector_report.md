# Collector report (night 19-20.10.2026)

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
3 random pseudo-bank splits, July only (no history), WHERE only: split seed 0: tested 526, flagged 0, raised 0, in Rule C 0; split seed 1: tested 525, flagged 0, raised 0, in Rule C 0; split seed 2: tested 516, flagged 0, raised 0, in Rule C 0. The collector flags nothing in the CNB data and touches none of the 16 Rule C cases, consistent with D-009.

## Tables
#### Test seeds, WHERE+HOW, NON-cumulative (the pre-registered snapshot; here S3 fails)

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag day, median [CI] | CZK through the flag day (incl.), median [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/21) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| shared_none | b | 0.00 (0/21) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| shared_none | c | 1.00 (21/21) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8645] | 17135 [8577, 31135] |
| shared_none | d | 1.00 (21/21) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8645] | 17135 [8577, 31135] |
| shared_none | e | 0.00 (0/21) | 0.80 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42610 [35580, 60897] | 47156 [35580, 73936] |
| shared_none | e | 0.00 (0/21) | 0.80 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42610 [35580, 60897] | 47156 [35580, 73936] |
| shared_medium | a | 0.00 (0/31) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| shared_medium | b | 0.00 (0/31) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [14.0, 32.0] | 4/6 | 38233 [30082, 86130] | 38432 [34568, 86130] |
| shared_medium | c | 1.00 (31/31) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8592] | 17087 [8529, 31141] |
| shared_medium | d | 1.00 (31/31) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8592] | 17087 [8529, 31141] |
| shared_medium | e | 0.00 (0/31) | 0.76 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42535 [35557, 60985] | 47044 [35557, 73974] |
| shared_medium | e | 0.00 (0/31) | 0.76 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42535 [35557, 60985] | 47044 [35557, 73974] |
| shared_high | a | 0.00 (0/36) | 0.75 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| shared_high | b | 0.00 (0/36) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 14.0 [14.0, 32.0] | 2/6 | 38165 [29885, 52753] | 38305 [34739, 58378] |
| shared_high | c | 1.00 (36/36) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8513] | 17015 [8457, 28342] |
| shared_high | d | 1.00 (36/36) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8513] | 17015 [8457, 28342] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_none | a | 0.00 (0/21) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | b | 0.00 (0/21) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | c | 0.00 (0/21) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | d | 0.00 (0/21) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 8.0 [8.0, 32.0] | 1/6 | 3971 [0, 35580] | 22036 [13435, 35839] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_medium | a | 0.00 (0/31) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_medium | b | 0.00 (0/31) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_medium | c | 0.00 (0/31) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_medium | d | 0.00 (0/31) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 13.0 [8.0, 32.0] | 1/6 | 38681 [4646, 50917] | 38946 [26740, 62914] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_high | a | 0.00 (0/36) | 0.75 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | b | 0.00 (0/36) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | c | 0.00 (0/36) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | d | 0.00 (0/36) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | d | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 71, flagged 0.0, institutional-suppressed 2.0; rotating_high: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_medium: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_none: tested 79, flagged 11.0, institutional-suppressed 2.0; shared_high: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_medium: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_none: tested 81, flagged 13.0, institutional-suppressed 2.0

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S1 | crimefree/d | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 0.00, (a) 0.00, n=36 | pass |
| S2 | shared_medium | (c) 1.00 vs (b) 0.00, (a) 0.00, n=31 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.00, (a) 0.00, n=21 | pass |
| S3 | rotating_medium | (d)-(c) = 0.00, n=31 | fail |
| S3 | rotating_none | (d)-(c) = 0.00, n=21 | fail |
| S4 | rotating_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_high/d | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_medium/d | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_none/d | honest raised mean 0.7, max 1 | pass |
| S4 | shared_high/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_high/d | honest raised mean 1.7, max 4 | pass |
| S4 | shared_medium/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_medium/d | honest raised mean 1.7, max 4 | pass |
| S4 | shared_none/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_none/d | honest raised mean 1.7, max 4 | pass |
| S5 | rotating_medium | median first day (a) 32.0 vs (d) 13.0; never flagged (a) 6/6, (d) 1/6 | pass |
| S5 | rotating_none | median first day (a) 32.0 vs (d) 8.0; never flagged (a) 6/6, (d) 1/6 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |

#### Test seeds, WHERE+HOW (queue-persistent; this is the table behind S3)

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag day, median [CI] | CZK through the flag day (incl.), median [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/21) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| shared_none | b | 0.00 (0/21) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| shared_none | c | 1.00 (21/21) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8645] | 17135 [8577, 31135] |
| shared_none | d | 1.00 (21/21) | 1.00 | 0.84 | 2.7 / 4 | 2.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8645] | 17135 [8577, 31135] |
| shared_none | e | 0.05 (1/21) | 0.81 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42610 [35580, 60897] | 47156 [35580, 73936] |
| shared_none | e | 0.05 (1/21) | 0.81 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42610 [35580, 60897] | 47156 [35580, 73936] |
| shared_medium | a | 0.00 (0/31) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| shared_medium | b | 0.29 (9/31) | 0.90 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [14.0, 32.0] | 4/6 | 38233 [31810, 86130] | 38432 [33627, 86130] |
| shared_medium | c | 1.00 (31/31) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8592] | 17087 [8529, 31141] |
| shared_medium | d | 1.00 (31/31) | 1.00 | 0.84 | 2.7 / 4 | 2.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8592] | 17087 [8529, 31141] |
| shared_medium | e | 0.13 (4/31) | 0.78 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42535 [35557, 60985] | 47044 [35557, 73974] |
| shared_medium | e | 0.13 (4/31) | 0.78 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42535 [35557, 60985] | 47044 [35557, 73974] |
| shared_high | a | 0.00 (0/36) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| shared_high | b | 0.67 (24/36) | 0.95 | 0.86 | 0.0 / 0 | 0.0 | 14.0 [14.0, 32.0] | 2/6 | 38165 [31887, 63666] | 38305 [33992, 74917] |
| shared_high | c | 1.00 (36/36) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 9204] | 17015 [8457, 36075] |
| shared_high | d | 1.00 (36/36) | 1.00 | 0.85 | 2.0 / 4 | 2.0 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 9204] | 17015 [8457, 36075] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_none | a | 0.00 (0/21) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 130407] | 67426 [35580, 130407] |
| rotating_none | b | 0.00 (0/21) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 130407] | 67426 [35580, 130407] |
| rotating_none | c | 0.00 (0/21) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 130407] | 67426 [35580, 130407] |
| rotating_none | d | 0.81 (17/21) | 0.98 | 0.85 | 1.7 / 2 | 1.7 | 8.0 [8.0, 32.0] | 1/6 | 3971 [0, 35580] | 22036 [13435, 36098] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 130407] | 67426 [35580, 130407] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 130407] | 67426 [35580, 130407] |
| rotating_medium | a | 0.00 (0/31) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_medium | b | 0.00 (0/31) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_medium | c | 0.00 (0/31) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_medium | d | 0.61 (19/31) | 0.95 | 0.84 | 1.7 / 2 | 1.7 | 13.0 [8.0, 32.0] | 1/6 | 38681 [4646, 50917] | 38946 [26740, 62914] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| rotating_high | a | 0.00 (0/36) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | b | 0.00 (0/36) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | c | 0.00 (0/36) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | d | 0.00 (0/36) | 0.86 | 0.84 | 1.0 / 2 | 1.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] | 67192 [35523, 130529] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | d | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 71, flagged 0.0, institutional-suppressed 2.0; rotating_high: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_medium: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_none: tested 79, flagged 11.0, institutional-suppressed 2.0; shared_high: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_medium: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_none: tested 81, flagged 13.0, institutional-suppressed 2.0

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S1 | crimefree/d | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 0.67, (a) 0.00, n=36 | pass |
| S2 | shared_medium | (c) 1.00 vs (b) 0.29, (a) 0.00, n=31 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.00, (a) 0.00, n=21 | pass |
| S3 | rotating_medium | (d)-(c) = 0.61, n=31 | pass |
| S3 | rotating_none | (d)-(c) = 0.81, n=21 | pass |
| S4 | rotating_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_high/d | honest raised mean 1.0, max 2 | pass |
| S4 | rotating_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_medium/d | honest raised mean 1.7, max 2 | pass |
| S4 | rotating_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_none/d | honest raised mean 1.7, max 2 | pass |
| S4 | shared_high/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_high/d | honest raised mean 2.0, max 4 | pass |
| S4 | shared_medium/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_medium/d | honest raised mean 2.7, max 4 | pass |
| S4 | shared_none/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_none/d | honest raised mean 2.7, max 4 | pass |
| S5 | rotating_medium | median first day (a) 32.0 vs (d) 13.0; never flagged (a) 6/6, (d) 1/6 | pass |
| S5 | rotating_none | median first day (a) 32.0 vs (d) 8.0; never flagged (a) 6/6, (d) 1/6 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |

#### Test seeds, WHERE only (non-cumulative, the pre-registered primary view)
### test seeds, p_inst=30

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag day, median [CI] | CZK through the flag day (incl.), median [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/21) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| shared_none | b | 0.00 (0/21) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| shared_none | c | 1.00 (21/21) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8645] | 17135 [8577, 31135] |
| shared_none | e | 0.00 (0/21) | 0.80 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42610 [35580, 60897] | 47156 [35580, 73936] |
| shared_none | e | 0.00 (0/21) | 0.80 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42610 [35580, 60897] | 47156 [35580, 73936] |
| shared_medium | a | 0.00 (0/31) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| shared_medium | b | 0.00 (0/31) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [14.0, 32.0] | 4/6 | 38233 [31810, 130456] | 38432 [33627, 130456] |
| shared_medium | c | 1.00 (31/31) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 9291] | 17087 [8529, 36089] |
| shared_medium | e | 0.00 (0/31) | 0.76 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 3/6 | 42535 [35557, 63774] | 47044 [35557, 74923] |
| shared_medium | e | 0.00 (0/31) | 0.76 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 3/6 | 42535 [35557, 63774] | 47044 [35557, 74923] |
| shared_high | a | 0.00 (0/36) | 0.75 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| shared_high | b | 0.00 (0/36) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 14.0 [14.0, 32.0] | 2/6 | 38165 [29885, 52753] | 38305 [34739, 58378] |
| shared_high | c | 1.00 (36/36) | 1.00 | 0.92 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8513] | 17015 [8457, 28342] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_none | a | 0.00 (0/21) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | b | 0.00 (0/21) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | c | 0.00 (0/21) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_medium | a | 0.00 (0/31) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_medium | b | 0.00 (0/31) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_medium | c | 0.00 (0/31) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_high | a | 0.00 (0/36) | 0.75 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_high | b | 0.00 (0/36) | 0.86 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_high | c | 0.00 (0/36) | 0.86 | 0.92 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 71, flagged 0.0, institutional-suppressed 2.0; rotating_high: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_medium: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_none: tested 79, flagged 11.0, institutional-suppressed 2.0; shared_high: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_medium: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_none: tested 81, flagged 13.0, institutional-suppressed 2.0

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 0.00, (a) 0.00, n=36 | pass |
| S2 | shared_medium | (c) 1.00 vs (b) 0.00, (a) 0.00, n=31 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.00, (a) 0.00, n=21 | pass |
| S4 | rotating_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_high/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_medium/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_none/c | honest raised mean 1.7, max 4 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |

#### test seeds, p_inst=30

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag day, median [CI] | CZK through the flag day (incl.), median [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/21) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| shared_none | b | 0.00 (0/21) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| shared_none | c | 1.00 (21/21) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8645] | 17135 [8577, 31135] |
| shared_none | e | 0.05 (1/21) | 0.81 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42610 [35580, 60897] | 47156 [35580, 73936] |
| shared_none | e | 0.05 (1/21) | 0.81 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [15.0, 32.0] | 3/6 | 42610 [35580, 60897] | 47156 [35580, 73936] |
| shared_medium | a | 0.00 (0/31) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] | 67332 [35557, 130456] |
| shared_medium | b | 0.29 (9/31) | 0.90 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [14.0, 32.0] | 4/6 | 38233 [30082, 130456] | 38432 [34568, 130456] |
| shared_medium | c | 1.00 (31/31) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 9291] | 17087 [8529, 36089] |
| shared_medium | e | 0.13 (4/31) | 0.78 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 3/6 | 42535 [35557, 63774] | 47044 [35557, 74923] |
| shared_medium | e | 0.13 (4/31) | 0.78 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 3/6 | 42535 [35557, 63774] | 47044 [35557, 74923] |
| shared_high | a | 0.00 (0/36) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| shared_high | b | 0.67 (24/36) | 0.95 | 0.86 | 0.0 / 0 | 0.0 | 14.0 [14.0, 32.0] | 2/6 | 38165 [29885, 52753] | 38305 [34739, 58378] |
| shared_high | c | 1.00 (36/36) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 8513] | 17015 [8457, 28342] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_none | a | 0.00 (0/21) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | b | 0.00 (0/21) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | c | 0.00 (0/21) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] | 67426 [35580, 119825] |
| rotating_medium | a | 0.00 (0/31) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_medium | b | 0.00 (0/31) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_medium | c | 0.00 (0/31) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 119800] | 67332 [35557, 119800] |
| rotating_high | a | 0.00 (0/36) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_high | b | 0.00 (0/36) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_high | c | 0.00 (0/36) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 119762] | 67192 [35523, 119762] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 71, flagged 0.0, institutional-suppressed 2.0; rotating_high: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_medium: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_none: tested 79, flagged 11.0, institutional-suppressed 2.0; shared_high: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_medium: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_none: tested 81, flagged 13.0, institutional-suppressed 2.0

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 0.67, (a) 0.00, n=36 | pass |
| S2 | shared_medium | (c) 1.00 vs (b) 0.29, (a) 0.00, n=31 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.00, (a) 0.00, n=21 | pass |
| S4 | rotating_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_high/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_medium/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_none/c | honest raised mean 1.7, max 4 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |

#### Dev seeds 1-5, WHERE (non-cumulative)

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag day, median [CI] | CZK through the flag day (incl.), median [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/40) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] | 73486 [41335, 117285] |
| shared_none | b | 0.00 (0/40) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 5/10 | 46550 [39782, 92325] | 54382 [39782, 92325] |
| shared_none | c | 1.00 (40/40) | 1.00 | 0.93 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4730 [0, 13888] | 18546 [10243, 33436] |
| shared_none | e | 0.00 (0/40) | 0.77 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [12.0, 32.0] | 5/10 | 45833 [39782, 62856] | 53735 [39782, 73719] |
| shared_none | e | 0.00 (0/40) | 0.77 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [12.0, 32.0] | 5/10 | 45833 [39782, 62856] | 53735 [39782, 73719] |
| shared_medium | a | 0.00 (0/50) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 117388] | 73582 [41269, 117388] |
| shared_medium | b | 0.00 (0/50) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 5/10 | 46621 [39716, 74550] | 54493 [39716, 74550] |
| shared_medium | c | 1.00 (50/50) | 1.00 | 0.93 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4789 [0, 13903] | 18647 [10175, 33516] |
| shared_medium | e | 0.00 (0/50) | 0.75 | 0.93 | 0.0 / 0 | 0.0 | 26.0 [14.0, 32.0] | 5/10 | 45834 [39716, 74140] | 53737 [39716, 74555] |
| shared_medium | e | 0.00 (0/50) | 0.75 | 0.93 | 0.0 / 0 | 0.0 | 26.0 [14.0, 32.0] | 5/10 | 45834 [39716, 74140] | 53737 [39716, 74555] |
| shared_high | a | 0.00 (0/59) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| shared_high | b | 0.00 (0/59) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 14.0 [14.0, 17.0] | 1/10 | 41915 [34548, 52716] | 43149 [37539, 61975] |
| shared_high | c | 1.00 (59/59) | 1.00 | 0.93 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4877 [0, 13927] | 18799 [10073, 33636] |
| shared_high | e | 0.00 (0/59) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 9/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| shared_high | e | 0.00 (0/59) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 9/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_none | a | 0.00 (0/40) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] | 73486 [41335, 117285] |
| rotating_none | b | 0.00 (0/40) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] | 73486 [41335, 117285] |
| rotating_none | c | 0.00 (0/40) | 0.85 | 0.92 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] | 73486 [41335, 117285] |
| rotating_none | e | 0.00 (0/40) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] | 73486 [41335, 117285] |
| rotating_none | e | 0.00 (0/40) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] | 73486 [41335, 117285] |
| rotating_medium | a | 0.00 (0/50) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_medium | b | 0.00 (0/50) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_medium | c | 0.00 (0/50) | 0.85 | 0.92 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_medium | e | 0.00 (0/50) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_medium | e | 0.00 (0/50) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_high | a | 0.00 (0/59) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_high | b | 0.00 (0/59) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_high | c | 0.00 (0/59) | 0.85 | 0.92 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_high | e | 0.00 (0/59) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_high | e | 0.00 (0/59) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 71, flagged 0.0, institutional-suppressed 2.0; rotating_high: tested 80, flagged 11.0, institutional-suppressed 2.2; rotating_medium: tested 80, flagged 11.0, institutional-suppressed 2.2; rotating_none: tested 80, flagged 11.0, institutional-suppressed 2.2; shared_high: tested 82, flagged 13.0, institutional-suppressed 2.2; shared_medium: tested 82, flagged 13.0, institutional-suppressed 2.2; shared_none: tested 82, flagged 13.0, institutional-suppressed 2.2

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 0.00, (a) 0.00, n=59 | pass |
| S2 | shared_medium | (c) 1.00 vs (b) 0.00, (a) 0.00, n=50 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.00, (a) 0.00, n=40 | pass |
| S4 | rotating_high/c | honest raised mean 0.6, max 1 | pass |
| S4 | rotating_medium/c | honest raised mean 0.6, max 1 | pass |
| S4 | rotating_none/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_high/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_medium/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_none/c | honest raised mean 0.6, max 1 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |

#### Dev seeds 1-5, WHERE (queue-persistent)

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag day, median [CI] | CZK through the flag day (incl.), median [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/40) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] | 73486 [41335, 117285] |
| shared_none | b | 0.55 (22/40) | 0.91 | 0.85 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 5/10 | 46550 [39782, 92325] | 54382 [39782, 92325] |
| shared_none | c | 1.00 (40/40) | 1.00 | 0.86 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4730 [0, 13888] | 18546 [10243, 33436] |
| shared_none | e | 0.10 (4/40) | 0.78 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [12.0, 32.0] | 5/10 | 45833 [39782, 62856] | 53735 [39782, 73719] |
| shared_none | e | 0.10 (4/40) | 0.78 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [12.0, 32.0] | 5/10 | 45833 [39782, 62856] | 53735 [39782, 73719] |
| shared_medium | a | 0.00 (0/50) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| shared_medium | b | 0.52 (26/50) | 0.90 | 0.85 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 5/10 | 46621 [39716, 74550] | 54493 [39716, 74550] |
| shared_medium | c | 1.00 (50/50) | 1.00 | 0.86 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4789 [0, 13903] | 18647 [10175, 33516] |
| shared_medium | e | 0.02 (1/50) | 0.76 | 0.91 | 0.0 / 0 | 0.0 | 26.0 [14.0, 32.0] | 5/10 | 45834 [39716, 74116] | 53737 [39716, 74542] |
| shared_medium | e | 0.02 (1/50) | 0.76 | 0.91 | 0.0 / 0 | 0.0 | 26.0 [14.0, 32.0] | 5/10 | 45834 [39716, 74116] | 53737 [39716, 74542] |
| shared_high | a | 0.00 (0/59) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 117341] | 73727 [41170, 117341] |
| shared_high | b | 0.90 (53/59) | 0.96 | 0.86 | 0.0 / 0 | 0.0 | 14.0 [14.0, 17.0] | 1/10 | 41915 [34548, 52716] | 43149 [37539, 61975] |
| shared_high | c | 1.00 (59/59) | 1.00 | 0.86 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4877 [0, 15367] | 18799 [10073, 33636] |
| shared_high | e | 0.00 (0/59) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 9/10 | 73727 [41170, 117341] | 73727 [41170, 117341] |
| shared_high | e | 0.00 (0/59) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 9/10 | 73727 [41170, 117341] | 73727 [41170, 117341] |
| rotating_none | a | 0.00 (0/40) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 113652] | 73486 [41335, 113652] |
| rotating_none | b | 0.00 (0/40) | 0.83 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 113652] | 73486 [41335, 113652] |
| rotating_none | c | 0.00 (0/40) | 0.85 | 0.84 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 113652] | 73486 [41335, 113652] |
| rotating_none | e | 0.00 (0/40) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 113652] | 73486 [41335, 113652] |
| rotating_none | e | 0.00 (0/40) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 113652] | 73486 [41335, 113652] |
| rotating_medium | a | 0.00 (0/50) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_medium | b | 0.00 (0/50) | 0.83 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_medium | c | 0.00 (0/50) | 0.85 | 0.84 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_medium | e | 0.00 (0/50) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_medium | e | 0.00 (0/50) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] | 73582 [41269, 113556] |
| rotating_high | a | 0.00 (0/59) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_high | b | 0.00 (0/59) | 0.83 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_high | c | 0.00 (0/59) | 0.85 | 0.84 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_high | e | 0.00 (0/59) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| rotating_high | e | 0.00 (0/59) | 0.74 | 0.91 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] | 73727 [41170, 113312] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 71, flagged 0.0, institutional-suppressed 2.0; rotating_high: tested 80, flagged 11.0, institutional-suppressed 2.2; rotating_medium: tested 80, flagged 11.0, institutional-suppressed 2.2; rotating_none: tested 80, flagged 11.0, institutional-suppressed 2.2; shared_high: tested 82, flagged 13.0, institutional-suppressed 2.2; shared_medium: tested 82, flagged 13.0, institutional-suppressed 2.2; shared_none: tested 82, flagged 13.0, institutional-suppressed 2.2

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 0.90, (a) 0.00, n=59 | fail |
| S2 | shared_medium | (c) 1.00 vs (b) 0.52, (a) 0.00, n=50 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.55, (a) 0.00, n=40 | pass |
| S4 | rotating_high/c | honest raised mean 0.6, max 1 | pass |
| S4 | rotating_medium/c | honest raised mean 0.6, max 1 | pass |
| S4 | rotating_none/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_high/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_medium/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_none/c | honest raised mean 0.6, max 1 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |

#### Dev seeds 1-3 only, WHERE+HOW, queue-persistent (d = frozen HOW, d2 = rejected variant)

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag day, median [CI] | CZK through the flag day (incl.), median [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/23) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] | 73486 [38229, 113742] |
| shared_none | b | 0.74 (17/23) | 0.95 | 0.86 | 0.0 / 0 | 0.0 | 14.0 [14.0, 32.0] | 2/6 | 44769 [36313, 110019] | 52601 [36313, 110019] |
| shared_none | c | 1.00 (23/23) | 1.00 | 0.85 | 0.7 / 1 | 0.7 | 7.0 [4.0, 8.0] | 0/6 | 4730 [0, 31207] | 17217 [8614, 38229] |
| shared_none | d | 1.00 (23/23) | 1.00 | 0.83 | 3.0 / 7 | 3.0 | 7.0 [4.0, 8.0] | 0/6 | 4730 [0, 31207] | 17217 [8614, 38229] |
| shared_none | d2 | 1.00 (23/23) | 1.00 | 0.69 | 23.7 / 32 | 23.7 | 7.0 [4.0, 8.0] | 0/6 | 4730 [0, 31207] | 17217 [8614, 38229] |
| shared_none | e | 0.13 (3/23) | 0.79 | 0.91 | 0.0 / 0 | 0.0 | 15.0 [8.0, 32.0] | 2/6 | 44769 [23034, 62856] | 52601 [36313, 74151] |
| shared_medium | a | 0.00 (0/31) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 113652] | 73582 [38163, 113652] |
| shared_medium | b | 0.55 (17/31) | 0.93 | 0.85 | 0.0 / 0 | 0.0 | 23.0 [14.0, 32.0] | 3/6 | 60727 [38163, 91870] | 68599 [38163, 91870] |
| shared_medium | c | 1.00 (31/31) | 1.00 | 0.85 | 0.7 / 1 | 0.7 | 7.0 [4.0, 8.0] | 0/6 | 4789 [0, 31098] | 17337 [8582, 38163] |
| shared_medium | d | 1.00 (31/31) | 1.00 | 0.84 | 2.7 / 7 | 2.7 | 7.0 [4.0, 8.0] | 0/6 | 4789 [0, 31098] | 17337 [8582, 38163] |
| shared_medium | d2 | 1.00 (31/31) | 1.00 | 0.69 | 23.3 / 28 | 23.3 | 7.0 [4.0, 8.0] | 0/6 | 4789 [0, 31098] | 17337 [8582, 38163] |
| shared_medium | e | 0.03 (1/31) | 0.76 | 0.91 | 0.0 / 0 | 0.0 | 24.0 [8.0, 32.0] | 3/6 | 46751 [36443, 95821] | 57209 [36443, 96237] |
| shared_high | a | 0.00 (0/36) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 117544] | 73727 [38064, 117544] |
| shared_high | b | 1.00 (36/36) | 1.00 | 0.86 | 0.0 / 0 | 0.0 | 14.0 [14.0, 16.0] | 0/6 | 39617 [27599, 50642] | 42405 [36306, 64323] |
| shared_high | c | 1.00 (36/36) | 1.00 | 0.85 | 0.7 / 1 | 0.7 | 7.0 [4.0, 8.0] | 0/6 | 4877 [0, 30934] | 17517 [9639, 38064] |
| shared_high | d | 1.00 (36/36) | 1.00 | 0.84 | 2.3 / 6 | 2.3 | 7.0 [4.0, 8.0] | 0/6 | 4877 [0, 30934] | 17517 [9639, 38064] |
| shared_high | d2 | 1.00 (36/36) | 1.00 | 0.69 | 23.3 / 29 | 23.3 | 7.0 [4.0, 8.0] | 0/6 | 4877 [0, 30934] | 17517 [9639, 38064] |
| shared_high | e | 0.00 (0/36) | 0.74 | 0.90 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 117544] | 73727 [38064, 117544] |
| rotating_none | a | 0.00 (0/23) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] | 73486 [38229, 113742] |
| rotating_none | b | 0.00 (0/23) | 0.85 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] | 73486 [38229, 113742] |
| rotating_none | c | 0.00 (0/23) | 0.85 | 0.83 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] | 73486 [38229, 113742] |
| rotating_none | d | 0.91 (21/23) | 0.98 | 0.83 | 3.0 / 7 | 3.0 | 7.0 [5.0, 10.0] | 0/6 | 16878 [4612, 31207] | 29575 [16304, 38229] |
| rotating_none | d2 | 1.00 (23/23) | 1.00 | 0.69 | 23.7 / 32 | 23.7 | 7.0 [4.0, 8.0] | 0/6 | 4730 [0, 31207] | 17217 [8614, 38229] |
| rotating_none | e | 0.00 (0/23) | 0.74 | 0.90 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] | 73486 [38229, 113742] |
| rotating_medium | a | 0.00 (0/31) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 113652] | 73582 [38163, 113652] |
| rotating_medium | b | 0.00 (0/31) | 0.85 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 113652] | 73582 [38163, 113652] |
| rotating_medium | c | 0.00 (0/31) | 0.85 | 0.83 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 113652] | 73582 [38163, 113652] |
| rotating_medium | d | 0.84 (26/31) | 0.97 | 0.83 | 2.7 / 7 | 2.7 | 8.0 [4.0, 20.0] | 0/6 | 16660 [0, 74017] | 27680 [10924, 74017] |
| rotating_medium | d2 | 0.94 (29/31) | 0.99 | 0.69 | 23.3 / 28 | 23.3 | 7.0 [4.0, 8.0] | 0/6 | 4789 [0, 31098] | 17337 [8582, 38163] |
| rotating_medium | e | 0.00 (0/31) | 0.74 | 0.90 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 113652] | 73582 [38163, 113652] |
| rotating_high | a | 0.00 (0/36) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 113517] | 73727 [38064, 113517] |
| rotating_high | b | 0.00 (0/36) | 0.85 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 113517] | 73727 [38064, 113517] |
| rotating_high | c | 0.00 (0/36) | 0.85 | 0.83 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 113517] | 73727 [38064, 113517] |
| rotating_high | d | 0.25 (9/36) | 0.89 | 0.82 | 2.3 / 6 | 2.3 | 7.0 [5.0, 32.0] | 2/6 | 16883 [4755, 74516] | 29213 [16571, 74516] |
| rotating_high | d2 | 0.69 (25/36) | 0.95 | 0.68 | 23.3 / 29 | 23.3 | 7.0 [4.0, 12.0] | 0/6 | 11120 [0, 36638] | 23029 [10801, 38064] |
| rotating_high | e | 0.00 (0/36) | 0.74 | 0.90 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 113517] | 73727 [38064, 113517] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | d | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | d2 | – (0/0) | – | 0.00 | 13.0 / 32 | 13.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 72, flagged 0.0, institutional-suppressed 1.7; rotating_high: tested 84, flagged 11.0, institutional-suppressed 2.0; rotating_medium: tested 84, flagged 11.0, institutional-suppressed 2.0; rotating_none: tested 84, flagged 11.0, institutional-suppressed 2.0; shared_high: tested 86, flagged 13.0, institutional-suppressed 2.0; shared_medium: tested 86, flagged 13.0, institutional-suppressed 2.0; shared_none: tested 86, flagged 13.0, institutional-suppressed 2.0

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S1 | crimefree/d | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 1.00, (a) 0.00, n=36 | fail |
| S2 | shared_medium | (c) 1.00 vs (b) 0.55, (a) 0.00, n=31 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.74, (a) 0.00, n=23 | fail |
| S3 | rotating_medium | (d)-(c) = 0.84, n=31 | pass |
| S3 | rotating_none | (d)-(c) = 0.91, n=23 | pass |
| S4 | rotating_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_high/d | honest raised mean 2.3, max 6 | pass |
| S4 | rotating_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_medium/d | honest raised mean 2.7, max 7 | pass |
| S4 | rotating_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_none/d | honest raised mean 3.0, max 7 | pass |
| S4 | shared_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_high/d | honest raised mean 2.3, max 6 | pass |
| S4 | shared_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_medium/d | honest raised mean 2.7, max 7 | pass |
| S4 | shared_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_none/d | honest raised mean 3.0, max 7 | pass |
| S5 | rotating_medium | median first day (a) 32.0 vs (d) 8.0; never flagged (a) 6/6, (d) 0/6 | pass |
| S5 | rotating_none | median first day (a) 32.0 vs (d) 7.0; never flagged (a) 6/6, (d) 0/6 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 7.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 7.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 7.0; never flagged (a) 6/6, (c) 0/6 | pass |

## pitch_numbers.json
The existing keys are unchanged from main (weak-evidence radar, held-out seeds 707/808, from the earlier frozen radar experiment). The new `collector` block is written by `scripts/collector_pitch.py` and reads only the frozen test runs (`eval/out/collector/test_how_summary.json` and `test_how_cum_summary.json`, seeds 4101/4202/4303). It contains both the non-cumulative and the queue-persistent (d) numbers. No dev number is in it.

## Service and UI
`collector/service.py` (POST /rounds/{id}/submit, GET /rounds/{id}/flags; 409 on a missing bank), `node/collector_cli.py submit|expand`, `make demo-collector` (3 bank processes and the collector; logs show only masked vectors and sums), `outbreak/index.html` (the Outbreak demo view as a standalone page; case cards carry the badge "Raised by network"). The old Stáj UI was not touched, by the owner's instruction.
