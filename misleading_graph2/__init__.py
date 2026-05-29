"""
misleading_graph — Chart misleading detection powered by ChartGemma.

Quick-start:
    from misleading_graph import ChartAnalyzer

    analyzer = ChartAnalyzer()
    results = analyzer.analyze(["chart1.png", "chart2.png"])
    for r in results:
        print(r["file"], r["verdict"], r["score"])
"""

from .api import ChartAnalyzer

__all__ = ["ChartAnalyzer"]
