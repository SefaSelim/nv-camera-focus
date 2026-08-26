
from pydantic import Field, validator
from typing import List, Optional, Union, Literal
from sdks.novavision.src.base.model import (
    Package, Image, Detection,
    Inputs, Configs, Outputs, Response, Request,
    Output, Input, Config,
)


class InputDetections(Input):
    name: Literal["inputDetections"] = "inputDetections"
    value: Union[List[Detection], Detection]
    type: str = "object"

    class Config:
        title = "Detections"


class OutputImage(Output):
    name: Literal["outputImage"] = "outputImage"
    value: Union[List[Image], Image]
    type: str = "object"

    @validator("type", pre=True, always=True)
    def set_type_based_on_value(cls, value, values):
        value = values.get('value')
        if isinstance(value, Image):
            return "object"
        elif isinstance(value, list):
            return "list"

    class Config:
        title = "Image"


class OutputFocusMeasure(Output):
    name: Literal["outputFocusMeasure"] = "outputFocusMeasure"
    value: float
    type: Literal["number"] = "number"

    class Config:
        title = "Focus Measure"


class OutputBboxFocusMeasures(Output):
    name: Literal["outputBboxFocusMeasures"] = "outputBboxFocusMeasures"
    value: Union[dict, list]
    type: str = "object"

    class Config:
        title = "Bbox Focus Measures"


class OutputCameraStatus(Output):
    name: Literal["outputCameraStatus"] = "outputCameraStatus"
    value: Union[dict, list]
    type: str = "object"

    class Config:
        title = "Camera Status"


# ---------------------------------------------------------------------------
# Shared option classes
# ---------------------------------------------------------------------------
class OptionDisable(Config):
    name: Literal["False"] = "False"
    value: Literal[False] = False
    type: Literal["bool"] = "bool"
    field: Literal["option"] = "option"

    class Config:
        title = "Disable"


class OptionEnable(Config):
    name: Literal["True"] = "True"
    value: Literal[True] = True
    type: Literal["bool"] = "bool"
    field: Literal["option"] = "option"

    class Config:
        title = "Enable"


# Grid overlay options -- value is the number of divisions passed to the renderer
class GridNone(Config):
    # 1 division = the whole frame = no grid lines. The value must not be 0:
    # dropdown option values of 0 are not allowed by the model specification.
    name: Literal["gridNone"] = "gridNone"
    value: Literal[1] = 1
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "None"


class Grid2x2(Config):
    name: Literal["grid2x2"] = "grid2x2"
    value: Literal[2] = 2
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "2x2"


class Grid3x3(Config):
    name: Literal["grid3x3"] = "grid3x3"
    value: Literal[3] = 3
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "3x3"


class Grid4x4(Config):
    name: Literal["grid4x4"] = "grid4x4"
    value: Literal[4] = 4
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "4x4"


class Grid5x5(Config):
    name: Literal["grid5x5"] = "grid5x5"
    value: Literal[5] = 5
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "5x5"


# ---------------------------------------------------------------------------
# Overlay parameters (used by Tenengrad and Stream modes)
# ---------------------------------------------------------------------------
class UnderExposedThreshold(Config):
    """
        Brightness level, as a percentage of the 0-255 range, below which a
        pixel is treated as under-exposed. Pixels darker than this are flagged
        by the zebra overlay. Raising it flags more dark pixels; lowering it
        flags fewer.
    """
    name: Literal["UnderExposedThreshold"] = "UnderExposedThreshold"
    value: float = Field(ge=0.0, le=100.0, default=3.0)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 100.0]"] = "[0.0, 100.0]"

    class Config:
        title = "Under-Exposed Threshold"
        json_schema_extra = {"shortDescription": "Under-Exposed Threshold (%)"}


class OverExposedThreshold(Config):
    """
        Brightness level, as a percentage of the 0-255 range, above which a
        pixel is treated as over-exposed. Pixels brighter than this are flagged
        by the zebra overlay. Lowering it flags more bright pixels; raising it
        flags fewer.
    """
    name: Literal["OverExposedThreshold"] = "OverExposedThreshold"
    value: float = Field(ge=0.0, le=100.0, default=97.0)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 100.0]"] = "[0.0, 100.0]"

    class Config:
        title = "Over-Exposed Threshold"
        json_schema_extra = {"shortDescription": "Over-Exposed Threshold (%)"}


class ShowZebraWarnings(Config):
    """
        Toggle the diagonal zebra stripes that mark under- and over-exposed
        regions. Enable to see exposure clipping; disable for a clean image.
    """
    name: Literal["ShowZebraWarnings"] = "ShowZebraWarnings"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionEnable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Show Zebra Warnings"
        json_schema_extra = {"shortDescription": "Show Zebra Warnings"}


class ShowFocusPeaking(Config):
    """
        Toggle the green focus-peaking overlay that highlights the sharpest
        regions of the frame. Enable to see what is in focus; disable to hide it.
    """
    name: Literal["ShowFocusPeaking"] = "ShowFocusPeaking"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionEnable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Show Focus Peaking"
        json_schema_extra = {"shortDescription": "Show Focus Peaking"}


class ShowHUD(Config):
    """
        Toggle the heads-up display panel showing the focus score and exposure
        histograms. Enable for on-image diagnostics; disable for a clean image.
    """
    name: Literal["ShowHUD"] = "ShowHUD"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionEnable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Show HUD"
        json_schema_extra = {"shortDescription": "Show HUD"}


class ShowCenterMarker(Config):
    """
        Toggle the center crosshair marker. Enable to aid composition; disable
        to hide it.
    """
    name: Literal["ShowCenterMarker"] = "ShowCenterMarker"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionEnable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Show Center Marker"
        json_schema_extra = {"shortDescription": "Show Center Marker"}


class GridOverlay(Config):
    """
        Composition grid drawn over the image. None draws no lines, 3x3 is
        the rule-of-thirds guide, higher values are denser. Affects only the
        overlay, not the focus measurement.
    """
    name: Literal["GridOverlay"] = "GridOverlay"
    value: Union[GridNone, Grid2x2, Grid3x3, Grid4x4, Grid5x5] = Field(default_factory=Grid3x3)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Grid Overlay"
        json_schema_extra = {"shortDescription": "Grid Overlay"}


# ---------------------------------------------------------------------------
# Control parameters (Stream mode)
# ---------------------------------------------------------------------------
class FocusValue(Config):
    """
        Absolute focus position (0.0-1.0) written to the camera. Only used in
        Manual focus mode; 0.0 and 1.0 are the two ends of the lens travel.
    """
    name: Literal["FocusValue"] = "FocusValue"
    value: float = Field(ge=0.0, le=1.0, default=0.5)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 1.0]"] = "[0.0, 1.0]"

    class Config:
        title = "Focus Value"
        json_schema_extra = {"shortDescription": "Manual focus (0-1)"}


class FocusSearchStep(Config):
    """
        Step size (0.0-1.0) used by the closed-loop autofocus hill-climb. Larger
        steps converge faster but overshoot; smaller steps are more precise.
    """
    name: Literal["FocusSearchStep"] = "FocusSearchStep"
    value: float = Field(ge=0.0, le=1.0, default=0.02)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 1.0]"] = "[0.0, 1.0]"

    class Config:
        title = "Focus Search Step"
        json_schema_extra = {"shortDescription": "Closed-loop step size"}


class ZoomValue(Config):
    """
        Absolute zoom position (0.0-1.0) written to the camera in every focus
        mode. 0.0 is fully wide, 1.0 fully tele.
    """
    name: Literal["ZoomValue"] = "ZoomValue"
    value: float = Field(ge=0.0, le=1.0, default=0.0)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 1.0]"] = "[0.0, 1.0]"

    class Config:
        title = "Zoom Value"
        json_schema_extra = {"shortDescription": "Zoom (0-1)"}


class FocusModeManual(Config):
    focusValue: FocusValue = Field(default_factory=FocusValue)
    name: Literal["manual"] = "manual"
    value: Literal["Manual"] = "Manual"
    type: Literal["string"] = "string"
    field: Literal["option"] = "option"

    class Config:
        title = "Manual"


class FocusModeOnePush(Config):
    name: Literal["onePushAutofocus"] = "onePushAutofocus"
    value: Literal["OnePushAutofocus"] = "OnePushAutofocus"
    type: Literal["string"] = "string"
    field: Literal["option"] = "option"

    class Config:
        title = "One-Push Autofocus"


class FocusModeClosedLoop(Config):
    focusSearchStep: FocusSearchStep = Field(default_factory=FocusSearchStep)
    name: Literal["closedLoop"] = "closedLoop"
    value: Literal["ClosedLoop"] = "ClosedLoop"
    type: Literal["string"] = "string"
    field: Literal["option"] = "option"

    class Config:
        title = "Closed-Loop Autofocus"


class FocusMode(Config):
    """
        How focus is driven in Stream mode. Manual writes the Focus Value you
        enter. One-Push Autofocus fires the camera's own autofocus once.
        Closed-Loop Autofocus continuously hill-climbs the Tenengrad focus
        measure and refocuses by itself when sharpness drops. Manual and
        Closed-Loop disable the camera's own continuous autofocus first so our
        commands hold. Zoom Value applies in all three modes.
    """
    name: Literal["FocusMode"] = "FocusMode"
    value: Union[FocusModeManual, FocusModeOnePush, FocusModeClosedLoop] = Field(
        default_factory=FocusModeManual)
    type: Literal["object"] = "object"
    field: Literal["dependentDropdownlist"] = "dependentDropdownlist"

    class Config:
        title = "Focus Mode"
        json_schema_extra = {"shortDescription": "Focus control mode"}


# ---------------------------------------------------------------------------
# Camera connection (shared, always shown)
# ---------------------------------------------------------------------------
class CameraIp(Config):
    """
        IPv4 address of the camera. The executor talks ONVIF to it to discover
        the video stream and to control focus and zoom.
    """
    name: Literal["CameraIp"] = "CameraIp"
    value: str = ""
    type: Literal["string"] = "string"
    field: Literal["textInput"] = "textInput"

    class Config:
        title = "Camera IP"
        json_schema_extra = {"shortDescription": "Camera IP address"}


class CameraUsername(Config):
    """
        Username for the camera's ONVIF authentication (usually 'admin', or a
        dedicated ONVIF user created on the camera).
    """
    name: Literal["CameraUsername"] = "CameraUsername"
    value: str = "admin"
    type: Literal["string"] = "string"
    field: Literal["textInput"] = "textInput"

    class Config:
        title = "Camera Username"
        json_schema_extra = {"shortDescription": "Camera username"}


class CameraPassword(Config):
    """
        Password for the camera. Entered in the node config; the executor never
        logs it. A plain textInput because the value must be user-editable (the
        hiddenInput field type is not rendered in the form).
    """
    name: Literal["CameraPassword"] = "CameraPassword"
    value: str = ""
    type: Literal["string"] = "string"
    field: Literal["textInput"] = "textInput"

    class Config:
        title = "Camera Password"
        json_schema_extra = {"shortDescription": "Camera password"}


class CameraHttpPort(Config):
    """
        The camera's ONVIF service port. Usually 80; some cameras expose ONVIF
        on a different port (e.g. 8000).
    """
    name: Literal["CameraHttpPort"] = "CameraHttpPort"
    value: int = Field(ge=1, le=65535, default=80)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"

    class Config:
        title = "Camera ONVIF Port"
        json_schema_extra = {"shortDescription": "ONVIF service port"}


class SubtypeMain(Config):
    # Profile numbers are 1-based: dropdown option values of 0 are not allowed
    # by the model specification.
    name: Literal["main"] = "main"
    value: Literal[1] = 1
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "Main Stream"


class SubtypeSub(Config):
    name: Literal["sub"] = "sub"
    value: Literal[2] = 2
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "Sub Stream"


class StreamSubtype(Config):
    """
        Which ONVIF media profile to pull: Main is profile 1 (high resolution),
        Sub is profile 2 (lower resolution, lighter and smoother for live
        preview). Affects only the video, not the focus/zoom control.
    """
    name: Literal["StreamSubtype"] = "StreamSubtype"
    value: Union[SubtypeMain, SubtypeSub] = Field(default_factory=SubtypeMain)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Stream Subtype"
        json_schema_extra = {"shortDescription": "Main / Sub stream"}


# ---------------------------------------------------------------------------
# Mode (dependentDropdownlist): Brenner | Tenengrad | Stream
# ---------------------------------------------------------------------------
class BrennerMode(Config):
    name: Literal["brenner"] = "brenner"
    value: Literal["Brenner"] = "Brenner"
    type: Literal["string"] = "string"
    field: Literal["option"] = "option"

    class Config:
        title = "Brenner"


class TenengradMode(Config):
    underExposedThreshold: UnderExposedThreshold = Field(default_factory=UnderExposedThreshold)
    overExposedThreshold: OverExposedThreshold = Field(default_factory=OverExposedThreshold)
    showZebraWarnings: ShowZebraWarnings = Field(default_factory=ShowZebraWarnings)
    showFocusPeaking: ShowFocusPeaking = Field(default_factory=ShowFocusPeaking)
    showHUD: ShowHUD = Field(default_factory=ShowHUD)
    showCenterMarker: ShowCenterMarker = Field(default_factory=ShowCenterMarker)
    gridOverlay: GridOverlay = Field(default_factory=GridOverlay)
    name: Literal["tenengrad"] = "tenengrad"
    value: Literal["Tenengrad"] = "Tenengrad"
    type: Literal["string"] = "string"
    field: Literal["option"] = "option"

    class Config:
        title = "Tenengrad"


class StreamMode(Config):
    underExposedThreshold: UnderExposedThreshold = Field(default_factory=UnderExposedThreshold)
    overExposedThreshold: OverExposedThreshold = Field(default_factory=OverExposedThreshold)
    showZebraWarnings: ShowZebraWarnings = Field(default_factory=ShowZebraWarnings)
    showFocusPeaking: ShowFocusPeaking = Field(default_factory=ShowFocusPeaking)
    showHUD: ShowHUD = Field(default_factory=ShowHUD)
    showCenterMarker: ShowCenterMarker = Field(default_factory=ShowCenterMarker)
    gridOverlay: GridOverlay = Field(default_factory=GridOverlay)
    zoomValue: ZoomValue = Field(default_factory=ZoomValue)
    focusMode: FocusMode = Field(default_factory=FocusMode)
    name: Literal["stream"] = "stream"
    value: Literal["Stream"] = "Stream"
    type: Literal["string"] = "string"
    field: Literal["option"] = "option"

    class Config:
        title = "Stream (Camera Focus Control)"


class Mode(Config):
    """
        What the executor does with the camera video: Brenner focus map,
        Tenengrad measure with overlays, or Stream (Tenengrad + live camera
        focus/zoom control). The camera video is always pulled from the camera.
    """
    name: Literal["Mode"] = "Mode"
    value: Union[BrennerMode, TenengradMode, StreamMode] = Field(default_factory=BrennerMode)
    type: Literal["object"] = "object"
    field: Literal["dependentDropdownlist"] = "dependentDropdownlist"

    class Config:
        title = "Mode"
        json_schema_extra = {"shortDescription": "Brenner / Tenengrad / Stream"}


# ---------------------------------------------------------------------------
# Executor: CameraFocus (single, camera-connected)
# ---------------------------------------------------------------------------
class CameraFocusInputs(Inputs):
    inputDetections: Optional[InputDetections] = None


class CameraFocusConfigs(Configs):
    cameraIp: CameraIp
    cameraUsername: CameraUsername
    cameraPassword: CameraPassword
    cameraHttpPort: CameraHttpPort
    streamSubtype: StreamSubtype
    mode: Mode


class CameraFocusOutputs(Outputs):
    outputImage: OutputImage
    outputFocusMeasure: OutputFocusMeasure
    outputBboxFocusMeasures: OutputBboxFocusMeasures
    outputCameraStatus: OutputCameraStatus


class CameraFocusRequest(Request):
    inputs: Optional[CameraFocusInputs] = None
    configs: CameraFocusConfigs

    class Config:
        json_schema_extra = {
            "target": "configs"
        }


class CameraFocusResponse(Response):
    outputs: CameraFocusOutputs


class CameraFocus(Config):
    name: Literal["CameraFocus"] = "CameraFocus"
    value: Union[CameraFocusRequest, CameraFocusResponse]
    type: Literal["object"] = "object"
    field: Literal["option"] = "option"

    class Config:
        title = "Camera Focus"
        json_schema_extra = {
            "target": {
                "value": 0
            }
        }


class ConfigExecutor(Config):
    """
        Camera-connected focus task. Connect to an IP camera, then choose the
        Mode (Brenner / Tenengrad / Stream) to measure focus and, in Stream mode,
        control the camera's focus and zoom.
    """
    name: Literal["ConfigExecutor"] = "ConfigExecutor"
    value: Union[CameraFocus]
    type: Literal["executor"] = "executor"
    field: Literal["dependentDropdownlist"] = "dependentDropdownlist"

    class Config:
        title = "Task"
        json_schema_extra = {
            "shortDescription": "Select Task",
            "target": "value"
        }


class PackageConfigs(Configs):
    executor: ConfigExecutor


class PackageModel(Package):
    configs: PackageConfigs
    type: Literal["component"] = "component"
    name: Literal["CameraFocus"] = "CameraFocus"
