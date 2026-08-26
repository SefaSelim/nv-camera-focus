"""
CameraFocus executor — single, camera-connected focus task.

Connects to any ONVIF-capable IP camera, pulls the live
RTSP frame, and runs one of three modes selected by the Mode dropdown:
  - Brenner   : Brenner focus map + overall focus measure.
  - Tenengrad : Tenengrad measure with overlays + per-detection measures.
  - Stream    : Tenengrad measure + overlays AND camera focus/zoom control.

Outputs (unified): outputImage, outputFocusMeasure, outputBboxFocusMeasures,
outputCameraStatus (protocol + detected capabilities + lens focus/zoom).

Thin adapter: camera I/O in CameraController/backends, measurement in
FocusMeasures, rendering in Visualization/OverlayRenderer, closed-loop search in
AutofocusController. Credentials are read from the request and never logged.
"""

import os
import sys
import threading

import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from sdks.novavision.src.media.image import Image
from sdks.novavision.src.base.model import Image as FrameImage
from sdks.novavision.src.base.component import Component
from sdks.novavision.src.helper.executor import Executor
from components.CameraFocus.src.utils.response import build_response
from components.CameraFocus.src.models.PackageModel import PackageModel
from components.CameraFocus.src.classes.FocusMeasures import FocusMeasures
from components.CameraFocus.src.classes.Visualization import Visualization
from components.CameraFocus.src.classes import OverlayRenderer
from components.CameraFocus.src.classes.CameraController import CameraController
from components.CameraFocus.src.classes.OnvifBackend import OnvifBackend
from components.CameraFocus.src.classes.AutofocusController import AutofocusController


def _log(message):
    """Minimal, credential-safe error/status log to stderr."""
    try:
        sys.stderr.write("CameraFocus: {}\n".format(message))
        sys.stderr.flush()
    except Exception:
        pass


class CameraFocus(Component):
    def __init__(self, request, bootstrap):
        super().__init__(request, bootstrap)
        self.request.model = PackageModel(**(self.request.data))

        self.detections = self.request.get_param("inputDetections")

        # camera connection (ONVIF)
        self.camera_ip = self._param("CameraIp", "")
        self.camera_user = self._param("CameraUsername", "admin")
        self.camera_pass = self._param("CameraPassword", "")
        self.onvif_port = self._param("CameraHttpPort", 80)
        self.subtype = self._param("StreamSubtype", 0)

        # mode + mode sub-params (present only for the selected mode)
        self.mode = self._param("Mode", "Brenner")

        under_pct = self._param("UnderExposedThreshold", 3.0)
        over_pct = self._param("OverExposedThreshold", 97.0)
        self.under = round(under_pct * 255 / 100)
        self.over = round(over_pct * 255 / 100)
        self.show_zebra = self._param("ShowZebraWarnings", True)
        self.show_peaking = self._param("ShowFocusPeaking", True)
        self.show_hud = self._param("ShowHUD", True)
        self.show_center = self._param("ShowCenterMarker", True)
        self.grid_divisions = self._param("GridOverlay", 3)

        # control (Stream mode)
        self.focus_mode = self._param("FocusMode", "Manual")
        self.focus_value = self._param("FocusValue", 0.5)
        self.zoom_value = self._param("ZoomValue", 0.0)
        self.focus_step = self._param("FocusSearchStep", 0.02)

        # outputs
        self.image = None
        self.focus_measure = 0.0
        self.bbox_focus_measures = []
        self.camera_status = {}

    def _param(self, name, default):
        value = self.request.get_param(name)
        return default if value is None else value

    @staticmethod
    def bootstrap(config: dict) -> dict:
        # The persistent camera connection and autofocus state are created lazily
        # in run() and kept here across frames.
        return {}

    def _make_backend(self):
        return OnvifBackend(self.camera_ip, self.camera_user, self.camera_pass,
                            port=self.onvif_port, subtype=self.subtype)

    def _get_camera(self):
        camera = self.bootstrap.get("camera")
        if camera is None:
            camera = CameraController(backend=self._make_backend())
            opened = camera.open_stream()
            _log("connected over ONVIF; stream opened={}".format(opened))
            if self.mode == "Stream" and self.focus_mode in ("Manual", "ClosedLoop"):
                camera.set_autofocus(False)
            self.bootstrap["camera"] = camera
            self.bootstrap.setdefault(
                "af_state", AutofocusController.initial_state(step=self.focus_step))
        return camera

    def _overlay_options(self):
        return {
            "show_zebra": self.show_zebra,
            "show_peaking": self.show_peaking,
            "show_center": self.show_center,
            "show_hud": self.show_hud,
            "grid_divisions": self.grid_divisions,
            "under": self.under,
            "over": self.over,
        }

    def _apply_control(self, camera, score):
        caps = camera.capabilities() or {}
        if self.focus_mode == "Manual":
            # Move each axis only when its target changes. Zoom goes FIRST: on a
            # varifocal lens a zoom move shifts focus, so focus is applied after
            # the framing is set (and re-applied whenever zoom moved). Focus uses
            # ONVIF relative moves, which do not disturb zoom.
            focus_t = round(float(self.focus_value), 3)
            zoom_t = round(float(self.zoom_value), 3)
            zoom_changed = self.bootstrap.get("last_zoom") != zoom_t
            focus_changed = self.bootstrap.get("last_focus") != focus_t
            if caps.get("zoom") and zoom_changed:
                camera.set_zoom(self.zoom_value)
                self.bootstrap["last_zoom"] = zoom_t
            if caps.get("focus") and (focus_changed or zoom_changed):
                camera.set_focus(self.focus_value)
                self.bootstrap["last_focus"] = focus_t
        elif self.focus_mode == "OnePushAutofocus":
            # Zoom applies in every focus mode; set it before focusing so the
            # camera autofocuses at the framing the user asked for.
            zoom_t = round(float(self.zoom_value), 3)
            if caps.get("zoom") and self.bootstrap.get("last_zoom") != zoom_t:
                camera.set_zoom(self.zoom_value)
                self.bootstrap["last_zoom"] = zoom_t
                self.bootstrap["one_push_done"] = False
            if not self.bootstrap.get("one_push_done"):
                camera.trigger_autofocus()
                self.bootstrap["one_push_done"] = True
        elif self.focus_mode == "ClosedLoop":
            # First bring zoom to the requested ZoomValue (exact via AbsoluteMove
            # where supported); once zoom is at the target, hill-climb focus. If a
            # focus move later disturbs zoom, re-establish it before focusing.
            if caps.get("zoom"):
                status = camera.get_status() or {}
                current_zoom = status.get("zoom")
                if current_zoom is None or abs(current_zoom - float(self.zoom_value)) > 0.05:
                    camera.set_zoom(self.zoom_value)
                    return  # let zoom settle; focus on a later worker iteration
            if caps.get("focus"):
                state = AutofocusController.step(
                    camera, score, self.bootstrap.get("af_state"), None)
                self.bootstrap["af_state"] = state

    def _spawn_worker(self, camera):
        """Run camera control + status reads in a background thread so the frame
        loop (run) never blocks on slow control-plane calls. Skips if a worker
        from a previous frame is still running."""
        worker = self.bootstrap.get("worker")
        if worker is not None and worker.is_alive():
            return
        worker = threading.Thread(target=self._camera_worker, args=(camera,), daemon=True)
        self.bootstrap["worker"] = worker
        worker.start()

    def _camera_worker(self, camera):
        try:
            if self.mode == "Stream":
                self._apply_control(camera, self.bootstrap.get("latest_score", 0.0))
            status = camera.get_status() or {}
            self.bootstrap["camera_status_data"] = {
                "protocol": "Onvif",
                "capabilities": camera.capabilities() or {},
                "focus": status.get("focus"),
                "zoom": status.get("zoom"),
                "status": status.get("status"),
            }
        except Exception as exc:
            _log("worker ERROR: {}".format(exc))

    def _publish(self, frame):
        frame_obj = FrameImage(
            name="outputImage", type="object", uID=self.uID,
            mimeType="image/jpg", encoding="bytes", value=frame,
        )
        self.image = Image.set_frame(img=frame_obj, package_uID=self.uID, redis_db=self.redis_db)

    def run(self):
        try:
            if not self.camera_ip or not self.camera_pass:
                _log("missing camera credentials (ip set={}, pass set={})".format(
                    bool(self.camera_ip), bool(self.camera_pass)))
                self.camera_status = {"protocol": "Onvif", "status": "MissingCredentials"}
                self._publish(np.zeros((16, 16, 3), dtype=np.uint8))
                return build_response(context=self)

            camera = self._get_camera()
            frame = camera.read_frame()
            if frame is None:
                self.camera_status = {"protocol": "Onvif", "status": "NoFrame",
                                      "capabilities": camera.capabilities() or {}}
                self._publish(np.zeros((16, 16, 3), dtype=np.uint8))
                return build_response(context=self)

            if self.mode == "Brenner":
                focus_matrix, self.focus_measure = FocusMeasures.brenner(frame)
                rendered = Visualization.render_brenner(focus_matrix, self.focus_measure)
                self.bbox_focus_measures = []
            else:  # Tenengrad or Stream
                gray, focus_matrix, self.focus_measure, self.bbox_focus_measures = \
                    FocusMeasures.tenengrad(frame, self.detections)
                rendered = OverlayRenderer.render(
                    frame, gray, focus_matrix, self.focus_measure, self._overlay_options())

            # Camera control (Stream) and status reads run in a background worker
            # so the frame loop never blocks on slow control-plane calls -- this
            # keeps the preview smooth while focus/zoom adjust asynchronously.
            self.bootstrap["latest_score"] = self.focus_measure
            self._spawn_worker(camera)
            self.camera_status = self.bootstrap.get("camera_status_data") or {"protocol": "Onvif"}

            self._publish(rendered)
            return build_response(context=self)
        except Exception as exc:
            _log("run() ERROR: {}".format(exc))
            raise


if "__main__" == __name__:
    Executor(sys.argv[1]).run()
