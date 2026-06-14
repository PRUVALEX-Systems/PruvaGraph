"""
Community detection -- Stage 4 of the pipeline.

Groups the graph into architectural "communities" (tightly-connected
clusters of modules/classes/functions) and writes the result onto each
node's ``community`` attribute as an integer id.

Primary algorithm: Leiden (via ``leidenalg`` + ``igraph``), as advertised
in pyproject.toml -- fast and high-quality on large graphs.

Fallback (if those packages aren't installed, or the graph is tiny/empty):
NetworkX's greedy modularity communities, then plain connected components.
Either way every node ends up with a non-null ``community`` id, so
``analyze.py`` / ``report.py`` / the MCP ``list_communities`` tool always
have something to show.
"""
from __future__ import annotations

import networkx as nx


def cluster_leiden(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """
    Assign a ``community`` (int) attribute to every node in *G*, in place,
    and return *G* for chaining.
    """
    if G.number_of_nodes() == 0:
        return G

    try:
        return _cluster_leiden_impl(G)
    except Exception:
        return _cluster_fallback(G)


# ---------------------------------------------------------------------------
# Leiden (preferred)
# ---------------------------------------------------------------------------


def _cluster_leiden_impl(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    import igraph as ig
    import leidenalg

    node_list = list(G.nodes())
    index = {node: i for i, node in enumerate(node_list)}
    edge_list = [(index[u], index[v]) for u, v in G.edges()]

    ig_graph = ig.Graph(n=len(node_list), edges=edge_list, directed=True)
    partition = leidenalg.find_partition(ig_graph, leidenalg.ModularityVertexPartition)

    for i, community_id in enumerate(partition.membership):
        G.nodes[node_list[i]]["community"] = int(community_id)

    return G


# ---------------------------------------------------------------------------
# Fallback: greedy modularity -> connected components
# ---------------------------------------------------------------------------


def _cluster_fallback(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    undirected = nx.Graph()
    undirected.add_nodes_from(G.nodes())
    for u, v in G.edges():
        undirected.add_edge(u, v)

    communities: list[set[str]]
    try:
        from networkx.algorithms.community import greedy_modularity_communities
        communities = [set(c) for c in greedy_modularity_communities(undirected)]
    except Exception:
        communities = [set(c) for c in nx.connected_components(undirected)]

    for community_id, members in enumerate(communities):
        for node_id in members:
            G.nodes[node_id]["community"] = community_id

    return G
