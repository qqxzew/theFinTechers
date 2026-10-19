# Pre-registration: weak-evidence radar (written BEFORE implementation and before any run on seeds 707 and 808)

Branch `radar-weak-evidence`. Date: 2026-10-19/20 (hackathon night).

## Problem
The radar compares only candidates that are already locally suspicious (case probability >= `token_export.min_prob`). A stealth mule with no local signal exports no token, so the radar has nothing to compare (audit finding: 7 of 15 stealth accounts on seed 101).

## Change under test
1. **Weak band:** in addition to the strong band, each bank exports the low-degree exit tokens of its top `weak_top_frac` clients by a local pass-through score (never the whole customer base; the fraction is the privacy knob).
2. **Match significance:** a cross-bank token match is scored by how improbable it is under random overlap: per bank a hypergeometric tail (eligible pool N, local degree of the token K, exported candidates n, observed x), combined across banks with Fisher's method, Bonferroni-corrected by the number of exported tokens. Popular tokens are discounted by construction (large K).
3. **Cluster boost** uses the significance instead of cluster size/rarity. Disclosure rule of the master prompt (>= 2 banks, >= 3 candidates) stays; an additional significance gate (adjusted p <= 0.01) can only withhold more.

## Procedure (fixed in advance)
1. Implement on the branch; unit tests including a null calibration test (random tokens must almost never be significant).
2. Choose `weak_top_frac` on DEV seeds only (7, 101, 202, 303, 404, 505, 606; all already seen) from {0, 0.05, 0.10, 0.20, 0.40}: the SMALLEST value whose dev-mean stealth recall is >= 90 % of the best value in the sweep and whose FP count is <= baseline FP + 1 on every dev seed. No other parameter is tuned afterwards.
3. Commit the frozen config and tag `prereg-config-frozen`. Generate seeds 707 and 808 only after the tag. Run BASELINE (`weak_top_frac = 0`, i.e. current main behaviour) and NEW once on each.
4. Report everything, including a privacy-cost curve (dev seeds): stealth recall vs exported tokens vs false disclosed clusters.

## Success criteria (held-out seeds 707 and 808, operating point: REVIEW, mule route, priority >= 30)
* **Primary:** mean stealth recall (flagged same_hand_stealth accounts / all) of NEW >= baseline + 0.10 (absolute).
* **Guard 1:** false positives (non-mule accounts flagged) of NEW <= baseline + 1 on each seed.
* **Guard 2:** no disclosed cluster contains a non-mule candidate more often than the baseline does.
* **Guard 3:** all existing tests stay green.
* If any criterion fails: `main` stays unchanged, the negative result is reported as is, and the current pitch stays ("same recall, zero raw records exposed").

## Not done here (listed as next steps)
Second round with a lowered local threshold for payers to a significant account (guilt-by-association risk; needs human check), and time buckets in tokens (§5.5).

---
## AMENDMENT 1 (written after the first dev sweep, BEFORE seeds 707/808 exist)

**Finding.** On the 7 dev worlds the baseline (no weak band, no significance) already reaches stealth recall 1.0 with the radar (isolated 0.79-1.0; the radar rescues 6 of 6 accounts that single banks miss: seeds 101, 303, 606). The weak band has therefore NO headroom on the existing scenarios, while it multiplies the exported tokens (mean 224 -> 1,463 at 5 %, 2,431 at 10 %, 4,536 at 20 %) and the bytes (x8-x13), and at 20 %/40 % it LOWERS recall (disclosed clusters fall from 3 to 0.9/0) because more exported candidates make a match less significant. Raw output: `eval/out/weak_sweep_v1_dev_ceiling.json`. By the rule of step 2 the smallest qualifying fraction on those worlds is 0 (no weak export).

**Why a new scenario.** To test the actual hypothesis (accounts with NO usable local signal) a scenario with real headroom is needed. It is added openly, after seeing the ceiling, and reported separately from the original schemes (original-scheme metrics must not get worse).

**`ghost_ring` (planted, synthetic; fixed in advance).** 9 established accounts (3 per bank): contract 1-5 years old, expected volume 200-400 k CZK with a consistent Q2 history (q2_volume = 3x expected, q2_max 20 k), two single pass-through cycles on distinct days (inflow 4-9 k CZK from a fresh payer; one outflow 88-92 % of it after the operator's lag of 2-4 h to ONE of 2 exit accounts shared by the whole ring), the operator's active hours 18-21, plus 6-12 ordinary small payments to popular accounts (they imitate an ordinary life, so E2 fires). No rule, detector or innocence-defeating signal is designed to fire locally; the expected baseline outcome is that they have no case at all. Planted last, with its own RNG, so existing worlds are unchanged.

**Priority floor (part of the change under test).** A member of a disclosed cluster with significance gate ON gets priority >= 30 + round(20 x x_score): statistical evidence of coordination must not be erased by a faked ordinary life. Members are REVIEW (never auto-closed) as before.

**Revised success criteria** (held-out seeds 707 and 808, operating point REVIEW + mule route + priority >= 30):
* **Primary:** mean ghost_ring recall of NEW >= baseline + 0.30 (absolute).
* **Guard 1:** FP of NEW <= baseline + 1 on each seed.
* **Guard 2:** recall on the ORIGINAL mule schemes of NEW >= baseline recall on each seed.
* **Guard 3:** disclosed non-mule candidates of NEW <= baseline's on each seed (baseline expected 0).
* **Guard 4:** all existing tests stay green.
* Fraction choice (dev seeds with ghost_ring, regenerated): the SMALLEST `weak_top_frac` in {0.05, 0.10, 0.20, 0.40} whose dev-mean ghost recall is >= 90 % of the best sweep value and whose FP is <= baseline + 1 on every dev seed. If no fraction yields dev-mean ghost recall > baseline + 0.30, the experiment is declared negative WITHOUT running seeds 707/808 and `main` stays unchanged.
