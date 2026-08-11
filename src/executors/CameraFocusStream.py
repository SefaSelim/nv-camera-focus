"""
CameraFocusStream executor.

Self-contained Dahua camera flow: connects to the camera by IP, pulls the live
RTSP frame, computes the Tenengrad focus measure (with optional overlays and
optional per-detection scores), controls the camera focus/zoom according to
FocusMode, and reports the lens status read back from the camera.

Outputs: outputImage (the live, optionally annotated camera frame),
outputFocusMeasure, outputBboxFocusMeasures, outputCameraStatus.

Thin adapter: the camera I/O lives in CameraController, the measurement in
FocusMeasures, the rendering in OverlayRenderer, and the closed-loop search in
AutofocusController. Credentials are read from the request and never logged.

The persistent camera connection and the autofocus search state live in the
bootstrap dict, so they survive across frames.
"""

import os
import sys

import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from sdks.novavision.src.media.image import Image
from sdks.novavision.src.base.model import Image as FrameImage
from sdks.novavision.src.base.component import Component
from sdks.novavision.src.helper.executor import Executor
from components.CameraFocus.src.utils.response import build_camera_stream_response
from components.CameraFocus.src.models.PackageModel import PackageModel
from components.CameraFocus.src.classes.FocusMeasures import FocusMeasures
from components.CameraFocus.src.classes.CameraController import CameraController
from components.CameraFocus.src.classes.AutofocusController import AutofocusController
from components.CameraFocus.src.classes import OverlayRenderer


class CameraFocusStream(Component):
    def __init__(self, request, bootstrap):
        super().__init__(request, bootstrap)
        self.request.model = PackageModel(**(self.request.data))

        self.detections = self.request.get_param("inputDetections")

        # camera connection
        self.camera_ip = self.request.get_param("CameraIp")
        self.camera_user = self.request.get_param("CameraUsername")
        self.camera_pass = self.request.get_param("CameraPassword")
        self.http_port = self.request.get_param("CameraHttpPort")
        self.rtsp_port = self.request.get_param("CameraRtspPort")
        self.channel = self.request.get_param("CameraChannel")
        self.subtype = self.request.get_param("StreamSubtype")

        # focus/zoom control
        self.focus_mode = self.request.get_param("FocusMode")
        self.focus_value = self.request.get_param("FocusValue")
        self.zoom_value = self.request.get_param("ZoomValue")
        self.focus_step = self.request.get_param("FocusSearchStep")
        self.trigger_af = self.request.get_param("TriggerAutofocus")

        # overlays (reused Tenengrad params)
        under_pct = self.request.get_param("UnderExposedThreshold")
        over_pct = self.request.get_param("OverExposedThreshold")
        self.under = round(under_pct * 255 / 100)
        self.over = round(over_pct * 255 / 100)
        self.show_zebra = self.request.get_param("ShowZebraWarnings")
        self.show_peaking = self.request.get_param("ShowFocusPeaking")
        self.show_hud = self.request.get_param("ShowHUD")
        self.show_center = self.request.get_param("ShowCenterMarker")
        self.grid_divisions = self.request.get_param("GridOverlay")

        # outputs
        self.image = None
        self.focus_measure = 0.0
        self.bbox_focus_measures = []
        self.camera_status = {}

    @staticmethod
    def bootstrap(config: dict) -> dict:
        # State is initialized lazily in run() and persisted here across frames:
        # the camera connection and the autofocus search state.
        return {}

    def _get_camera(self):
        camera = self.bootstrap.get("camera")
        if camera is None:
            camera = CameraController(
                self.camera_ip, self.camera_user, self.camera_pass,
                http_port=self.http_port, rtsp_port=self.rtsp_port,
                channel=self.channel, subtype=self.subtype,
            )
            camera.open_stream()
            # In manual / closed-loop we drive focus ourselves, so turn off the
            # camera's own continuous autofocus tracking to stop it overriding us.
            if self.focus_mode in ("Manual", "ClosedLoop"):
                camera.set_continuous_autofocus(False)
            self.bootstrap["camera"] = camera
            self.bootstrap.setdefault(
                "af_state", AutofocusController.initial_state(step=self.focus_step))
        return camera

    def _apply_control(self, camera):
        if self.focus_mode == "Manual":
            if self.trigger_af:
                camera.trigger_autofocus()
            else:
                camera.set_focus_zoom(self.focus_value, self.zoom_value)
        elif self.focus_mode == "OnePushAutofocus":
            if not self.bootstrap.get("one_push_done"):
                camera.trigger_autofocus()
                self.bootstrap["one_push_done"] = True
        elif self.focus_mode == "ClosedLoop":
            status = camera.get_focus_status()
            zoom = status.get("zoom")
            zoom = self.zoom_value if zoom is None else zoom
            state = AutofocusController.step(
                camera, self.focus_measure, self.bootstrap.get("af_state"), zoom)
            self.bootstrap["af_state"] = state

    def _publish(self, frame):
        # A source executor has no incoming frame to reuse; construct the frame
        # object (base-model Image value holder) and publish it to Redis.
        frame_obj = FrameImage(value=frame)
        self.image = Image.set_frame(img=frame_obj, package_uID=self.uID, redis_db=self.redis_db)

    def run(self):
        camera = self._get_camera()
        frame = camera.read_frame()

        if frame is None:
            self.camera_status = {"status": "NoFrame"}
            self._publish(np.zeros((16, 16, 3), dtype=np.uint8))
            return build_camera_stream_response(context=self)

        gray, focus_matrix, self.focus_measure, self.bbox_focus_measures = \
            FocusMeasures.tenengrad(frame, self.detections)

        options = {
            "show_zebra": self.show_zebra,
            "show_peaking": self.show_peaking,
            "show_center": self.show_center,
            "show_hud": self.show_hud,
            "grid_divisions": self.grid_divisions,
            "under": self.under,
            "over": self.over,
        }
        rendered = OverlayRenderer.render(frame, gray, focus_matrix, self.focus_measure, options)

        self._apply_control(camera)

        status = camera.get_focus_status()
        self.camera_status = {k: v for k, v in status.items() if k != "raw"}

        self._publish(rendered)
        return build_camera_stream_response(context=self)


if "__main__" == __name__:
    Executor(sys.argv[1]).run()
