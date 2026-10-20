LIM = """14. **Collector (pre-registered experiment, eval/collector_report.md).** Synthetic worlds only; one team writes generator and detectors. The planted cash-out account has no honest payers, which makes shared-hub detection easy; real hubs mix honest and mule payers. If the collector colludes with all but one bank, that bank's counts are revealed. A round needs all banks (no dropout recovery). The baseline has 30 days of history (cloned from the evaluation month). The existing radar (b) catches some stealth mules on some days of the month, so conclusions depend on whether a flag persists in the queue. HOW was frozen on 3 dev seeds and its test-seed run is not part of the frozen results until it is run. The legal status of sharing counts about all customers is not confirmed.
"""
RD = """
## Built during the hackathon: Collector (night 19->20.10)
A second shared node that receives masked counts about ALL customers of all banks (never customer-level data), finds unusual pass-through destinations (WHERE) and unusual skim/delay patterns (HOW), and returns only flagged bucket ids and windows. Each bank then raises its own matching customers once; the analyst decides.
- Pre-registration: `eval/prereg_collector.md` (+ `eval/prereg_collector_amendment2.md`); results and every failure: `eval/collector_report.md`.
- Code: `node/signatures.py`, `node/secagg.py`, `node/expansion.py`, `node/collector_cli.py`, `collector/` (aggregation, statistics, FastAPI service), `redteam/generate_collector.py`, `eval/collector_*.py`.
- Demo: `make demo-collector`, then `python -m http.server 8200 -d outbreak` (Outbreak page, a demo view).
- LIMITATIONS: synthetic worlds; one team builds generator and detectors; the collector colluding with all but one bank breaks secrecy; no dropout recovery; short-history baseline; legal status not confirmed (see `LIMITATIONS.md` item 14).
"""
open("LIMITATIONS.md", "a", encoding="utf-8").write(LIM)
open("README.md", "a", encoding="utf-8").write(RD)
