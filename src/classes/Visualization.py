"""
Simple focus-map renderer for the Brenner executor. The Tenengrad executor uses
the richer OverlayRenderer instead.
"""

import cv2
import numpy as np


class Visualization:
    @staticmethod
    def render_brenner(focus_matrix, focus_value):
        """
        Turn the raw Brenner focus matrix into an 8-bit visualization: normalize
        to 0-255, expand to BGR, and draw the overall score in the top-left.

        The label reads "Brenner: <value>". The reference prints "Focus value",
        which contradicts its own documentation (report, secondary finding).
        """
        matrix = focus_matrix.astype(np.float64)
        matrix_max = float(matrix.max())
        if matrix_max > 0:
            normalized = matrix / matrix_max * 255.0
        else:
            # flat image: avoid divide-by-zero, produce a black focus map
            normalized = np.zeros_like(matrix)

        focus_map = normalized.astype(np.uint8)
        canvas = cv2.cvtColor(focus_map, cv2.COLOR_GRAY2BGR)

        label = "Brenner: {:.2f}".format(focus_value)
        cv2.putText(
            canvas, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
            1.0, (0, 255, 0), 2, cv2.LINE_AA,
        )
        return canvas
