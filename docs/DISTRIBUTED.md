# Stáj – distributed mode (one process per bank node + a radar coordinator)

All data is synthetic. This document describes what `node/service.py`, `radar/service.py`, `radar/transport.py`,
`scripts/run_local_cluster.py` and `infra/docker-compose.yml` actually do, and what they do **not** protect.

The in-process path (`radar/sessions.py::run_radar`, used by `eval/` and `api/`) is unchanged. The distributed mode reuses the same
modules: `node.pipeline.run_node` / `apply_clusters`, `radar.psi.dh_psi.PsiParty`, `radar.guards.Guards`,
`radar.clustering.build_clusters`, `radar.sessions.token_id` / `_bucket`, `audit.log.AuditLog`. Two small pieces are **replicated**
rather than imported, and say so in their docstrings:
- `node.service.BankView.of` = `eval.redteam_eval.to_bank_node` (node/ must not import eval/ – import-linter contract);
- `radar.service.post_match` = the loop after `build_clusters` in `run_radar` (same-hand-global concentration + 6.4 summary), because
  `run_radar` does not expose it as a function. Test (a) proves both produce identical clusters, scores and post-match summaries.

## 1. Architecture

```
  process: node B1 (:8101)          process: node B2 (:8102)          process: node B3 (:8103)
  ┌───────────────────────┐         ┌───────────────────────┐         ┌───────────────────────┐
  │ own rows only (B1)    │         │ own rows only (B2)    │         │ own rows only (B3)    │
  │ run_node -> cases     │         │ run_node -> cases     │         │ run_node -> cases     │
  │ bank secret, epoch key│         │ bank secret, epoch key│         │ bank secret, epoch key│
  │ PSI exponent / session│         │ PSI exponent / session│         │ PSI exponent / session│
  │ own audit chain       │         │ own audit chain       │         │ own audit chain       │
  └──────────┬────────────┘         └──────────┬────────────┘         └──────────┬────────────┘
             │ HTTP/JSON: counts, blinded hex elements, keyed match rows, 6.4 cluster summary
             └──────────────────────────────┬──────────────────────────────────┘
                              process: radar coordinator (:8200)
                              ┌───────────────────────────────────────┐
                              │ Guards on counts | relays PSI hex     │  no exponents, no tokens,
                              │ build_clusters + post_match           │  no epoch key, no client ids
                              │ /wire (verbatim, capped) | own audit  │
                              └───────────────────────────────────────┘
```
In docker compose each node is on its own network shared only with the radar (`net-b1/2/3`): nodes cannot reach each other directly.

## 2. Message flow of one round (`POST radar /run`)

| # | radar -> node | node -> radar |
|---|---|---|
| 1 | `GET /submission` (every node) | `{token_count, unscored_count, scored_share}` -> radar applies `Guards` (min/max set size, unscored share, rate) |
| 2 | `POST A /psi/blind {session_id, peer}` | `{blind: [H(x)^a ...]}` shuffled, fresh exponent `a` for this session |
| 3 | `POST B /psi/respond {session_id, peer, incoming}` | `{double: [H(x)^ab], blind: [H(y)^b]}` – B first runs its own guards on the incoming set (singleton probes refused, 403) |
| 4 | `POST A /psi/finish {session_id, double, blind}` | `{back: [H(y)^ba]}` – A learns its matched tokens **locally** and forgets `a` |
| 5 | `POST B /psi/learn {session_id, returned}` | `{ok}` – B learns its matched tokens locally and forgets `b` |
| 6 | `GET /session/{round}/match-rows` (every live node) | `{rows: [{token_id, bank_id, cand_ref, rarity}], stats: [{cand_ref, lag_bucket_h, retention_bucket}]}` |
| 7 | radar: `build_clusters(rows)` + `post_match` | – |
| 8 | `POST /clusters {round_id, clusters}` – per bank only disclosed clusters it is in, only its own refs + 6.4 summary | node runs `apply_clusters` on its own cases |

Steps 2–5 run for every pair (A < B in bank-id order), exactly the order of `run_radar`. Session ids are `<round>:<A>:<B>`; a node
refuses a session it is not party to, a wrong role, a peer mismatch or a reused session id (replay), and audit-logs the refusal.

## 3. What crosses each boundary

| Boundary | Crosses | Never crosses |
|---|---|---|
| node -> radar `/submission` | token count, unscored count, scored share | tokens, scores per token, client ids |
| node <-> radar <-> node, PSI | 512-hex-char elements of the order-q subgroup of RFC 3526 group 14, blinded under per-session exponents | plaintext tokens, unblinded `H(x)`, exponents |
| node -> radar match rows | `token_id` = HMAC(epoch key, token)[:16], `bank_id`, `cand_ref` = HMAC(bank secret, client id)[:12], rarity, lag bucket (1 h), retention bucket (2 pp) | tokens, client ids, raw lag/retention, amounts, timestamps |
| radar -> node `/clusters` | for disclosed clusters the bank is in: cluster id, score, same-hand flag, the bank's OWN cand_refs, n other banks, n other candidates, matched token ids, lag/ret concentration | other banks' cand_refs or client ids, names, transactions |
| node internal only | `/cases`, `/cases/{id}` (case JSON + timeline), `/audit` | – the radar never calls these; production binds them to the bank's internal network |

Secrets: each node's bank secret and the epoch key come from its environment (`STAJ_BANK_SECRET`, `STAJ_EPOCH_KEY`). The banks share the
epoch key out of band; the radar process is started without it (`run_local_cluster.py` strips all `STAJ_*` variables from the radar's
environment; in compose the radar service has no `STAJ_EPOCH_KEY`). No node ever opens `labels.parquet`; it reads tx/clients with a
lazy parquet scan filtered on its own `bank_id`.

## 4. What is NOT protected (be honest)

- **Semi-honest model.** Parties are assumed to follow the protocol. A malicious bank can put arbitrary tokens in its set (probing
  whether an account is a candidate elsewhere, or poisoning with fake tokens) – guards only bound the set size, unscored share and
  session rate; they cannot tell a real candidate set from a crafted one of the right size. A malicious node can also abort after it
  learned its result (step 4) so the peer learns nothing.
- **The relay learns intersection sizes.** The radar sees both double-blinded sets of a session (`double` in step 3 and `back` in step 4)
  and can count equal elements, i.e. it learns |A ∩ B| per pair (not which tokens). Test (e) demonstrates this. It learns the same
  information from the match rows anyway; end-to-end encryption between nodes (radar as an opaque relay) would remove it.
- **Traffic analysis.** Message sizes reveal each bank's candidate-set size; timing reveals pipeline effort.
- **Coordinator compromise** reveals pseudonymous cand_refs, keyed token ids, coarse buckets and cluster structure, not tokens or
  client ids. A coordinator that colludes with one bank can link that bank's tokens to token ids for clusters it is in (the bank knows
  the epoch key).
- **Epoch key handling** is an environment variable; there is no rotation, no KMS, no per-bank key store.
- **No transport security.** Plain HTTP on localhost / a docker network: no mutual TLS, no request signing, no authentication of the
  radar to the nodes (any caller that can reach a node port can drive PSI against it, within the node's guards and rate limit).
- **Still one machine.** Separate processes and (in compose) separate containers and networks, but one host, one kernel, one operator,
  and in compose the same read-only world directory mounted into every node (each node filters to its own rows itself). A real
  deployment gives each bank its own storage and infrastructure. AWS Clean Rooms (cryptographic computing) or Nitro Enclaves would be
  hardened alternatives – **neither is used here**.
- `cardinality_only` PSI mode is not exposed over HTTP. The UI/API (`api/`) still uses the in-process path, not these services.
- PSI minimises what is shared; it is **not a legal basis** for sharing (see ARCHITECTURE.md).

## 5. Audit

Every node keeps its **own** hash-chained log (`audit.log.AuditLog`, path from `STAJ_NODE_AUDIT`): one entry per PSI call it served
(`psi_blind`, `psi_respond`, `psi_finish`, `psi_learn`, or `psi_refused`) with actor, session, peer and element/match counts – never
tokens – plus `node_started`, `match_rows_released`, `clusters_applied`. The radar keeps its own (`STAJ_RADAR_AUDIT`):
`submission_refused`, `psi_session_relayed` / `psi_session_failed`, `cluster_disclosed`, `round_done`. `GET /audit/verify` on every
service re-verifies its chain.

## 6. How to run

```bash
# 3 node processes + radar on ports 8101-8103 / 8200, one round, clusters + traffic summary + leak check, then teardown
PYTHONPATH=. .venv/Scripts/python scripts/run_local_cluster.py                       # data/redteam/seed101 (slow: full pipeline per node)
PYTHONPATH=. .venv/Scripts/python scripts/run_local_cluster.py data/redteam/seed909  # small world
#   (create it once: python -m redteam.generate --seed 909 --out data/redteam/seed909 --n-per-bank 300)
# logs and audit chains: eval/out/dist/

# single services by hand
STAJ_EPOCH_KEY=k STAJ_BANK_SECRET=s1 python -m node.service --bank B1 --world data/redteam/seed909 --port 8101
python -m radar.service --nodes B1=http://127.0.0.1:8101,B2=http://127.0.0.1:8102,B3=http://127.0.0.1:8103 --port 8200
curl -X POST localhost:8200/run; curl localhost:8200/clusters?disclosed_only=true; curl 'localhost:8200/wire?summary=true'

# containers (node-b1..b3, radar, api, ui)
STAJ_EPOCH_KEY=$(openssl rand -hex 16) docker compose -f infra/docker-compose.yml up --build
curl -X POST localhost:8200/run
```

Measured once (seed909, 3 x ~340 clients, real subprocesses, shared laptop under load): 3 PSI sessions with 1,038 / 1,106 / 1,060
relayed elements, 21 HTTP exchanges, 3.34 MB on the wire, round time 125 s (dominated by 2048-bit modular exponentiation in pure
Python), 5 disclosed clusters, leak check clean, all four audit chains verify.

## 7. Tests

```bash
PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python -m pytest tests/integration/test_distributed.py -q        # in-memory ASGI, no ports
STAJ_SLOW_TESTS=1 PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python -m pytest tests/integration/test_distributed.py -q -k real_processes  # real subprocesses
```
`tests/integration/test_distributed.py` uses `data/redteam/seed909` (generated on first use) and checks:
(a) the distributed round discloses the same clusters as `run_radar` on the same node results (member sets as (bank, cand_ref),
token ids, cluster ids, scores, same-hand flags, post-match summaries) and the node-side cases after `/clusters` equal in-process
`apply_clusters`; (b) every request/response recorded by the radar's transport **and** by each node's ASGI traffic recorder contains no
counterparty token (all of tx.parquet), no client id / own account (the cand_ref preimages), no tx id, no timestamp, no transaction
amount, no bank secret or epoch key, and no JSON key outside a whitelist (no raw tx column names); every PSI element is 512 hex chars
and in the prime-order subgroup; the relay forwards only elements that a node produced; (c) a singleton probe at `/psi/respond` is
refused (403, `min_set_size`) and audit-logged; (d) each node's chain verifies and has exactly one `psi_*` entry per `/psi/*` call it
served; (e) a coordinator with all recorded traffic: no token, no unblinded `H(t)` for any known token, elements of two rounds are
disjoint (fresh exponents) – and, documented as a known leak, it can compute per-pair intersection sizes.
