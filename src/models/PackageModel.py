
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
    inputs: Optional[CameraFocusBrennerInputs]
    configs: Optional[CameraFocusBrennerConfigs]

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
    inputDetections: Optional[InputDetections]


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
    inputs: Optional[CameraFocusTenengradInputs]
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
# Task selector (two executors -> NO target, the user picks)
# ---------------------------------------------------------------------------
class ConfigExecutor(Config):
    """
        Select which focus-measurement task to run. Brenner is a fast,
        parameter-free sharpness check; Tenengrad is the full-featured measure
        with exposure/focus overlays and optional per-detection scores.
    """
    name: Literal["ConfigExecutor"] = "ConfigExecutor"
    value: Union[CameraFocusBrenner, CameraFocusTenengrad]
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
