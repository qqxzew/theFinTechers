# Grafana panels for the Metrics screen

Grafana OSS 12.4.3 runs in Docker. It is provisioned entirely from files in `infra/grafana/` and reads the live FastAPI backend (`GET /api/metrics`) through the Infinity datasource (`yesoreyeram-infinity-datasource` 4.1.1). Anonymous visitors get Viewer access, and embedding is allowed. The default theme is light.

## Start / stop

```powershell
# one-time: infra/grafana/.env must contain GF_ADMIN_PASSWORD=<random> (gitignored; already generated locally)
docker compose -f infra/grafana/docker-compose.grafana.yml up -d      # http://127.0.0.1:3000
docker compose -f infra/grafana/docker-compose.grafana.yml ps         # wait for "healthy"
docker compose -f infra/grafana/docker-compose.grafana.yml down       # stop (add -v to drop the grafana-data volume)
```

The API must be running on the host at `:8000`. The container reaches it at `http://host.docker.internal:8000`. Override that with the `STAJ_API_URL` environment variable.

Checks:

```powershell
curl http://127.0.0.1:3000/api/health                                       # {"database":"ok"}
curl -u admin:<pw> http://127.0.0.1:3000/api/datasources/uid/staj-api/health # Health check successful
```

Admin login: user `admin`, password in `infra/grafana/.env`. Anonymous users are Viewers only.

## Files

| File | Purpose |
|---|---|
| `infra/grafana/docker-compose.grafana.yml` | container, port 127.0.0.1:3000, plugin install, `host.docker.internal` mapping |
| `infra/grafana/grafana.ini` | anonymous Viewer, `allow_embedding`, `cookie_samesite = lax`, light theme, no telemetry/news/help |
| `infra/grafana/provisioning/datasources/infinity.yml` | datasource `Staj API` (uid `staj-api`) |
| `infra/grafana/provisioning/dashboards/staj.yml` | file provider for `infra/grafana/dashboards/` |
| `infra/grafana/dashboards/eval.json` | dashboard `Evaluation`, uid `staj-eval` (generated) |
| `infra/grafana/gen_dashboard.py` | generator of `eval.json`; edit this, not the JSON |
| `infra/grafana/screenshots/panel-N.png` | 900x420 renders of each panel |

After you change the dashboard, run `python infra/grafana/gen_dashboard.py` and then `docker restart staj-grafana`. Use the restart because the Windows bind mount does not reliably trigger Grafana's 10-second file poll.

## Embed URL

```
http://127.0.0.1:3000/d-solo/staj-eval/eval?orgId=1&panelId=<N>&theme=light&kiosk&hideLogo=true
```

`hideLogo=true` removes the "Powered by Grafana" badge on solo panels. Suggested iframe size is 900x420 or similar. The panels fill the iframe.

```html
<iframe src="http://127.0.0.1:3000/d-solo/staj-eval/eval?orgId=1&panelId=1&theme=light&kiosk&hideLogo=true"
        width="100%" height="420" frameborder="0"></iframe>
```

## Panels

Panels have no title (the UI frames them). Series names are plain English: **Banks alone** (`isolated`), **With Stáj** (`staj_psi`), **All data pooled (privacy cost)** (`naive_raw_sharing`).

| id | Type | What it shows | Axes | Source in `/api/metrics` |
|---|---|---|---|---|
| 1 | bar chart | "Alerts that were right" (precision), "Mules found" (recall), "Overall score" (F1) for the three modes, mean over held-out test worlds | y 0–100 % (max 106 % internally so a full bar's label is not clipped) | `headline_held_out_mean` |
| 2 | trend | Mules found at priority cut-off 30/40/50/60, three modes, held-out mean | x "Priority cut-off", y "Found (mules, average)" from 0 | `threshold_curve_held_out_mean` |
| 3 | trend (log x) | Privacy cost: accounts exported to the radar vs hidden ring found, With Stáj, for baseline, weak_0.05 … weak_0.40. Series "Test worlds" (held-out seeds) and "Tuning worlds" (dev seeds), averaged over seeds | x "Accounts exported to the radar (log scale)", y "Hidden ring found (share of test worlds)" 0–100 %, on the right | `weak_evidence_experiment.*.<seed>.<variant>.exported_candidates` / `.staj_psi.ghost_recall` |
| 4 | stat | Raw records shared with other parties: With Stáj vs All data pooled, held-out mean | – | `headline_held_out_mean.*.raw_records_exposed` |
| 5 | horizontal bar | Planted mules caught per scheme, With Stáj, demo world. Labels: Same operator, Same operator, small amounts, Hidden ring, Brand-new account, Fixed commission, Fake invoices, each with "k of n (p%)" | 0–100 % (value axis hidden; share is in the label) | `breakdown` keys `scheme:*` |
| 6 | horizontal bar | Honest look-alikes wrongly flagged per persona, With Stáj, demo world. Labels: Migrant sending money home, Students splitting rent, Second-hand seller, Group collection, Fixed-fee middleman, Freelancer, Fundraiser, each with "k of n (p%)" | same as 5 | `breakdown` keys `persona:*` |
| 7 | table | Worst false alarms and missed mules. Columns Client (pseudonym), Bank, Priority, Why. "Why" says False alarm / Missed mule, the look-alike or scheme, and each signal in plain words with its innocent explanation in brackets; wraps | – | `failures.worst_false_positives`, `failures.false_negatives` |

Visual rules: no title row, transparent background, no border, no "Powered by Grafana" (via `hideLogo=true`). Colours: With Stáj ink blue `#1F3A5F`, Banks alone grey `#8A8F98`, All data pooled muted amber `#C9A227` (the only amber series). Lines 1.5 px. Grid lines only on the value axis. Every count axis starts at 0; ratio axes are fixed 0–100 %. The signal and name translations live in `SCHEMES`, `PERSONAS`, `SIGNALS` and `EXPLAINS` in `gen_dashboard.py`.

## Known limits

- All numbers are synthetic, and the panels show whatever the running API returns. Panels 5 to 7 use the API's current demo world, which is a single dev seed (`dataset` / `seed` in `/api/metrics`), not a held-out mean. The UI caption should say "demo world".
- Grafana's log scale snaps to whole decades, so panel 3's x axis always ends at a power of ten. The y axis sits on the right because its gutter stops the last x tick from being clipped at the iframe edge. The trend panel always puts its legend at the bottom.
- Panel 3 only has data if `eval/report.json` contains `weak_evidence_experiment` (it is passed through `_report_extras`). Each point is a mean over seeds, so a mean like 0.14 means "found in 1 of 7 dev seeds", not partial recall.
- The Infinity backend parser returns columns in alphabetical order. Each panel therefore has an `organize` transformation that pins the order. Keep it if you add columns.
- The XY chart panel's manual series mapping failed ("Err") with Infinity frames in 12.4.3. That is why panel 3 uses the trend panel.
- Cookies are `SameSite=Lax` and not Secure (plain HTTP). Embedding works when the UI and Grafana are on the same site, e.g. both `127.0.0.1`. Mixing `localhost:5173` with `127.0.0.1:3000` is cross-site. Anonymous viewing needs no cookie, but avoid the mix anyway.
- Grafana is bound to `127.0.0.1` only. It is not meant to be exposed beyond the local machine.
