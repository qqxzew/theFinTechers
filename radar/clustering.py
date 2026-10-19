"""Connected-component clustering of candidates that share tokens."""

import hashlib

import networkx as nx

from radar.significance import adjusted_minus_log10, token_p


def _node_label(node: tuple) -> str:
    """Render a graph node as a deterministic string."""
    if node[0] == "c":
        return f"c:{node[1]}:{node[2]}"
    return f"t:{node[1]}"


def build_clusters(rows: list[dict], n_tests: int | None = None, min_significance: float | None = None,
                   significance_cap: float = 8.0) -> list[dict]:
    """Cluster rows via connected components of the candidate/token bipartite graph."""
    graph = nx.Graph()
    max_rarity: dict[str, float] = {}
    for row in rows:
        cand = ("c", row["bank_id"], row["cand_ref"])
        token = ("t", row["token_id"])
        graph.add_edge(cand, token)
        prev = max_rarity.get(row["token_id"])
        if prev is None or row["rarity"] > prev:
            max_rarity[row["token_id"]] = row["rarity"]

    token_sig: dict[str, float] = {}
    if n_tests:
        by_tok: dict[str, dict[str, list[dict]]] = {}
        for row in rows:
            by_tok.setdefault(row["token_id"], {}).setdefault(row["bank_id"], []).append(row)
        for tok, banks in by_tok.items():
            if all("deg" in rs[0] and rs[0].get("deg") is not None and rs[0].get("n_eligible") for rs in banks.values()):
                entries = [(len(rs), rs[0]["n_eligible"], rs[0]["deg"], rs[0]["n_cands"]) for rs in banks.values()]
                token_sig[tok] = adjusted_minus_log10(token_p(entries), n_tests)

    clusters: list[dict] = []
    for component in nx.connected_components(graph):
        banks = sorted({node[1] for node in component if node[0] == "c"})
        candidates = sorted((node[1], node[2]) for node in component if node[0] == "c")
        tokens = sorted(node[1] for node in component if node[0] == "t")
        digest_input = "|".join(sorted(_node_label(node) for node in component))
        cluster_id = hashlib.sha256(digest_input.encode()).hexdigest()[:12]
        mean_rarity = sum(max_rarity[t] for t in tokens) / len(tokens)
        score = (
            0.3 * min(1, (len(banks) - 1) / 2)
            + 0.3 * min(1, (len(candidates) - 2) / 8)
            + 0.4 * mean_rarity
        )
        sig = max((token_sig[t] for t in tokens if t in token_sig), default=None)
        spec_rule = len(banks) >= 2 and len(candidates) >= 3
        clusters.append(
            {
                "cluster_id": cluster_id,
                "significance": None if sig is None else round(sig, 3),
                "x_score": None if sig is None else round(min(1.0, sig / significance_cap), 4),
                "banks": banks,
                "candidates": candidates,
                "tokens": tokens,
                "score": max(0.0, min(1.0, score)),
                "disclosed": spec_rule and (min_significance is None or sig is None or sig >= min_significance),
            }
        )
    clusters.sort(key=lambda c: (-c["score"], c["cluster_id"]))
    return clusters
