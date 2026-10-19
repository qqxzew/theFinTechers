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
