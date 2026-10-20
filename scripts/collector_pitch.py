"""Adds a `collector` block to pitch_numbers.json from the FROZEN TEST runs only (eval/out/collector/test*_summary.json). Touches no other key."""
import json

OUT = "eval/out/collector/"
nc = json.load(open(OUT + "test_how_summary.json"))
cu = json.load(open(OUT + "test_how_cum_summary.json"))
pitch = json.load(open("pitch_numbers.json", encoding="utf-8"))


def cell(summ, c, m, k):
    return summ["summary"][c][m][k]


pitch["collector"] = {
    "synthetic": True, "source": "eval/out/collector/test_how*_summary.json (test seeds 4101, 4202, 4303; frozen tags collector-where-frozen, collector-how-frozen)",
    "crimefree_network_only_errors_per_seed": {m: cell(nc, "crimefree", m, "network_only_errors_mean") for m in ("c", "d")},
    "shared_stealth_recall_month_end": {c: {m: cell(nc, c, m, "stealth_recall") for m in "abc"} for c in ("shared_none", "shared_medium", "shared_high")},
    "shared_stealth_recall_queue_persistent": {c: {m: cell(cu, c, m, "stealth_recall") for m in "abc"} for c in ("shared_none", "shared_medium", "shared_high")},
    "rotating_stealth_recall_queue_persistent_d": {c: cell(cu, c, "d", "stealth_recall") for c in ("rotating_none", "rotating_medium", "rotating_high")},
    "rotating_stealth_recall_month_end_d_NONCUMULATIVE": {c: cell(nc, c, "d", "stealth_recall") for c in ("rotating_none", "rotating_medium", "rotating_high")},
    "median_first_flag_day": {c: {m: cell(nc, c, m, "first_flag_day")[0] for m in "abcde"} for c in ("shared_none", "rotating_none", "rotating_medium")},
    "honest_raised_mean": {c: {m: cell(nc, c, m, "honest_raised_mean") for m in "cd"} for c in ("shared_none", "rotating_none")},
    "records_exposed_to_collector": 0,
    "collector_bytes_per_bank_per_month": nc["summary"]["shared_none"]["bytes_collector_per_bank_per_month"],
}
json.dump(pitch, open("pitch_numbers.json", "w", encoding="utf-8"), indent=1)
print("pitch_numbers.json: collector block written")
