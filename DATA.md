# Data

**Everything is synthetic. No real PII. Raw data is never committed (`data/` is in `.gitignore`).**

| Dataset | What | How obtained | Used for |
|---|---|---|---|
| ČNB hackathon dataset | `transactions.csv` (397,853 rows, 1–31 July 2026), `clients.csv` (5,493 rows); semicolon-separated, UTF-8 BOM | organisers' bucket `s3://ai-hackathon-datasets-422928733782/CNB/`; local copy identical in size (36,474,908 / 497,141 bytes); row counts verified | FINREG rules A/B/C, background "normal life" for the red-team world, CNB evaluation |
| IBM AMLworld `HI-Small` (Altman et al., NeurIPS 2023) | 5,078,345 transactions + patterns file (generic laundering: fan-out, cycle, …) | Kaggle `ealtman2019/ibm-transactions-for-anti-money-laundering-aml` | downloaded; **evaluation not yet computed**; these are generic patterns, **not Czech mule schemes** |
| Red-team world | 3 banks, ≈3,000 background clients resampled from ČNB (they keep their real external counterparties, split disjointly over the banks) + PLANTED schemes and honest look-alikes | generated locally by `python -m redteam.generate --seed N` (seeded, reproducible) | blue-team evaluation; labels are in `labels.parquet`, read only by `eval/` |

`data/MANIFEST.json` lists file, size, SHA-256, row count and columns (`python ingest/manifest.py`).

## Established facts about the ČNB data (verified by code, see `docs/DECISIONS.md`)
- Directions: 187,152 outgoing, 170,986 incoming, 39,715 remittances (outgoing cross-border).
- The `volume` column is already CZK-denominated for every currency (median ≈ 3,000 for CZK, EUR, JPY, HUF, KRW, ZAR alike); `config/fx.yaml: volume_is_czk: true`. FX rates themselves are placeholders.
- **The data contain no mule networks**: client→external→client relay matches equal a shuffled baseline (19,840 vs 19,717–19,821; with exits of degree ≤ 10: 1 vs 3–6). The 16 clients hit by rule C are large, long-standing, ordinary-looking clients.
- None of the 33 country codes in the data is on the FATF or EU high-risk lists, so the country condition of rule B never fires; its 4 alerts are PEP-related.
- Rule A fires on 60–99.9 % of clients under every unit interpretation.

## Planted in the red-team world (all labelled `planted`)
Mule schemes: day-zero handover, same hand, stealth same hand (small per-account volumes, signal only across banks), fixed skim, business-to-personal invoice mule. Victim draining own savings (must be routed to victim protection). Honest look-alikes: migrant remittances, students splitting rent, second-hand seller, group collection, co-host middleman, freelancer, fundraiser. Parameters are randomised within documented ranges; the generator is a separate package that the detectors never import (import-linter rule).

## Canonical schema
`tx_id, bank_id, client_id (pseudonymous), ts (UTC), amount_czk, amount_orig, currency, direction {in,out,remit_out}, own_account, counterparty_token, payer_country, payee_country, channel_type, source_dataset` and a client table (`common/schemas.py`).
