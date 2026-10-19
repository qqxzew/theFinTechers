# Decision log

| # | Date | Decision | Why |
|---|---|---|---|
| D-001 | 2026-10-19 | ČNB local copy of `transactions.csv`/`clients.csv` (identical to `s3://ai-hackathon-datasets-422928733782/CNB/`, same sizes 36474908 / 497141 bytes) is used from `data/raw/cnb/`. | Already downloaded by the team; verified row counts 397,853 / 5,493 and direction counts 187,152 out / 170,986 in / 39,715 remittance. |
| D-002 | 2026-10-19 | ČNB timestamps are read as Europe/Prague local time and converted to UTC. | Source gives no zone; local time is the natural reading for a Czech bank. |
| D-003 | 2026-10-19 | Client column parsing is positional, not by header text. | Header spelling in the source differs from the spec ("at the time" vs "at thetime"). |
| D-004 | 2026-10-19 | Work is split into small tasks executed by sandboxed Kimi-K3 workers (`orchestrator/`); acceptance tests are written by the orchestrator, not by the worker. | Workers are weak; prevents self-grading. |
| D-005 | 2026-10-19 | High-risk jurisdiction lists compiled from web search (EU Del. Reg. 2026/46 etc.); FATF grey list left empty and flagged unverified (fatf-gafi.org returned 403). | Never guess lists. Only ZA and TR from the ČNB country set were ever candidates; ZA was removed from the EU list by 2026/83, so rule B country-condition will almost never fire on ČNB data (PEP condition will). |
