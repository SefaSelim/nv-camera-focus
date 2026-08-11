
from pydantic import Field, validator
from typing import List, Optional, Union, Literal
from sdks.novavision.src.base.model import (
    Package, Image, Detection,
    Inputs, Configs, Outputs, Response, Request,
    Output, Input, Config,
)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
class InputImage(Input):
    name: Literal["inputImage"] = "inputImage"
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


class InputDetections(Input):
    name: Literal["inputDetections"] = "inputDetections"
    value: Union[List[Detection], Detection]
    type: str = "object"

    class Config:
        title = "Detections"


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Option classes (leaf nodes) -- reused by the boolean dropdowns
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
    name: Literal["gridNone"] = "gridNone"
    value: Literal[0] = 0
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
# Configuration parameters (Tenengrad)
# ---------------------------------------------------------------------------
class UnderExposedThreshold(Config):
    """
        Brightness level, as a percentage of the 0-255 range, below which a
        pixel is treated as under-exposed (crushed shadow). Pixels darker than
        this are flagged by the zebra overlay. Raising it flags more dark
        pixels as clipped; lowering it flags fewer.
    """
    name: Literal["UnderExposedThreshold"] = "UnderExposedThreshold"
    value: float = Field(ge=0.0, le=100.0, default=3.0)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 100.0]"] = "[0.0, 100.0]"

    class Config:
        title = "Under-Exposed Threshold"
        json_schema_extra = {
            "shortDescription": "Under-Exposed Threshold (%)"
        }


class OverExposedThreshold(Config):
    """
        Brightness level, as a percentage of the 0-255 range, above which a
        pixel is treated as over-exposed (blown highlight). Pixels brighter
        than this are flagged by the zebra overlay. Lowering it flags more
        bright pixels as clipped; raising it flags fewer.
    """
    name: Literal["OverExposedThreshold"] = "OverExposedThreshold"
    value: float = Field(ge=0.0, le=100.0, default=97.0)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 100.0]"] = "[0.0, 100.0]"

    class Config:
        title = "Over-Exposed Threshold"
        json_schema_extra = {
            "shortDescription": "Over-Exposed Threshold (%)"
        }


class ShowZebraWarnings(Config):
    """
        Toggle the diagonal zebra stripes that mark under- and over-exposed
        regions. Enable to see where the image is clipping in shadows or
        highlights; disable for a clean, unmarked image.
    """
    name: Literal["ShowZebraWarnings"] = "ShowZebraWarnings"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionEnable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Show Zebra Warnings"
        json_schema_extra = {
            "shortDescription": "Show Zebra Warnings"
        }


class ShowFocusPeaking(Config):
    """
        Toggle the green focus-peaking overlay that highlights the sharpest
        regions of the frame. Enable to see what is critically in focus;
        disable to hide it.
    """
    name: Literal["ShowFocusPeaking"] = "ShowFocusPeaking"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionEnable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Show Focus Peaking"
        json_schema_extra = {
            "shortDescription": "Show Focus Peaking"
        }


class ShowHUD(Config):
    """
        Toggle the heads-up display panel showing the overall focus score and
        exposure histograms. Enable for on-image diagnostics; disable for a
        clean image.
    """
    name: Literal["ShowHUD"] = "ShowHUD"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionEnable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Show HUD"
        json_schema_extra = {
            "shortDescription": "Show HUD"
        }


class ShowCenterMarker(Config):
    """
        Toggle the center crosshair marker. Enable to aid composition and
        centering; disable to hide it.
    """
    name: Literal["ShowCenterMarker"] = "ShowCenterMarker"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionEnable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Show Center Marker"
        json_schema_extra = {
            "shortDescription": "Show Center Marker"
        }


class GridOverlay(Config):
    """
        Composition grid drawn over the image. Choose the number of divisions:
        None disables the grid, 3x3 gives the rule-of-thirds guide, and higher
        values draw a denser grid. Changing this only affects the overlay, not
        the focus measurement.
    """
    name: Literal["GridOverlay"] = "GridOverlay"
    value: Union[GridNone, Grid2x2, Grid3x3, Grid4x4, Grid5x5] = Field(default_factory=Grid3x3)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Grid Overlay"
        json_schema_extra = {
            "shortDescription": "Grid Overlay"
        }


# ---------------------------------------------------------------------------
# Executor A: CameraFocusBrenner (no parameters)
# ---------------------------------------------------------------------------
class CameraFocusBrennerInputs(Inputs):
    inputImage: InputImage


class CameraFocusBrennerConfigs(Configs):
    pass


class CameraFocusBrennerOutputs(Outputs):
    outputImage: OutputImage
    outputFocusMeasure: OutputFocusMeasure


class CameraFocusBrennerRequest(Request):
    inputs: Optional[CameraFocusBrennerInputs] = None
    configs: Optional[CameraFocusBrennerConfigs] = None

    class Config:
        json_schema_extra = {
            "target": "configs"
        }


class CameraFocusBrennerResponse(Response):
    outputs: CameraFocusBrennerOutputs


class CameraFocusBrenner(Config):
    name: Literal["CameraFocusBrenner"] = "CameraFocusBrenner"
    value: Union[CameraFocusBrennerRequest, CameraFocusBrennerResponse]
    type: Literal["object"] = "object"
    field: Literal["option"] = "option"

    class Config:
        title = "Camera Focus Brenner"
        json_schema_extra = {
            "target": {
                "value": 0
            }
        }


# ---------------------------------------------------------------------------
# Executor B: CameraFocusTenengrad (seven parameters)
# ---------------------------------------------------------------------------
class CameraFocusTenengradInputs(Inputs):
    inputImage: InputImage
    inputDetections: Optional[InputDetections] = None


class CameraFocusTenengradConfigs(Configs):
    underExposedThreshold: UnderExposedThreshold
    overExposedThreshold: OverExposedThreshold
    showZebraWarnings: ShowZebraWarnings
    showFocusPeaking: ShowFocusPeaking
    showHUD: ShowHUD
    showCenterMarker: ShowCenterMarker
    gridOverlay: GridOverlay


class CameraFocusTenengradOutputs(Outputs):
    outputImage: OutputImage
    outputFocusMeasure: OutputFocusMeasure
    outputBboxFocusMeasures: OutputBboxFocusMeasures


class CameraFocusTenengradRequest(Request):
    inputs: Optional[CameraFocusTenengradInputs] = None
    configs: CameraFocusTenengradConfigs

    class Config:
        json_schema_extra = {
            "target": "configs"
        }


class CameraFocusTenengradResponse(Response):
    outputs: CameraFocusTenengradOutputs


class CameraFocusTenengrad(Config):
    name: Literal["CameraFocusTenengrad"] = "CameraFocusTenengrad"
    value: Union[CameraFocusTenengradRequest, CameraFocusTenengradResponse]
    type: Literal["object"] = "object"
    field: Literal["option"] = "option"

    class Config:
        title = "Camera Focus Tenengrad"
        json_schema_extra = {
            "target": {
                "value": 0
            }
        }


# ---------------------------------------------------------------------------
# Executor C: CameraFocusStream (self-contained Dahua camera source + control)
# ---------------------------------------------------------------------------

# --- camera status output ---
class OutputCameraStatus(Output):
    name: Literal["outputCameraStatus"] = "outputCameraStatus"
    value: Union[dict, list]
    type: str = "object"

    class Config:
        title = "Camera Status"


# --- stream subtype options ---
class SubtypeMain(Config):
    name: Literal["main"] = "main"
    value: Literal[0] = 0
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "Main Stream"


class SubtypeSub(Config):
    name: Literal["sub"] = "sub"
    value: Literal[1] = 1
    type: Literal["number"] = "number"
    field: Literal["option"] = "option"

    class Config:
        title = "Sub Stream"


# --- focus-mode options ---
class FocusModeManual(Config):
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
    name: Literal["closedLoop"] = "closedLoop"
    value: Literal["ClosedLoop"] = "ClosedLoop"
    type: Literal["string"] = "string"
    field: Literal["option"] = "option"

    class Config:
        title = "Closed-Loop Autofocus"


# --- camera connection configs ---
class CameraIp(Config):
    """
        IPv4 address of the Dahua camera. The executor connects to this address
        over RTSP (video) and HTTP CGI (focus/zoom control).
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
        Username for the camera's HTTP/RTSP authentication (usually 'admin').
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
        Password for the camera's HTTP/RTSP authentication. Entered in the node
        config. The executor never logs it (only its length in diagnostics).
        Note: this is a plain textInput because it must be user-editable; the
        hiddenInput field type is not shown in the form, so it cannot be used
        for a value the user needs to type.
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
        HTTP port used for the Dahua CGI control API. Default 80.
    """
    name: Literal["CameraHttpPort"] = "CameraHttpPort"
    value: int = Field(ge=1, le=65535, default=80)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"

    class Config:
        title = "Camera HTTP Port"
        json_schema_extra = {"shortDescription": "HTTP/CGI port"}


class CameraRtspPort(Config):
    """
        RTSP port used to pull the camera video stream. Default 554.
    """
    name: Literal["CameraRtspPort"] = "CameraRtspPort"
    value: int = Field(ge=1, le=65535, default=554)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"

    class Config:
        title = "Camera RTSP Port"
        json_schema_extra = {"shortDescription": "RTSP port"}


class CameraChannel(Config):
    """
        Camera channel index for the RTSP URL and the PTZ CGI calls. Default 1.
    """
    name: Literal["CameraChannel"] = "CameraChannel"
    value: int = Field(ge=1, le=64, default=1)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"

    class Config:
        title = "Camera Channel"
        json_schema_extra = {"shortDescription": "Channel index"}


class StreamSubtype(Config):
    """
        Which RTSP stream to pull: Main is higher resolution, Sub is lighter and
        faster. Changing this affects only the pulled frame, not the control.
    """
    name: Literal["StreamSubtype"] = "StreamSubtype"
    value: Union[SubtypeMain, SubtypeSub] = Field(default_factory=SubtypeMain)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Stream Subtype"
        json_schema_extra = {"shortDescription": "Main / Sub stream"}


# --- control configs ---
class FocusMode(Config):
    """
        How the camera focus is driven. Manual writes FocusValue/ZoomValue (or,
        if TriggerAutofocus is enabled, fires a one-push autofocus).
        OnePushAutofocus fires the camera's own autofocus once. ClosedLoop
        continuously hill-climbs the Tenengrad focus measure. For Manual and
        ClosedLoop the camera's continuous autofocus tracking is disabled so our
        commands are not overridden.
    """
    name: Literal["FocusMode"] = "FocusMode"
    value: Union[FocusModeManual, FocusModeOnePush, FocusModeClosedLoop] = Field(
        default_factory=FocusModeManual)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Focus Mode"
        json_schema_extra = {"shortDescription": "Focus control mode"}


class FocusValue(Config):
    """
        Target absolute focus position (0.0-1.0) written to the camera in Manual
        mode. 0.0 is one extreme of the lens travel, 1.0 the other.
    """
    name: Literal["FocusValue"] = "FocusValue"
    value: float = Field(ge=0.0, le=1.0, default=0.5)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 1.0]"] = "[0.0, 1.0]"

    class Config:
        title = "Focus Value"
        json_schema_extra = {"shortDescription": "Manual focus (0-1)"}


class ZoomValue(Config):
    """
        Target absolute zoom position (0.0-1.0) written to the camera in Manual
        mode. 0.0 is fully wide, 1.0 fully tele.
    """
    name: Literal["ZoomValue"] = "ZoomValue"
    value: float = Field(ge=0.0, le=1.0, default=0.0)
    type: Literal["number"] = "number"
    field: Literal["textInput"] = "textInput"
    placeHolder: Literal["[0.0, 1.0]"] = "[0.0, 1.0]"

    class Config:
        title = "Zoom Value"
        json_schema_extra = {"shortDescription": "Manual zoom (0-1)"}


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


class TriggerAutofocus(Config):
    """
        In Manual mode, when Enabled, fire a one-push autofocus on this run
        instead of writing FocusValue/ZoomValue. Ignored in the other modes.
    """
    name: Literal["TriggerAutofocus"] = "TriggerAutofocus"
    value: Union[OptionEnable, OptionDisable] = Field(default_factory=OptionDisable)
    type: Literal["object"] = "object"
    field: Literal["dropdownlist"] = "dropdownlist"

    class Config:
        title = "Trigger Autofocus"
        json_schema_extra = {"shortDescription": "Fire one-push AF (Manual)"}


# --- executor C aggregation ---
class CameraFocusStreamInputs(Inputs):
    inputDetections: Optional[InputDetections] = None


class CameraFocusStreamConfigs(Configs):
    cameraIp: CameraIp
    cameraUsername: CameraUsername
    cameraPassword: CameraPassword
    cameraHttpPort: CameraHttpPort
    cameraRtspPort: CameraRtspPort
    cameraChannel: CameraChannel
    streamSubtype: StreamSubtype
    focusMode: FocusMode
    focusValue: FocusValue
    zoomValue: ZoomValue
    focusSearchStep: FocusSearchStep
    triggerAutofocus: TriggerAutofocus
    underExposedThreshold: UnderExposedThreshold
    overExposedThreshold: OverExposedThreshold
    showZebraWarnings: ShowZebraWarnings
    showFocusPeaking: ShowFocusPeaking
    showHUD: ShowHUD
    showCenterMarker: ShowCenterMarker
    gridOverlay: GridOverlay


class CameraFocusStreamOutputs(Outputs):
    outputImage: OutputImage
    outputFocusMeasure: OutputFocusMeasure
    outputBboxFocusMeasures: OutputBboxFocusMeasures
    outputCameraStatus: OutputCameraStatus


class CameraFocusStreamRequest(Request):
    inputs: Optional[CameraFocusStreamInputs] = None
    configs: CameraFocusStreamConfigs

    class Config:
        json_schema_extra = {
            "target": "configs"
        }


class CameraFocusStreamResponse(Response):
    outputs: CameraFocusStreamOutputs


class CameraFocusStream(Config):
    name: Literal["CameraFocusStream"] = "CameraFocusStream"
    value: Union[CameraFocusStreamRequest, CameraFocusStreamResponse]
    type: Literal["object"] = "object"
    field: Literal["option"] = "option"

    class Config:
        title = "Camera Focus Stream"
        json_schema_extra = {
            "target": {
                "value": 0
            }
        }


# ---------------------------------------------------------------------------
# Task selector (three executors -> NO target, the user picks)
# ---------------------------------------------------------------------------
class ConfigExecutor(Config):
    """
        Select which task to run. Brenner is a fast, parameter-free sharpness
        check on an input image; Tenengrad is the full-featured measure with
        exposure/focus overlays and optional per-detection scores on an input
        image; CameraFocusStream connects directly to a Dahua camera (RTSP +
        CGI), measures focus, and controls the camera's focus/zoom.
    """
    name: Literal["ConfigExecutor"] = "ConfigExecutor"
    value: Union[CameraFocusBrenner, CameraFocusTenengrad, CameraFocusStream]
    type: Literal["executor"] = "executor"
    field: Literal["dependentDropdownlist"] = "dependentDropdownlist"

    class Config:
        title = "Task"
        json_schema_extra = {
            "shortDescription": "Select Task"
        }


class PackageConfigs(Configs):
    executor: ConfigExecutor


class PackageModel(Package):
    configs: PackageConfigs
    type: Literal["component"] = "component"
    name: Literal["CameraFocus"] = "CameraFocus"
