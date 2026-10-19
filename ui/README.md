# Stáj UI

Analyst front-end for Stáj. Built with Vite, React 18, TypeScript, Tailwind CSS 3, Cytoscape.js and Recharts. Czech is the default language, with an English toggle in the top bar. All versions are pinned in `package.json`.

## Run against mocks (no backend)

```bash
cd ui
npm install
npm run dev          # http://localhost:5173
```

If `VITE_API_BASE` is not set, `src/api.ts` reads static files from `public/mock/*.json`. A **MOCK** banner is shown on every screen in this mode. Every number in the mocks is invented for layout only.

The write endpoints (decision, section V save, explain, ask) are simulated in memory and reset on page reload. The mock decision check copies the server rules: relationship owner, rule author, first triager, four-eyes at priority >= 70, role below the escalation target, and an override reason shorter than 10 characters. The real server is the authority on all of these.

Regenerate the mocks deterministically with:

```bash
node scripts/gen-mocks.mjs
```

Mock cases with full cards: `B1-R00123` (cluster K1, high priority, with an "ask" answer), `B2-R00087` (K1, real-backend-style template ids, no explanation yet, so you can test "Generate"), `B1-R00311` (FP "mom" case with E1/E3), `B3-R00045` (victim protection), `B2-R00210` (PEP), `B3-R00167` (already decided, with QA violations). OPO drafts exist for `B1-R00123` and `B2-R00210`.

Demo conflict: the default identity "Eva Horáková" is the relationship owner of `B2-R00087`, so a decision there is rejected with `decider_is_relationship_owner`.

## Run against the real API

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5173
# PowerShell: $env:VITE_API_BASE="http://127.0.0.1:8000"; npm run dev -- --host 127.0.0.1 --port 5173
```

The backend must allow CORS from the dev origin. It can also serve `dist/` after you run `npm run build`.

A decision rejected with HTTP 4xx is still shown correctly, as long as the JSON body contains `violations`.

Slow calls, all with a visible loading state:

- **First open of `/opo/:id`** runs an LLM draft on the server, which takes about 1–2 minutes. The screen shows the elapsed time. Only the OPO screen triggers it, and concurrent requests are de-duplicated (React StrictMode would otherwise send two). The Markdown export button stays disabled until the draft exists, because `export.md` would otherwise start a second draft.
- **"Generate explanation"** and **"Ask about a rule"** on the case card only run when a person clicks them. "Ask" can take up to about 1 minute.

Note: every call to `POST /decision` writes to the audit chain, including rejected decisions (`decision_rejected`), and so does `POST /ask` (`rule_question`).

Screenshots from the run against real data (1440x900) are in `screenshots/`.

## Checks

```bash
npm run typecheck    # tsc --noEmit
npm run build        # typecheck + production build to dist/
```

## How the UI reads the contract

- **Metrics `breakdown`:** keys are grouped by prefix. `scheme:*` is detection per scheme, `persona:*` is the FP rate for honest personas, `victim:*` is victim routing, and `other:*` (or no prefix) is listed under "Other".
- **Metrics modes:** for each mode the UI shows `rank.average_precision` (AP) and `rank.precision_at_k` (P@K, with K). `overall_any_priority` appears as a sub-row. The isolated mode's `per_bank`, `best_single_bank_f1` and `mean_bank_f1` get their own block.
- **Ablations:** ΔF1 is measured against `ablations.full` when it exists. Otherwise it is measured against `modes.staj_psi.overall`.
- **Optional metric sections:** `headline_held_out_mean`, `threshold_curve_held_out_mean` and `ring_size_sweep` are rendered generically when present (array of objects, object of objects, or key/value) and skipped when absent.
- **`cnb`:** shown with its own `dataset` label. If `sample_sheet_url` is not an http(s) URL or an absolute path, it is shown as a server file path rather than a link.
- **Signal sentence:** if `Signal.template` contains `{evidence_key}` placeholders, they are filled in from `evidence`. If it is a bare id (e.g. `d5_rare_exit_concentration`), `rule_definitions[detector_id]` is shown as the plain sentence, with the template id underneath.
- **Evidence and features:** numeric arrays of 8 or more values (e.g. `hour_hist`) are drawn as a mini histogram, and string arrays as chips. Feature descriptions come from `feature_glossary`.
- **Refs:** refs on explanation, ask and OPO sentences are clickable. These forms work:
  - `D5:R03035`, which highlights that signal
  - `D6:R03035.evidence`, which also highlights the signal
  - `features.x` or `feature:x`, which open the feature list
  - `cluster:*` or `X:*`, which scroll to the cluster card
- **Case card:** "Účty za dropy / Accounts behind the drops" lists `cluster.matched_exit_accounts`. These are plaintext only at the owning bank, and Stáj does not resolve who owns them.
- **Radar `wire`:** sessions shaped `A:B` (or `AxB`) are animated as hex ciphertext, truncated to 96 hex characters with the full value in the tooltip. The `coordinator` session carries match-row objects and is shown as a table.
- **Queue:** the server caps `items` at 500 and reports `total_matching`. When the list is capped, the UI says so and offers a "REVIEW only" filter.
- **Staff:** the decider and approver lists come from `meta.staff` when the server sends it. Otherwise a local demo list is used (`src/state.tsx`).
