"""
Local test client for the CameraFocus package (single camera-connected executor).

Runs the CameraFocus executor in one of three modes (Brenner / Tenengrad /
Stream) without the NovaVision platform or Redis. It builds a schema-valid
request payload from PackageModel and executes the real executor code with a
small Redis-free mock SDK layer.

Usage:
    # offline (synthetic frame, mock camera):
    python client.py --mode tenengrad
    # real camera over ONVIF:
    python client.py --camera-ip 10.20.30.139 --camera-password PASS --mode stream \
        --focus-mode Manual --zoom 0.4

If --camera-ip is given the real ONVIF backend is used; otherwise a mock camera
yields a synthetic frame so the modes can be exercised offline. The password is
never printed.
"""

import argparse
import os
import sys
import types

import numpy as np

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

GRID_MAP = {"none": 0, "2x2": 2, "3x3": 3, "4x4": 4, "5x5": 5}


# ---------------------------------------------------------------------------
# Environment: components namespace + Redis-free SDK mocks
# ---------------------------------------------------------------------------
def _register_components_namespace():
    if "components.CameraFocus" in sys.modules:
        return
    components = sys.modules.get("components")
    if components is None:
        components = types.ModuleType("components")
        components.__path__ = []
        sys.modules["components"] = components
    camerafocus = types.ModuleType("components.CameraFocus")
    camerafocus.__path__ = [REPO_ROOT]
    sys.modules["components.CameraFocus"] = camerafocus
    components.CameraFocus = camerafocus


def _make_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _install_sdk_mocks():
    from typing import Any, Optional  # noqa: F401
    from pydantic import BaseModel

    class _Base(BaseModel):
        class Config:
            arbitrary_types_allowed = True
            extra = "allow"

    class Image(_Base):
        value: Any = None

    class BoundingBox(_Base):
        left: float = 0.0
        top: float = 0.0
        width: float = 0.0
        height: float = 0.0

    class Detection(_Base):
        boundingBox: Optional[BoundingBox] = None
        confidence: float = 0.0
        classLabel: str = ""
        classId: int = 0

    for name in ["sdks", "sdks.novavision", "sdks.novavision.src",
                 "sdks.novavision.src.base", "sdks.novavision.src.media",
                 "sdks.novavision.src.helper"]:
        if name not in sys.modules:
            _make_module(name).__path__ = []
    base_model = _make_module("sdks.novavision.src.base.model")
    for cls_name in ["Package", "Inputs", "Configs", "Outputs", "Response",
                     "Request", "Output", "Input", "Config", "Model"]:
        setattr(base_model, cls_name, type(cls_name, (_Base,), {}))
    base_model.Image = Image
    base_model.BoundingBox = BoundingBox
    base_model.Detection = Detection

    media_image = _make_module("sdks.novavision.src.media.image")

    class MediaImage:
        @staticmethod
        def get_frame(img, redis_db=None):
            return img

        @staticmethod
        def set_frame(img, package_uID=None, redis_db=None):
            return img

    media_image.Image = MediaImage

    component_mod = _make_module("sdks.novavision.src.base.component")

    class Component:
        def __init__(self, request, bootstrap):
            self.request = request
            self.bootstrap = bootstrap if isinstance(bootstrap, dict) else {}
            self.redis_db = None
            self.uID = "local"
            self.flow = None

    component_mod.Component = Component

    executor_mod = _make_module("sdks.novavision.src.helper.executor")

    class Executor:
        def __init__(self, *a, **k):
            pass

        def run(self):
            return None

    executor_mod.Executor = Executor

    package_mod = _make_module("sdks.novavision.src.helper.package")

    class PackageHelper:
        def __init__(self, packageModel=None, packageConfigs=None):
            self.packageConfigs = packageConfigs

        def build_model(self, context):
            return self.packageConfigs

    package_mod.PackageHelper = PackageHelper


def setup_environment():
    _register_components_namespace()
    try:
        import sdks.novavision.src.base.model  # noqa: F401
        return "real-sdk"
    except Exception:
        _install_sdk_mocks()
        return "mock-sdk"


# ---------------------------------------------------------------------------
# Mock camera (offline): synthetic frame + fake control
# ---------------------------------------------------------------------------
class MockController:
    def __init__(self, *args, **kwargs):
        import cv2
        rng = np.random.default_rng(0)
        frame = cv2.GaussianBlur(rng.integers(40, 210, (480, 640, 3), dtype=np.uint8), (3, 3), 0)
        frame[:120, :120] = 5
        frame[:120, -120:] = 252
        self._frame = frame
        self._zoom = 0.0
        self._focus = 0.5

    def open_stream(self):
        return True

    def read_frame(self):
        return self._frame

    def release(self):
        pass

    def close(self):
        pass

    def get_status(self):
        return {"focus": self._focus, "zoom": self._zoom, "status": "Mock"}

    def capabilities(self):
        return {"zoom": True, "focus": True, "autofocus": True}

    def set_zoom(self, target):
        self._zoom = float(target)
        return True

    def set_focus(self, target):
        self._focus = float(target)
        return True

    def set_autofocus(self, enabled):
        return True

    def trigger_autofocus(self):
        return True


# ---------------------------------------------------------------------------
# Payload + request
# ---------------------------------------------------------------------------
def _cfg(name, value):
    return {"name": name, "value": value}


def build_payload(args):
    mode_opt = {"name": args.mode, "value": args.mode.capitalize()}
    req = {
        "inputs": {"name": "CameraFocus"},
        "configs": {
            "cameraIp": _cfg("CameraIp", args.camera_ip or ""),
            "cameraUsername": _cfg("CameraUsername", args.camera_user),
            "cameraPassword": _cfg("CameraPassword", args.camera_password or ""),
            "cameraHttpPort": _cfg("CameraHttpPort", args.onvif_port),
            "streamSubtype": _cfg("StreamSubtype", {"name": "sub", "value": 1} if args.subtype == "sub"
                                  else {"name": "main", "value": 0}),
            "mode": _cfg("Mode", mode_opt),
        },
    }
    return {"configs": {"executor": {"name": "ConfigExecutor",
            "value": {"name": "CameraFocus", "value": req}}},
            "type": "component", "name": "CameraFocus"}


class MockRequest:
    def __init__(self, data, params):
        self.data = data
        self._params = params
        self.model = None

    def get_param(self, name):
        return self._params.get(name)


def build_params(args):
    return {
        "inputDetections": None,
        "CameraIp": args.camera_ip or "", "CameraUsername": args.camera_user,
        "CameraPassword": args.camera_password or "", "CameraHttpPort": args.onvif_port,
        "StreamSubtype": 1 if args.subtype == "sub" else 0,
        "Mode": args.mode.capitalize(),
        "UnderExposedThreshold": args.under, "OverExposedThreshold": args.over,
        "ShowZebraWarnings": args.show_zebra, "ShowFocusPeaking": args.show_focus_peaking,
        "ShowHUD": args.show_hud, "ShowCenterMarker": args.show_center_marker,
        "GridOverlay": GRID_MAP[args.grid],
        "FocusMode": args.focus_mode, "FocusValue": args.focus, "ZoomValue": args.zoom,
        "FocusSearchStep": args.focus_step,
    }


def str2bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def parse_args():
    p = argparse.ArgumentParser(description="Local runner for the CameraFocus package.")
    p.add_argument("--mode", choices=["brenner", "tenengrad", "stream"], default="tenengrad")
    p.add_argument("--camera-ip", default=None)
    p.add_argument("--camera-user", default="admin")
    p.add_argument("--camera-password", default=None)
    p.add_argument("--onvif-port", type=int, default=80)
    p.add_argument("--subtype", choices=["main", "sub"], default="sub")
    p.add_argument("--output", default=None)
    # overlays
    p.add_argument("--under", type=float, default=3.0)
    p.add_argument("--over", type=float, default=97.0)
    p.add_argument("--show-zebra", type=str2bool, default=True)
    p.add_argument("--show-focus-peaking", type=str2bool, default=True)
    p.add_argument("--show-hud", type=str2bool, default=True)
    p.add_argument("--show-center-marker", type=str2bool, default=True)
    p.add_argument("--grid", choices=list(GRID_MAP.keys()), default="3x3")
    # control (stream)
    p.add_argument("--focus-mode", choices=["Manual", "OnePushAutofocus", "ClosedLoop"], default="Manual")
    p.add_argument("--focus", type=float, default=0.5)
    p.add_argument("--zoom", type=float, default=0.0)
    p.add_argument("--focus-step", type=float, default=0.02)
    return p.parse_args()


def main():
    mode_env = setup_environment()
    args = parse_args()

    import cv2  # noqa: F401  (imported after env setup)

    use_real = bool(args.camera_ip)
    if not use_real:
        # Offline: placeholder credentials so the executor's credential guard
        # passes; the mock camera ignores them.
        args.camera_ip = "mock"
        args.camera_password = "mock"

    # Validate the payload against the real schema.
    from components.CameraFocus.src.models.PackageModel import PackageModel
    payload = build_payload(args)
    try:
        PackageModel(**payload)
    except Exception as exc:
        print("  ! payload did not validate: {}".format(exc))

    from components.CameraFocus.src.executors import CameraFocus as cf_module
    if not use_real:
        cf_module.CameraController = MockController  # offline: synthetic frame

    request = MockRequest(payload, build_params(args))
    executor = cf_module.CameraFocus(request, {})

    print("CameraFocus client [{} | {}]".format(
        mode_env, "real-camera" if use_real else "mock-camera"))
    print("  mode     : {}".format(args.mode))

    executor.run()

    out_path = args.output or "camerafocus_{}.png".format(args.mode)
    import cv2
    cv2.imwrite(out_path, executor.image.value)
    print("  outputImage        -> {}".format(out_path))
    print("  outputFocusMeasure : {:.4f}".format(executor.focus_measure))
    measures = executor.bbox_focus_measures
    if measures:
        print("  outputBboxFocusMeasures ({}):".format(len(measures)))
        for i, m in enumerate(measures):
            print("    [{}] {}".format(i, "nan" if m != m else "{:.4f}".format(m)))
    print("  outputCameraStatus : {}".format(executor.camera_status))

    if not use_real:
        executor.bootstrap.get("camera") and executor.bootstrap["camera"].close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
