"""
PruvaGraph — codebase knowledge graphs with 70.5%-81.5% token savings and up to 100% cache bypass.

Quick start:
    from pruvagraph import build_graph, query

    graph = build_graph(".")
    answer = query(graph, "how does auth connect to the database?")
"""
from __future__ import annotations

from pruvagraph.cache import GraphCache
from pruvagraph.cost import CostReport, CostTracker
from pruvagraph.pipeline import build_graph, build_graph_async
from pruvagraph.query import query, query_async

__all__ = [
    "build_graph",
    "build_graph_async",
    "query",
    "query_async",
    "CostTracker",
    "CostReport",
    "GraphCache",
]

__version__ = "1.9.0"
__author__ = "PRUVALEX"
__license__ = "MIT"
