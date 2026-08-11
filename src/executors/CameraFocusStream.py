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

NOTE: a lightweight diagnostic logger is enabled (writes to a log file and
stderr; the camera password is never logged). It is meant for bring-up on the
platform and can be removed once the flow is confirmed.
"""

import json
import os
import sys
import tempfile
import time
import traceback

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


def _debug_log(message):
    """Append a timestamped diagnostic line to a log file and stderr. Never
    raises; never logs the camera password."""
    line = "[{}] CameraFocusStream: {}".format(
        time.strftime("%Y-%m-%d %H:%M:%S"), message)
    try:
        path = os.environ.get("CAMERAFOCUS_LOG") or os.path.join(
            tempfile.gettempdir(), "camerafocus_debug.log")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass
    try:
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
    except Exception:
        pass


class CameraFocusStream(Component):
    def __init__(self, request, bootstrap):
        super().__init__(request, bootstrap)

        # Diagnostic: did unresolved template placeholders reach the executor?
        try:
            raw = json.dumps(self.request.data)
            _debug_log("request contains '{{changeable}}' placeholder: {}".format(
                "{{changeable}}" in raw))
        except Exception:
            pass

        try:
            self.request.model = PackageModel(**(self.request.data))
        except Exception as exc:
            _debug_log("PackageModel build FAILED: {}\n{}".format(exc, traceback.format_exc()))
            raise

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

        _debug_log(
            "params: ip={!r} http={!r} rtsp={!r} ch={!r} sub={!r} mode={!r} "
            "focus={!r} zoom={!r} pass_len={}".format(
                self.camera_ip, self.http_port, self.rtsp_port, self.channel,
                self.subtype, self.focus_mode, self.focus_value, self.zoom_value,
                len(self.camera_pass or "") if isinstance(self.camera_pass, str) else "n/a"))

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
            opened = camera.open_stream()
            _debug_log("camera created; open_stream -> {}".format(opened))
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
                # Fire autofocus once, not every frame.
                if not self.bootstrap.get("manual_af_done"):
                    camera.trigger_autofocus()
                    self.bootstrap["manual_af_done"] = True
            else:
                # Send the absolute focus/zoom ONCE per target. Re-issuing
                # adjustFocus every frame restarts the (slow) lens motor and
                # re-triggers autofocus, so it never settles. Only command when
                # the target changes.
                target = (round(float(self.focus_value), 4), round(float(self.zoom_value), 4))
                if self.bootstrap.get("last_manual_target") != target:
                    camera.set_focus_zoom(self.focus_value, self.zoom_value)
                    self.bootstrap["last_manual_target"] = target
                    self.bootstrap["manual_af_done"] = False
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
        # A source executor has no incoming frame to reuse; construct a full
        # frame descriptor (the SDK Image requires name/type/uID/mimeType/
        # encoding) and publish it to Redis via set_frame (which encodes the
        # ndarray to bytes and stores it).
        frame_obj = FrameImage(
            name="outputImage",
            type="object",
            uID=self.uID,
            mimeType="image/jpg",
            encoding="bytes",
            value=frame,
        )
        self.image = Image.set_frame(img=frame_obj, package_uID=self.uID, redis_db=self.redis_db)

    def run(self):
        try:
            _debug_log("run() called")

            # Guard: without credentials, do NOT touch the camera. Repeated
            # failed logins (e.g. empty password) trigger a Dahua account
            # lockout. Publish a placeholder and report the missing config.
            if not self.camera_ip or not self.camera_pass:
                _debug_log("missing camera credentials (ip set={}, pass set={}); "
                           "skipping camera to avoid lockout".format(
                               bool(self.camera_ip), bool(self.camera_pass)))
                self.camera_status = {"status": "MissingCredentials"}
                self._publish(np.zeros((16, 16, 3), dtype=np.uint8))
                return build_camera_stream_response(context=self)

            camera = self._get_camera()
            frame = camera.read_frame()
            _debug_log("read_frame -> {}".format(None if frame is None else frame.shape))

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

            # Reading lens status is a blocking HTTP call; doing it every frame
            # adds latency and makes the preview lag. Poll it ~once per second
            # and reuse the cached value in between.
            self.bootstrap["frame_count"] = self.bootstrap.get("frame_count", 0) + 1
            if self.bootstrap["frame_count"] % 15 == 1:
                status = camera.get_focus_status()
                self.bootstrap["last_status"] = {k: v for k, v in status.items() if k != "raw"}
            self.camera_status = self.bootstrap.get("last_status", {})

            self._publish(rendered)
            _debug_log("published outputImage type={} focus_measure={:.1f}".format(
                type(self.image).__name__, self.focus_measure))
            return build_camera_stream_response(context=self)
        except Exception as exc:
            _debug_log("run() ERROR: {}\n{}".format(exc, traceback.format_exc()))
            raise


if "__main__" == __name__:
    Executor(sys.argv[1]).run()
