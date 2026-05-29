"""
High-level Python API for chart misleading detection.

Usage:
    from api import ChartAnalyzer

    analyzer = ChartAnalyzer()                        # loads model once
    results  = analyzer.analyze(["a.png", "b.jpg"])   # list of dicts
"""

from pathlib import Path
from analyzer import (
    load_model,
    collect_images,
    analyze_batch,
    SUPPORTED_EXTENSIONS,
)


class ChartAnalyzer:
    """
    Wrapper around ChartGemma for batch chart misleading detection.

    Parameters
    ----------
    device : str
        "auto" (default), "cuda", or "cpu".
    """

    def __init__(self, device: str = "auto"):
        self._model, self._processor, self._device = load_model(device)

    def analyze(self, inputs: list[str]) -> list[dict]:
        """
        Analyze one or more chart images.

        Parameters
        ----------
        inputs : list[str]
            Paths to image files or directories containing images.

        Returns
        -------
        list[dict]
            One dict per image with keys:
              file, verdict, score, score_normalized,
              detected_issues, explanation, recommendation,
              raw_output, error
        """
        image_paths = collect_images(inputs)
        if not image_paths:
            return []
        return analyze_batch(image_paths, self._model, self._processor, self._device)

    def analyze_single(self, image_path: str) -> dict:
        """Convenience method for a single image."""
        results = self.analyze([image_path])
        return results[0] if results else {}
