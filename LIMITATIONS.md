# Limitations (read before believing any number)

1. **No mule networks in the ČNB data.** All cross-bank results come from PLANTED red-team data. Detection rates measure how well we recognise our own scheme definitions; they say nothing about real-world recall or precision.
2. **The red-team generator and the detectors were written by the same team.** The persona separators (E6–E8) were designed after seeing false positives on our own personas; their false-positive rate on real customers is unknown. A mule who imitates an ordinary spending life would defeat them.
3. **Tuning on dev seeds.** D6 thresholds and the radar candidate band were chosen on dev seed 7; seed 101 was also used in sweeps. Headline numbers use held-out seeds (see `eval/report.md`); once a held-out seed is looked at for tuning it is no longer held-out.
4. **Rule A is noise at CNB scale** (60–99.9 % of clients under every unit interpretation). The value is in triage, not in the rule.
5. **`naive_raw_sharing` is not a guaranteed upper bound**: it pools raw data into one node with thresholds calibrated per bank.
6. **PSI is semi-honest DH-PSI.** Probing and token poisoning are mitigated by guards and humans-in-the-loop, not eliminated. No Clean Rooms / Nitro Enclaves are used. **PSI is not a legal basis**: sharing needs the banking-secrecy change (§ 38 Act 21/1992; planned Safe-D) and, under EU AMLR Art. 75 (from 10 July 2027), a notified partnership with a DPIA.
7. **Placeholders:** FX rates, escalation matrix, bank settings (sender/contact), model prices (budget guard-rails only). The EU high-risk list was compiled from web search and not verified against the consolidated EUR-Lex text; FATF lists were read from the FATF page (19 June 2026 plenary).
8. **Out of scope for the data we have:** card, ATM, merchant, device and IP detectors (interfaces only). Behavioural/device vendors (ThreatMark, BioCatch) cover that part and are complementary.
9. **Deployment:** the three bank nodes run in one process in this repository (data separation is real, process separation is not); `docker compose`, mutual TLS and per-bank key stores are planned.
10. **LLM:** explanations are validated for supported numbers and references, not for semantic correctness (a model once described a retention *ratio* as a duration); a human reads every draft. Latency measured on 2026-10-19: Kimi-K3 ≈ 3 min per task, Claude Sonnet 4.5 ≈ 40–50 s. Costs shown use placeholder prices.
11. **IBM AMLworld evaluation not yet computed.**
12. The OPO is a **draft**: sections VI (executed/not executed/postponed) and IX (submission) are left to a human; no analyst name appears in the body.
