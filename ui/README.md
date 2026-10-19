# Stáj UI

Analyst front-end for Stáj. Built with Vite, React 18, TypeScript, Tailwind CSS 3, Cytoscape.js and Recharts. Czech is the default language, with an English toggle in the top bar. All versions are pinned in `package.json`.

## Run against mocks (no backend)

```bash
cd ui
npm install
npm run dev          # http://localhost:5173
```

If `VITE_API_BASE` is not set, `src/api.ts` reads static files from `public/mock/*.json`. A **MOCK** banner is shown on every screen in this mode. Every number in the mocks is invented for layout only.

The write endpoints (decision, section V save, explain) are simulated in memory and reset on page reload. The mock decision check copies the server rules: relationship owner, rule author, first triager, four-eyes at priority >= 70, role below the escalation target, and override without a reason. The real server is the authority on all of these.

Regenerate the mocks deterministically with:

```bash
node scripts/gen-mocks.mjs
```

Mock cases with full cards: `B1-R00123` (cluster K1, high priority), `B2-R00087` (K1, no explanation yet, so you can test "Generate"), `B1-R00311` (FP "mom" case with E1/E3), `B3-R00045` (victim protection), `B2-R00210` (PEP), `B3-R00167` (already decided, with QA violations). OPO drafts exist for `B1-R00123` and `B2-R00210`.

Demo conflict: the default identity "Eva Horáková" is the relationship owner of `B2-R00087`, so a decision there is rejected with `decider_is_relationship_owner`.

## Run against the real API

```bash
VITE_API_BASE=http://localhost:8000 npm run dev
# PowerShell: $env:VITE_API_BASE="http://localhost:8000"; npm run dev
```

The backend must allow CORS from the dev origin (`http://localhost:5173`). It can also serve `dist/` after you run `npm run build`.

A decision rejected with HTTP 4xx is still shown correctly, as long as the JSON body contains `violations`.

## Checks

```bash
npm run typecheck    # tsc --noEmit
npm run build        # typecheck + production build to dist/
```

## Assumptions about the contract

- `/api/metrics` `breakdown` keys are grouped by prefix: `scheme:*` (detection per scheme), `persona:*` (FP rate for honest personas) and `victim:*` (victim routing). Keys without a prefix are listed under "Other".
- `failures.*` items are rendered generically. The known keys are `case_id`, `client_ref`, `signals`, `why` and `missed_because`, and any other fields are listed as key/value pairs.
- Explanation `refs` such as `cluster:K1` and `feature:is_pep` are clickable and scroll to the cluster card or the feature list. Refs that match a `signal_id` highlight that signal.
- `Signal.template` may contain `{evidence_key}` placeholders, which are filled in from `evidence`.
- The approver list is a local demo staff directory (`src/state.tsx`). The API has no staff endpoint.
