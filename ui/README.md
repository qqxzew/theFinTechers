# Stáj UI

The analyst front-end for Stáj, in English only. Built with Vite, React 18, TypeScript, Tailwind CSS 3, Cytoscape.js and Recharts, with all versions pinned in `package.json`.

## Run

```bash
cd ui && npm install
# against the real API
VITE_API_BASE=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5173
# PowerShell: $env:VITE_API_BASE="http://127.0.0.1:8000"; npm run dev -- --host 127.0.0.1 --port 5173
# against mocks (public/mock/*.json, regenerate with: node scripts/gen-mocks.mjs)
npm run dev
npm run build        # typecheck + production build
```

In mock mode a quiet amber note says the data is mock. In real-API mode nothing is shown. The write endpoints are simulated in memory in mock mode.

Routes and navigation:

| Nav label | Route | Notes |
|---|---|---|
| Queue | `/` | |
| Case | `/case/:id` | In the nav only once a case has been opened |
| Radar | `/radar` | |
| Metrics | `/metrics` | |
| Report | `/report/:id` | The FIU report (OPO) draft. Old `/opo/:id` links redirect here. |
| Limits | `/limits` | Formerly "Honesty"; `/honesty` redirects here |

The Audit screen has been removed.

## Design foundation

These rules are hard requirements:

- **Theme:** light only; there is no dark mode.
- **Surfaces:** the page is `#F6F5F2` and surfaces are white.
- **No borders anywhere:** `index.css` zeroes every border. Elements are separated by layered soft shadows (`shadow-rest`, `shadow-raise` on hover/active, `shadow-inset` for inputs, `shadow-focus` for the focus ring) and by spacing on an 8px grid.
- **Fonts:** Bricolage Grotesque (variable, self-hosted) for text. JetBrains Mono only for ids and hashes. Numbers use tabular figures.
- **Colour means something:** ink text, grey secondary (`muted`, `faint`), one deep ink-blue `accent` for primary actions and selection, and `amber` for warnings, used rarely. There are no icons, no emoji, no gradients and no coloured chips. Legacy colour names (navy, teal, good, bad, violet) map onto this palette.
- **Layout:** a text-only left rail, a slim top bar holding only the demo identity (name and role), and content capped at `max-w-content` (1240px).
- **Strings:** all UI text is in `src/i18n.tsx`, English only. `useI18n()` returns `t`, `num`, `pct` and `fmtDate`.

## Primitives (`src/components/ui.tsx`)

- **`Page` / `PageTitle`:** the page wrapper with vertical rhythm; a title with an optional one-line description and actions on the right.
- **`Section`:** a heading, an optional one-line `explain` saying what the block is, and optional actions.
- **`Card`:** a white surface with a resting shadow and an optional `title`/`sub`/`right` header. `interactive` lifts it on hover.
- **`Button`:** `variant` is `primary` (accent), `secondary` (shadow) or `quiet` (text only).
- **`Tag`:** a neutral label that shows emphasis by font weight (`default` / `strong` / `muted`). `warn` gives amber text, for rare cases only.
- **`Stat`:** a big tabular number, a one-line label, and an optional hint.
- **`Table`:** takes `columns` and `rows`. It has a sticky header, a hover tint on rows, and keyboard support (Tab into a row, ↑/↓ to move, Enter to open). Sorting is set through `sort` and `onSort`.
- **`PriorityBar`:** an ink number with a thin ink bar. The bar turns amber only at or above `threshold` (default 90). `Bar` is the plain version.
- **`EmptyState` / `Loading` / `ErrorBox`:** the calm empty, loading and error states. `ViolationList` shows server findings and never hides them.
- **Legacy wrappers:** `Chip`, `PageHeader`, `TriageChip`, `RuleChip` and the others only keep old screens compiling, rendered in the neutral look. New code should not use them.

## Data-viz rules for new charts

- **One idea per chart.** If there are two measures on different scales, draw two charts. Never use a second y-axis.
- **Label lines and bars directly** instead of using a legend box. Keep any number of series small.
- **No gridline clutter:** at most faint horizontal guides and no chart border.
- **Colour:** use the ink palette (`--c-out`, `--c-remit`, `--muted`) plus the single `accent` for the series that matters. Use amber only for a real threshold.
- **Numbers and units:** use tabular numbers and spell out units on the axes ("CZK", "exported tokens per world", "%").
- **Text colour:** text stays in ink or grey and is never painted in the series colour.

## Contract notes

`src/api.ts` is the single fetch layer and `src/types.ts` mirrors the API, which is the authority. Slow LLM calls (the first Report draft, Generate explanation, Ask) run only when a person triggers them, and they show their elapsed time.
