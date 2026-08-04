"""
Input normalization gate shared by BOTH focus executors.

Any incoming frame is normalized to a 2D uint8 grayscale array before a focus
measure is computed. The Roboflow v2 (Tenengrad) reference omits this step
(report defect #3), which lets non-uint8 / multi-channel frames reach the Sobel
stage with inconsistent scaling; routing every executor through this gate fixes
that.
"""

import cv2
import numpy as np


class InputGate:
    @staticmethod
    def to_grayscale_uint8(image):
        """
        Normalize an arbitrary image array to a contiguous 2D uint8 grayscale
        image. Handles common channel counts (1/2/3/4) and dtypes
        (uint8/float/uint16/other integer). Raises ValueError on shapes it
        cannot interpret.
        """
        arr = np.ascontiguousarray(image)

        # --- channel handling ---
        if arr.ndim == 2:
            gray = arr
        elif arr.ndim == 3:
            channels = arr.shape[2]
            if channels == 1:
                gray = arr[:, :, 0]
            elif channels == 3:
                gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
            elif channels == 4:
                gray = cv2.cvtColor(arr, cv2.COLOR_BGRA2GRAY)
            elif channels == 2:
                gray = arr.mean(axis=2)
            else:
                raise ValueError(
                    "Unsupported channel count for grayscale conversion: {}".format(channels)
                )
        else:
            raise ValueError(
                "Unsupported image ndim for grayscale conversion: {}".format(arr.ndim)
            )

        # --- dtype handling ---
        dtype = gray.dtype
        if dtype == np.uint8:
            out = gray
        elif np.issubdtype(dtype, np.floating):
            out = np.nan_to_num(gray)
            out = np.clip(out, 0, 255).astype(np.uint8)
        elif dtype == np.uint16:
            out = (gray >> 8).astype(np.uint8)
        elif np.issubdtype(dtype, np.integer):
            info = np.iinfo(dtype)
            out = np.clip(gray.astype(np.float64) / info.max * 255.0, 0, 255).astype(np.uint8)
        else:
            raise ValueError("Unsupported image dtype for grayscale conversion: {}".format(dtype))

        return np.ascontiguousarray(out, dtype=np.uint8)
