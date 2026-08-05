"""
CameraFocusTenengrad executor.

Full-featured focus measurement using the Tenengrad (Sobel gradient) measure,
with optional exposure/focus/composition overlays and optional per-detection
focus scores. Outputs the (optionally annotated) image, the overall focus
score, and per-bounding-box focus measures.

This file is a thin adapter (report Section 04): it reads parameters, converts
the exposure thresholds, and delegates measurement to FocusMeasures and
rendering to OverlayRenderer. No algorithm logic lives here.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from sdks.novavision.src.media.image import Image
from sdks.novavision.src.base.component import Component
from sdks.novavision.src.helper.executor import Executor
from components.CameraFocus.src.utils.response import build_tenengrad_response
from components.CameraFocus.src.models.PackageModel import PackageModel
from components.CameraFocus.src.classes.FocusMeasures import FocusMeasures
from components.CameraFocus.src.classes import OverlayRenderer


class CameraFocusTenengrad(Component):
    def __init__(self, request, bootstrap):
        super().__init__(request, bootstrap)
        self.request.model = PackageModel(**(self.request.data))

        self.image = self.request.get_param("inputImage")
        self.detections = self.request.get_param("inputDetections")

        under_pct = self.request.get_param("UnderExposedThreshold")
        over_pct = self.request.get_param("OverExposedThreshold")
        # Convert percentage thresholds to the 0-255 range. round(), not int():
        # int() truncates (3% -> 7 instead of 8) -- report defect #4.
        self.under = round(under_pct * 255 / 100)
        self.over = round(over_pct * 255 / 100)

        self.show_zebra = self.request.get_param("ShowZebraWarnings")
        self.show_peaking = self.request.get_param("ShowFocusPeaking")
        self.show_hud = self.request.get_param("ShowHUD")
        self.show_center = self.request.get_param("ShowCenterMarker")
        self.grid_divisions = self.request.get_param("GridOverlay")

        self.focus_measure = 0.0
        self.bbox_focus_measures = []

    @staticmethod
    def bootstrap(config: dict) -> dict:
        return {}

    def run(self):
        img = Image.get_frame(img=self.image, redis_db=self.redis_db)
        original = img.value

        gray, focus_matrix, self.focus_measure, self.bbox_focus_measures = \
            FocusMeasures.tenengrad(original, self.detections)

        options = {
            "show_zebra": self.show_zebra,
            "show_peaking": self.show_peaking,
            "show_center": self.show_center,
            "show_hud": self.show_hud,
            "grid_divisions": self.grid_divisions,
            "under": self.under,
            "over": self.over,
        }

        rendered = OverlayRenderer.render(original, gray, focus_matrix, self.focus_measure, options)

        # Zero-copy: when no visualization layer is enabled, render() returns the
        # very same input array. Skip the Redis wrapping and keep the original
        # input frame as the output.
        if rendered is not original:
            img.value = rendered
            self.image = Image.set_frame(img=img, package_uID=self.uID, redis_db=self.redis_db)

        return build_tenengrad_response(context=self)


if "__main__" == __name__:
    Executor(sys.argv[1]).run()
