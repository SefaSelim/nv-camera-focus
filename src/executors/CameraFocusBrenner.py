"""
CameraFocusBrenner executor.

Fast, parameter-free sharpness check using the Brenner gradient measure.

IMPORTANT: the output image is a normalized Brenner *focus map* (a sharpness
visualization with the overall score drawn in the top-left corner), NOT the
original input image.

This file is a thin adapter (report Section 04): it only reads parameters and
calls into src/classes/. No algorithm logic lives here.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from sdks.novavision.src.media.image import Image
from sdks.novavision.src.base.component import Component
from sdks.novavision.src.helper.executor import Executor
from components.CameraFocus.src.utils.response import build_brenner_response
from components.CameraFocus.src.models.CameraFocusModel import CameraFocusModel
from components.CameraFocus.src.classes.InputGate import InputGate
from components.CameraFocus.src.classes.FocusMeasures import FocusMeasures
from components.CameraFocus.src.classes.Visualization import Visualization


class CameraFocusBrenner(Component):
    def __init__(self, request, bootstrap):
        super().__init__(request, bootstrap)
        self.request.model = CameraFocusModel(**(self.request.data))
        self.image = self.request.get_param("inputImage")
        self.focus_measure = 0.0

    @staticmethod
    def bootstrap(config: dict) -> dict:
        return {}

    def run(self):
        img = Image.get_frame(img=self.image, redis_db=self.redis_db)
        gray = InputGate.to_grayscale_uint8(img.value)
        focus_matrix, self.focus_measure = FocusMeasures.brenner(gray)
        img.value = Visualization.render_brenner(focus_matrix, self.focus_measure)
        self.image = Image.set_frame(img=img, package_uID=self.uID, redis_db=self.redis_db)
        return build_brenner_response(context=self)


if "__main__" == __name__:
    Executor(sys.argv[1]).run()
