"""
Focus-measure algorithms (pure functions). Executors are thin adapters that
call into here -- no algorithm logic lives in the executor files (report
Section 04, three-layer split).
"""

import numpy as np

from components.CameraFocus.src.classes.InputGate import InputGate


class FocusMeasures:
    @staticmethod
    def brenner(image):
        """
        Brenner gradient focus measure.

        The image is normalized to grayscale via InputGate, then the squared
        forward differences at a 2-pixel stride are taken in both directions,
        clipped to their positive part, combined with an element-wise max and
        squared. Returns the per-pixel focus matrix and its mean (the overall
        focus score).

        Deviations from the reference (report Section 05):
        - the horizontal/vertical difference buffers are allocated as int32
          instead of float64: the differences of int16 pixels are small
          integers, so float64 only wastes memory.
        - a flat image yields an all-zero matrix (max == 0); the downstream
          normalization guards against the resulting divide-by-zero.
        """
        gray = InputGate.to_grayscale_uint8(image).astype(np.int16)
        height, width = gray.shape

        diff_horizontal = np.zeros((height, width), dtype=np.int32)
        diff_vertical = np.zeros((height, width), dtype=np.int32)

        if width > 2:
            diff_horizontal[:, : width - 2] = (
                gray[:, 2:].astype(np.int32) - gray[:, : width - 2].astype(np.int32)
            )
        if height > 2:
            diff_vertical[: height - 2, :] = (
                gray[2:, :].astype(np.int32) - gray[: height - 2, :].astype(np.int32)
            )

        np.clip(diff_horizontal, 0, None, out=diff_horizontal)
        np.clip(diff_vertical, 0, None, out=diff_vertical)

        focus_matrix = np.maximum(diff_horizontal, diff_vertical)
        focus_matrix = focus_matrix * focus_matrix

        measure = float(focus_matrix.mean())
        return focus_matrix, measure
