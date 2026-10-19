"""Generates infra/grafana/dashboards/eval.json (Stáj Evaluation dashboard).

Usage: python infra/grafana/gen_dashboard.py   then   docker restart staj-grafana

Panels are embedded as bare iframes in the UI, so they carry no title, no border and
plain-English series names. Panel ids 1..7 are part of the embed contract: keep them stable.
"""
import json
import os
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboards", "eval.json")
INK = "#1F3A5F"     # With Stáj (and any single series)
GREY = "#8A8F98"    # banks alone / secondary series
AMBER = "#C9A227"   # all data pooled: the only amber series
DS = {"type": "yesoreyeram-infinity-datasource", "uid": "staj-api"}
LINE = 1.5

ALONE, STAJ, POOLED = "Banks alone", "With Stáj", "All data pooled (privacy cost)"
MODES = [("isolated", ALONE, GREY), ("naive_raw_sharing", POOLED, AMBER), ("staj_psi", STAJ, INK)]

SCHEMES = {"same_hand": "Same operator", "same_hand_stealth": "Same operator, small amounts",
           "ghost_ring": "Hidden ring", "day_zero": "Brand-new account", "fixed_skim": "Fixed commission",
           "invoice_mule": "Fake invoices"}
PERSONAS = {"migrant_remit": "Migrant sending money home", "students_rent": "Students splitting rent",
            "second_hand_seller": "Second-hand seller", "group_collection": "Group collection",
            "middleman_cohost": "Fixed-fee middleman", "freelancer": "Freelancer", "fundraiser": "Fundraiser"}
# Short plain-English meaning of each signal (S) and of each innocent explanation (E), for the table.
SIGNALS = {"R-A": "volume above the stated profile", "R-B": "payment linked to a high-risk country or a PEP",
           "R-C": "money passed straight through", "D1": "fast pass-through pattern",
           "D2": "new account emptied at once", "D3": "volume far above the stated profile",
           "D4": "many new unknown senders", "D5": "money leaves to rarely used recipients",
           "D6": "same operator as other suspects", "D7": "fixed commission skimmed",
           "D8": "amounts just under a limit", "X": "linked to suspects at other banks"}
EXPLAINS = {"E1": "regular money sent home", "E2": "everyday spending", "E3": "own salary",
            "E4": "payers are institutions", "E5": "two-way payments", "E6": "one-off group collection",
            "E7": "fixed-fee middleman", "E8": "freelance income"}


def q(ref, root, columns, url="/api/metrics"):
    return {
        "refId": ref, "datasource": DS, "type": "json", "source": "url", "format": "table",
        "parser": "backend", "url": url, "url_options": {"method": "GET", "data": ""},
        "root_selector": root,
        "columns": [{"selector": s, "text": t, "type": ty} for s, t, ty in columns],
        "filters": [],
    }


def ov(name, *props, regex=False):
    return {"matcher": {"id": "byRegexp" if regex else "byName", "options": name},
            "properties": [{"id": k, "value": v} for k, v in props]}


def color(name, c):
    return ov(name, ("color", {"mode": "fixed", "fixedColor": c}))


def base(pid, typ, grid, targets):
    # No title / description: the UI frames each panel itself; empty title also drops the header row.
    return {"id": pid, "type": typ, "title": "", "description": "", "transparent": True,
            "datasource": DS, "gridPos": grid, "targets": targets}


mode_cols = [(k, n, "number") for k, n, _ in MODES]
mode_colors = [color(n, c) for _, n, c in MODES]
LEGEND = {"showLegend": True, "displayMode": "list", "placement": "bottom", "calcs": []}
NO_LEGEND = {"showLegend": False, "displayMode": "list", "placement": "bottom", "calcs": []}
TOOLTIP = {"mode": "multi", "sort": "none"}
NO_GRID = ("custom.axisGridShow", False)  # category / x axis: no grid lines

panels = []

# 1  Precision / recall / F1, held-out mean (ratio -> fixed 0-100 %)
root1 = ('($h := headline_held_out_mean; $map(["precision","recall","f1"], function($m){ {'
         '"metric": $m = "f1" ? "Overall score" : $m = "precision" ? "Alerts that were right" : "Mules found", '
         '"isolated": $lookup($h.isolated, $m), "naive_raw_sharing": $lookup($h.naive_raw_sharing, $m), '
         '"staj_psi": $lookup($h.staj_psi, $m)} }))')
p = base(1, "barchart", {"x": 0, "y": 0, "w": 12, "h": 10},
         [q("A", root1, [("metric", "Metric", "string")] + mode_cols)])
# max a hair above 100 % so the value label on a full bar is not clipped; ticks still read 0-100 %
p["fieldConfig"] = {"defaults": {"unit": "percentunit", "decimals": 0, "min": 0, "max": 1.06,
                                 "custom": {"axisLabel": "Share (average over test worlds)", "axisPlacement": "left",
                                            "fillOpacity": 100, "lineWidth": 0, "gradientMode": "none",
                                            "axisGridShow": True, "axisBorderShow": False}},
                    "overrides": mode_colors + [ov("Metric", NO_GRID, ("custom.axisLabel", ""))]}
p["options"] = {"orientation": "vertical", "xField": "Metric", "groupWidth": 0.7, "barWidth": 0.85, "barRadius": 0,
                "showValue": "always", "stacking": "none", "legend": LEGEND, "tooltip": TOOLTIP,
                "xTickLabelRotation": 0, "text": {"valueSize": 11}, "fullHighlight": False}
panels.append(p)

# 2  Mules found vs priority cut-off (count -> y from 0)
root2 = ('($t := threshold_curve_held_out_mean; $map($sort($keys($t.staj_psi), function($a, $b){ $number($a) > $number($b) }), function($k){ {'
         '"threshold": $number($k), "isolated": $lookup($t.isolated, $k).tp, '
         '"naive_raw_sharing": $lookup($t.naive_raw_sharing, $k).tp, "staj_psi": $lookup($t.staj_psi, $k).tp} }))')
X2 = "Priority cut-off"
p = base(2, "trend", {"x": 12, "y": 0, "w": 12, "h": 10}, [q("A", root2, [("threshold", X2, "number")] + mode_cols)])
p["fieldConfig"] = {"defaults": {"unit": "none", "decimals": 0, "min": 0,
                                 "custom": {"drawStyle": "line", "lineWidth": LINE, "pointSize": 5, "showPoints": "always",
                                            "lineInterpolation": "linear", "fillOpacity": 0,
                                            "axisLabel": "Found (mules, average)", "axisGridShow": True,
                                            "axisBorderShow": False, "spanNulls": True}},
                    "overrides": mode_colors + [ov(X2, ("custom.axisLabel", X2), ("decimals", 0), ("min", None), NO_GRID)]}
p["options"] = {"xField": X2, "legend": LEGEND, "tooltip": TOOLTIP}
panels.append(p)

# 3  Privacy cost: accounts exported vs hidden ring found (ratio -> 0-100 %)
VARS = '["baseline","weak_0.05","weak_0.10","weak_0.20","weak_0.40"]'


def rows3(split, own, other):
    return ('($s := $lookup($w, "' + split + '"); $seeds := $keys($s); $map(' + VARS + ', function($v){ {'
            '"variant": $v, "split": "' + split + '", '
            '"exported": $average($map($seeds, function($k){ $lookup($lookup($s, $k), $v).exported_candidates })), '
            '"' + own + '": $average($map($seeds, function($k){ $lookup($lookup($s, $k), $v).staj_psi.ghost_recall })), '
            '"' + other + '": null } }))')


# One frame: test rows carry a null tuning value and vice versa, so the trend panel draws two series.
root3 = ('($w := weak_evidence_experiment; $append(' + rows3("held_out", "heldout", "dev") + ', '
         + rows3("dev", "dev", "heldout") + '))')
X3 = "Accounts exported to the radar (log scale)"
Y3A, Y3B = "Test worlds", "Tuning worlds"
cols3 = [("exported", X3, "number"), ("heldout", Y3A, "number"), ("dev", Y3B, "number"), ("variant", "Variant", "string")]
p = base(3, "trend", {"x": 0, "y": 10, "w": 12, "h": 10}, [q("A", root3, cols3)])
p["fieldConfig"] = {"defaults": {"unit": "percentunit", "decimals": 0, "min": 0, "max": 1,
                                 "custom": {"drawStyle": "line", "lineWidth": LINE, "pointSize": 6, "showPoints": "always",
                                            "lineInterpolation": "linear", "fillOpacity": 0, "spanNulls": True,
                                            "axisLabel": "Hidden ring found (share of test worlds)",
                                            # y axis on the right: its gutter keeps the last log tick ("10 K")
                                            # from being clipped at the iframe edge
                                            "axisPlacement": "right",
                                            "axisGridShow": True, "axisBorderShow": False}},
                    "overrides": [ov(X3, ("unit", "short"), ("decimals", 0), ("min", None), ("max", None),
                                     ("custom.axisLabel", X3), NO_GRID,
                                     ("custom.scaleDistribution", {"type": "log", "log": 10})),
                                  color(Y3A, INK), color(Y3B, GREY)]}
p["options"] = {"xField": X3, "legend": LEGEND, "tooltip": TOOLTIP}
p["transformations"] = [{"id": "sortBy", "options": {"sort": [{"field": X3, "desc": False}]}},
                        {"id": "organize", "options": {"excludeByName": {"Variant": True}}}]
panels.append(p)

# 4  Raw records exposed to other parties
root4 = ('($h := headline_held_out_mean; [{"staj_psi": $h.staj_psi.raw_records_exposed, '
         '"naive_raw_sharing": $h.naive_raw_sharing.raw_records_exposed}])')
p = base(4, "stat", {"x": 12, "y": 10, "w": 12, "h": 5},
         [q("A", root4, [("staj_psi", STAJ, "number"), ("naive_raw_sharing", POOLED, "number")])])
p["fieldConfig"] = {"defaults": {"unit": "locale", "decimals": 0,
                                 "color": {"mode": "fixed", "fixedColor": INK}},
                    "overrides": [ov(STAJ, ("displayName", STAJ + ": raw records shared")),
                                  ov(POOLED, ("displayName", POOLED + ": raw records shared"),
                                     ("color", {"mode": "fixed", "fixedColor": AMBER}))]}
p["options"] = {"reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""}, "orientation": "vertical",
                "textMode": "value_and_name", "colorMode": "value", "graphMode": "none", "justifyMode": "center",
                "wideLayout": True, "showPercentChange": False, "text": {"titleSize": 14, "valueSize": 30}}
panels.append(p)


# 5 / 6  Breakdown per scheme / persona (ratio -> fixed 0-100 %)
def root_bd(prefix, names):
    return ('($b := breakdown; $names := ' + json.dumps(names, ensure_ascii=False) + '; '
            '$map($filter($keys($b), function($k){ $substringBefore($k, ":") = "' + prefix + '" }), '
            'function($k){ ($id := $substringAfter($k, ":"); $nm := $lookup($names, $id); '
            '$f := $lookup($b, $k).flagged_as_mule_case; $n := $lookup($b, $k).n; {'
            '"group": ($nm ? $nm : $id) & "   " & $string($f) & " of " & $string($n) '
            '& " (" & $string($round(100 * $f / $n)) & "%)", '
            '"value": $f / $n}) }))')


def bd_panel(pid, prefix, names, label, grid):
    p = base(pid, "barchart", grid, [q("A", root_bd(prefix, names), [("group", "Group", "string"), ("value", label, "number")])])
    p["fieldConfig"] = {"defaults": {"unit": "percentunit", "decimals": 0, "min": 0, "max": 1,
                                     "color": {"mode": "fixed", "fixedColor": INK},
                                     # value axis hidden: a full-width axis clips its "100%" tick at the
                                     # iframe edge; the share is printed in each category label instead
                                     "custom": {"axisLabel": label, "fillOpacity": 100, "lineWidth": 0,
                                                "axisPlacement": "hidden", "axisBorderShow": False, "axisGridShow": True}},
                        "overrides": [ov("Group", NO_GRID, ("custom.axisLabel", label),("custom.axisPlacement", "left"))]}
    p["options"] = {"orientation": "horizontal", "xField": "Group", "groupWidth": 0.6, "barWidth": 0.9, "showValue": "never",
                    "stacking": "none", "legend": NO_LEGEND, "tooltip": {"mode": "single", "sort": "none"},
                    "text": {"valueSize": 11}, "fullHighlight": False}
    p["transformations"] = [{"id": "sortBy", "options": {"sort": [{"field": label, "desc": True}]}}]
    return p


panels.append(bd_panel(5, "scheme", SCHEMES, "Planted mules caught, with Stáj", {"x": 0, "y": 20, "w": 12, "h": 9}))
panels.append(bd_panel(6, "persona", PERSONAS, "Honest look-alikes wrongly flagged, with Stáj", {"x": 12, "y": 20, "w": 12, "h": 9}))

# 7  Worst false alarms and missed mules
row = ('function($r){ ($bk := $substringBefore($r.reasons[0], "-"); '
       '$why := $map($filter($r.reasons, function($x){ $not($contains($x, " priority ")) }), function($x){ '
       '($body := $substringAfter($x, ": "); $sig := $substringBefore($body, ":"); $s := $lookup($S, $sig); '
       '$ex := $substringBefore($substringAfter($body, " explained by "), ":"); $e := $lookup($E, $ex); '
       '($s ? $s : $sig) & ($contains($body, " explained by ") ? " (but " & ($e ? $e : $ex) & ")" : "")) }); '
       '$grp := $r.persona ? $lookup($P, $r.persona) : $lookup($C, $r.scheme); '
       '{"client_id": $r.client_id, "bank": $bk ? "Bank " & $substring($bk, 1) : "", "priority": $r.priority, '
       '"why": "%s" & ($grp ? " (" & $grp & ")" : "") & ": " & '
       '($count($why) > 0 ? $join($why, "; ") : "no signal strong enough")}) }')
root7 = ('($S := ' + json.dumps(SIGNALS) + '; $E := ' + json.dumps(EXPLAINS) + '; $P := ' + json.dumps(PERSONAS)
         + '; $C := ' + json.dumps(SCHEMES) + '; $f := failures; '
         '$append($map($f.worst_false_positives, ' + row % "False alarm" + '), '
         '$map($f.false_negatives, ' + row % "Missed mule" + ')))')
p = base(7, "table", {"x": 0, "y": 29, "w": 24, "h": 10},
         [q("A", root7, [("client_id", "Client", "string"), ("bank", "Bank", "string"),
                         ("priority", "Priority", "number"), ("why", "Why", "string")])])
p["fieldConfig"] = {"defaults": {"custom": {"align": "left", "cellOptions": {"type": "auto", "wrapText": True},
                                            "wrapText": True, "inspect": False, "filterable": False},
                                 "color": {"mode": "fixed", "fixedColor": INK}},
                    "overrides": [ov("Client", ("custom.width", 90)), ov("Bank", ("custom.width", 80)),
                                  ov("Priority", ("custom.width", 80), ("decimals", 0))]}
p["options"] = {"showHeader": True, "cellHeight": "sm", "footer": {"show": False, "reducer": ["sum"], "fields": ""},
                "sortBy": [{"displayName": "Priority", "desc": True}]}
panels.append(p)

# The backend parser returns columns alphabetically: pin the declared order.
for p in panels:
    order = [c["text"] for c in p["targets"][0]["columns"]]
    p.setdefault("transformations", []).insert(0, {"id": "organize", "options": {
        "indexByName": {n: i for i, n in enumerate(order)}, "excludeByName": {}, "renameByName": {}}})

dash = {
    "uid": "staj-eval", "title": "Evaluation", "tags": ["staj"], "timezone": "utc", "editable": False,
    "graphTooltip": 0, "time": {"from": "now-1h", "to": "now"}, "timepicker": {"hidden": True},
    "refresh": "", "schemaVersion": 41, "version": 1, "liveNow": False, "fiscalYearStartMonth": 0,
    "annotations": {"list": []}, "templating": {"list": []}, "links": [], "panels": panels,
    "description": "Stáj evaluation numbers served by the FastAPI backend (/api/metrics). Synthetic data.",
}
json.dump(dash, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("wrote", OUT, len(panels), "panels")
