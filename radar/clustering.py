"""Connected-component clustering of candidates that share tokens."""

import hashlib

import networkx as nx


def _node_label(node: tuple) -> str:
    """Render a graph node as a deterministic string."""
    if node[0] == "c":
        return f"c:{node[1]}:{node[2]}"
    return f"t:{node[1]}"


def build_clusters(rows: list[dict]) -> list[dict]:
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
        clusters.append(
            {
                "cluster_id": cluster_id,
                "banks": banks,
                "candidates": candidates,
                "tokens": tokens,
                "score": max(0.0, min(1.0, score)),
                "disclosed": len(banks) >= 2 and len(candidates) >= 3,
            }
        )
    clusters.sort(key=lambda c: (-c["score"], c["cluster_id"]))
    return clusters
