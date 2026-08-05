"""
Local test client for the CameraFocus package.

Runs either executor (Brenner or Tenengrad) against a single image file, without
the NovaVision platform or Redis. It builds a schema-valid request payload from
PackageModel, then executes the real executor code with a small mock layer
standing in for the SDK's Redis-backed Image I/O.

Usage:
    python client.py --image test.jpg --task Brenner
    python client.py --image test.jpg --task Tenengrad --grid 3x3 --show-hud true

Notes:
- "client app" is my best interpretation of the Trello item: a local runner for
  the package. There is no built-in client pattern in the in-repo template or an
  installed SDK to follow, so this implements the behaviour described in the
  step. Swap it out if the team means a platform-specific client.
- The seven Tenengrad parameters are exposed as CLI flags whose defaults are
  read from the PackageModel schema (falling back to the documented values).
- If the real SDK is importable it is used; otherwise Redis-free mocks are
  installed. The Image.get_frame / Image.set_frame frame I/O is always mocked so
  no Redis is required.
"""

import argparse
import json
import os
import sys
import types

import numpy as np

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Schema-documented fallbacks (used if the model can't be introspected).
_FALLBACK_DEFAULTS = {
    "under": 3.0,
    "over": 97.0,
    "show_zebra": True,
    "show_peaking": True,
    "show_hud": True,
    "show_center": True,
    "grid": "3x3",
}

GRID_MAP = {"none": 0, "2x2": 2, "3x3": 3, "4x4": 4, "5x5": 5}
GRID_INV = {v: k for k, v in GRID_MAP.items()}


# ---------------------------------------------------------------------------
# Environment wiring: make components.CameraFocus resolve to this repo, and
# provide Redis-free SDK mocks when the real SDK is unavailable.
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
    """Install minimal mock SDK modules into sys.modules (no Redis)."""
    from typing import Any, List, Optional, Union  # noqa: F401
    from pydantic import BaseModel

    class _Base(BaseModel):
        class Config:
            arbitrary_types_allowed = True
            extra = "allow"

    class Model(_Base):
        pass

    class Image(_Base):
        # data-model Image: also carries the pixel array in .value for the mock
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

    class Input(_Base):
        pass

    class Output(_Base):
        pass

    class Config(_Base):
        pass

    class Inputs(_Base):
        pass

    class Configs(_Base):
        pass

    class Outputs(_Base):
        pass

    class Request(_Base):
        pass

    class Response(_Base):
        pass

    class Package(_Base):
        pass

    # sdks.novavision.src.base.model
    for name in ["sdks", "sdks.novavision", "sdks.novavision.src",
                 "sdks.novavision.src.base"]:
        if name not in sys.modules:
            m = _make_module(name)
            m.__path__ = []
    base_model = _make_module("sdks.novavision.src.base.model")
    for cls in (Model, Image, BoundingBox, Detection, Input, Output, Config,
                Inputs, Configs, Outputs, Request, Response, Package):
        setattr(base_model, cls.__name__, cls)

    # sdks.novavision.src.media.image -> media Image with Redis-free frame I/O
    media = _make_module("sdks.novavision.src.media")
    media.__path__ = []
    media_image = _make_module("sdks.novavision.src.media.image")

    class MediaImage:
        @staticmethod
        def get_frame(img, redis_db=None):
            return img

        @staticmethod
        def set_frame(img, package_uID=None, redis_db=None):
            return img

    media_image.Image = MediaImage

    # sdks.novavision.src.base.component -> Component base
    component_mod = _make_module("sdks.novavision.src.base.component")

    class Component:
        def __init__(self, request, bootstrap):
            self.request = request
            self.bootstrap = bootstrap if isinstance(bootstrap, dict) else {}
            self.redis_db = None
            self.uID = "local"
            self.flow = None

    component_mod.Component = Component

    # sdks.novavision.src.helper.{executor,package}
    helper = _make_module("sdks.novavision.src.helper")
    helper.__path__ = []
    executor_mod = _make_module("sdks.novavision.src.helper.executor")

    class Executor:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            return None

    executor_mod.Executor = Executor

    package_mod = _make_module("sdks.novavision.src.helper.package")

    class PackageHelper:
        def __init__(self, packageModel=None, packageConfigs=None):
            self.packageModel = packageModel
            self.packageConfigs = packageConfigs

        def build_model(self, context):
            # The client reads outputs off the executor directly; just return the
            # assembled configs so build_response has something to hand back.
            return self.packageConfigs

    package_mod.PackageHelper = PackageHelper


def setup_environment():
    _register_components_namespace()
    try:
        import sdks.novavision.src.base.model  # noqa: F401
        import sdks.novavision.src.media.image  # noqa: F401
        # Real SDK present: still avoid Redis by mocking the frame I/O.
        from sdks.novavision.src.media.image import Image as RealImage
        RealImage.get_frame = staticmethod(lambda img, redis_db=None: img)
        RealImage.set_frame = staticmethod(lambda img, package_uID=None, redis_db=None: img)
        return "real-sdk"
    except Exception:
        _install_sdk_mocks()
        return "mock-sdk"


# ---------------------------------------------------------------------------
# Schema-derived defaults
# ---------------------------------------------------------------------------
def schema_defaults():
    try:
        from components.CameraFocus.src.models.PackageModel import (
            UnderExposedThreshold, OverExposedThreshold, ShowZebraWarnings,
            ShowFocusPeaking, ShowHUD, ShowCenterMarker, GridOverlay,
        )
        return {
            "under": float(UnderExposedThreshold().value),
            "over": float(OverExposedThreshold().value),
            "show_zebra": bool(ShowZebraWarnings().value.value),
            "show_peaking": bool(ShowFocusPeaking().value.value),
            "show_hud": bool(ShowHUD().value.value),
            "show_center": bool(ShowCenterMarker().value.value),
            "grid": GRID_INV.get(int(GridOverlay().value.value), "3x3"),
        }
    except Exception:
        return dict(_FALLBACK_DEFAULTS)


# ---------------------------------------------------------------------------
# Payload construction (shape validated against PackageModel)
# ---------------------------------------------------------------------------
def _bool_option(flag):
    return {"name": "True", "value": True} if flag else {"name": "False", "value": False}


def _grid_option(divisions):
    return {"name": "grid{}".format("None" if divisions == 0 else "{0}x{0}".format(divisions)),
            "value": divisions}


def build_payload(task, opts, detections_payload):
    if task == "Brenner":
        request = {
            "inputs": {"inputImage": {"name": "inputImage", "value": {}}},
            "configs": {},
        }
        executor = {"name": "CameraFocusBrenner", "value": request}
    else:
        inputs = {"inputImage": {"name": "inputImage", "value": {}}}
        if detections_payload is not None:
            inputs["inputDetections"] = {"name": "inputDetections", "value": detections_payload}
        request = {
            "inputs": inputs,
            "configs": {
                "underExposedThreshold": {"name": "UnderExposedThreshold", "value": opts["under"]},
                "overExposedThreshold": {"name": "OverExposedThreshold", "value": opts["over"]},
                "showZebraWarnings": {"name": "ShowZebraWarnings", "value": _bool_option(opts["show_zebra"])},
                "showFocusPeaking": {"name": "ShowFocusPeaking", "value": _bool_option(opts["show_peaking"])},
                "showHUD": {"name": "ShowHUD", "value": _bool_option(opts["show_hud"])},
                "showCenterMarker": {"name": "ShowCenterMarker", "value": _bool_option(opts["show_center"])},
                "gridOverlay": {"name": "GridOverlay", "value": _grid_option(opts["grid_divisions"])},
            },
        }
        executor = {"name": "CameraFocusTenengrad", "value": request}
    return {
        "configs": {"executor": {"name": "ConfigExecutor", "value": executor}},
        "type": "component",
        "name": "CameraFocus",
    }


def validate_payload(payload):
    """Best-effort: confirm the payload is accepted by the real schema."""
    try:
        from components.CameraFocus.src.models.PackageModel import PackageModel
        PackageModel(**payload)
        return True
    except Exception as exc:  # pragma: no cover - diagnostic only
        print("  ! payload did not validate against PackageModel: {}".format(exc))
        return False


# ---------------------------------------------------------------------------
# Mock request
# ---------------------------------------------------------------------------
class MockRequest:
    """Stands in for the platform request. get_param returns the concrete value
    the executor expects (image frame, detections, or a config value)."""

    def __init__(self, data, params):
        self.data = data
        self._params = params
        self.model = None

    def get_param(self, name):
        return self._params.get(name)


# ---------------------------------------------------------------------------
# Detections
# ---------------------------------------------------------------------------
def load_detections(path):
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if isinstance(raw, dict):
        raw = [raw]
    detections = []
    for item in raw:
        bb = item.get("boundingBox", item)
        detections.append({
            "boundingBox": {
                "left": float(bb["left"]),
                "top": float(bb["top"]),
                "width": float(bb["width"]),
                "height": float(bb["height"]),
            },
            "confidence": float(item.get("confidence", 1.0)),
            "classLabel": str(item.get("classLabel", "")),
            "classId": int(item.get("classId", 0)),
        })
    return detections


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def str2bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def parse_args(defaults):
    parser = argparse.ArgumentParser(description="Local runner for the CameraFocus package.")
    parser.add_argument("--image", required=True, help="Path to the input image.")
    parser.add_argument("--task", required=True, choices=["Brenner", "Tenengrad"],
                        help="Which executor to run.")
    parser.add_argument("--output", default=None,
                        help="Output image path (default: <image-stem>_<task>.png).")
    parser.add_argument("--detections", default=None,
                        help="(Tenengrad) JSON file of bounding boxes for per-region scores.")

    # Tenengrad parameters, defaults from the schema
    parser.add_argument("--under", type=float, default=defaults["under"],
                        help="Under-exposed threshold %% [0-100].")
    parser.add_argument("--over", type=float, default=defaults["over"],
                        help="Over-exposed threshold %% [0-100].")
    parser.add_argument("--show-zebra", type=str2bool, default=defaults["show_zebra"],
                        help="Show zebra exposure warnings (true/false).")
    parser.add_argument("--show-focus-peaking", type=str2bool, default=defaults["show_peaking"],
                        help="Show focus peaking (true/false).")
    parser.add_argument("--show-hud", type=str2bool, default=defaults["show_hud"],
                        help="Show HUD panel (true/false).")
    parser.add_argument("--show-center-marker", type=str2bool, default=defaults["show_center"],
                        help="Show center crosshair (true/false).")
    parser.add_argument("--grid", choices=list(GRID_MAP.keys()), default=defaults["grid"],
                        help="Composition grid overlay.")
    return parser.parse_args()


def main():
    mode = setup_environment()
    defaults = schema_defaults()
    args = parse_args(defaults)

    import cv2  # imported after env setup to keep failures local

    image = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if image is None:
        print("ERROR: could not read image: {}".format(args.image))
        return 2

    output_path = args.output or "{}_{}.png".format(
        os.path.splitext(os.path.basename(args.image))[0], args.task)

    # For Tenengrad always carry an inputDetections field (empty list = no boxes).
    # Under the real SDK's Pydantic v1, Optional[InputDetections] defaults to
    # None so it could be omitted; sending an empty list keeps the payload valid
    # under both Pydantic v1 and v2 and is equivalent to "no detections".
    detections_payload = None
    if args.task == "Tenengrad":
        detections_payload = load_detections(args.detections) if args.detections else []

    opts = {
        "under": float(args.under),
        "over": float(args.over),
        "show_zebra": bool(args.show_zebra),
        "show_peaking": bool(args.show_focus_peaking),
        "show_hud": bool(args.show_hud),
        "show_center": bool(args.show_center_marker),
        "grid_divisions": GRID_MAP[args.grid],
    }

    payload = build_payload(args.task, opts, detections_payload)

    print("CameraFocus client [{}]".format(mode))
    print("  task   : {}".format(args.task))
    print("  image  : {}  ({}x{})".format(args.image, image.shape[1], image.shape[0]))
    validate_payload(payload)

    # Build the data-model Image frame carrying the pixel array.
    from sdks.novavision.src.base.model import Image as ModelImage
    frame = ModelImage(value=image)

    params = {"inputImage": frame, "inputDetections": detections_payload}
    if args.task == "Tenengrad":
        params.update({
            "UnderExposedThreshold": opts["under"],
            "OverExposedThreshold": opts["over"],
            "ShowZebraWarnings": opts["show_zebra"],
            "ShowFocusPeaking": opts["show_peaking"],
            "ShowHUD": opts["show_hud"],
            "ShowCenterMarker": opts["show_center"],
            "GridOverlay": opts["grid_divisions"],
        })

    request = MockRequest(data=payload, params=params)

    if args.task == "Brenner":
        from components.CameraFocus.src.executors.CameraFocusBrenner import CameraFocusBrenner
        executor = CameraFocusBrenner(request, {})
    else:
        from components.CameraFocus.src.executors.CameraFocusTenengrad import CameraFocusTenengrad
        executor = CameraFocusTenengrad(request, {})

    executor.run()

    # Handle outputs
    out_image = executor.image.value
    cv2.imwrite(output_path, out_image)
    print("  outputImage        -> {}".format(output_path))
    print("  outputFocusMeasure : {:.4f}".format(executor.focus_measure))
    if args.task == "Tenengrad":
        measures = executor.bbox_focus_measures
        print("  outputBboxFocusMeasures ({} box(es)):".format(len(measures)))
        for i, m in enumerate(measures):
            print("    [{}] {}".format(i, "nan" if m != m else "{:.4f}".format(m)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
