"""
Focus-measure algorithms (pure functions). Executors are thin adapters that
call into here -- no algorithm logic lives in the executor files (report
Section 04, three-layer split).
"""

import cv2
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

    @staticmethod
    def _detection_box(detection):
        """Extract (left, top, width, height) from a Detection object or dict,
        or return None if no bounding box is present."""
        bbox = None
        if hasattr(detection, "boundingBox"):
            bbox = detection.boundingBox
        elif isinstance(detection, dict):
            bbox = detection.get("boundingBox")
        if bbox is None:
            return None
        if hasattr(bbox, "left"):
            return bbox.left, bbox.top, bbox.width, bbox.height
        if isinstance(bbox, dict):
            return bbox.get("left"), bbox.get("top"), bbox.get("width"), bbox.get("height")
        return None

    @staticmethod
    def tenengrad(image, detections=None):
        """
        Tenengrad focus measure (sum of squared Sobel gradients).

        The image is normalized to grayscale via InputGate (the reference skips
        this -- defect #3), then gx and gy are computed with cv2.Sobel
        (ksize=3, CV_32F) and combined as gx^2 + gy^2. The overall score is the
        mean of that matrix. If detections are supplied, a mean is also computed
        per bounding box (clipped to image bounds).

        Optimizations preserved (report Section 04):
        - the gx^2 + gy^2 combination is done fully in place via np.square /
          np.add with out=, avoiding intermediate allocations.
        - the square root is intentionally NOT taken: it changes no ordering of
          scores and only costs time.

        Per-region fix (report defect #2): for a degenerate box (x2 <= x1 or
        y2 <= y1 after clipping) the reference appends None. This appends
        float("nan") instead -- list indices stay aligned with the detections
        while the element type stays a consistent float.

        Returns (grayscale, focus_matrix, overall_score, per_box_scores).
        """
        gray = InputGate.to_grayscale_uint8(image)

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)

        focus_matrix = gx
        np.square(focus_matrix, out=focus_matrix)
        np.square(gy, out=gy)
        np.add(focus_matrix, gy, out=focus_matrix)

        overall_score = float(focus_matrix.mean())

        per_box_scores = []
        if detections is not None:
            det_list = detections if isinstance(detections, (list, tuple)) else [detections]
            height, width = focus_matrix.shape
            for detection in det_list:
                box = FocusMeasures._detection_box(detection)
                if box is None or any(v is None for v in box):
                    per_box_scores.append(float("nan"))
                    continue
                left, top, box_w, box_h = box
                x1 = max(0, min(int(round(left)), width))
                y1 = max(0, min(int(round(top)), height))
                x2 = max(0, min(int(round(left + box_w)), width))
                y2 = max(0, min(int(round(top + box_h)), height))
                if x2 <= x1 or y2 <= y1:
                    per_box_scores.append(float("nan"))
                else:
                    per_box_scores.append(float(focus_matrix[y1:y2, x1:x2].mean()))

        return gray, focus_matrix, overall_score, per_box_scores
