
from sdks.novavision.src.helper.package import PackageHelper
from components.CameraFocus.src.models.CameraFocusModel import (
    CameraFocusModel, PackageConfigs, ConfigExecutor,
    CameraFocusBrenner, CameraFocusBrennerResponse, CameraFocusBrennerOutputs,
    CameraFocusTenengrad, CameraFocusTenengradResponse, CameraFocusTenengradOutputs,
    OutputImage, OutputFocusMeasure, OutputBboxFocusMeasures,
)


def build_brenner_response(context):
    outputImage = OutputImage(value=context.image)
    outputFocusMeasure = OutputFocusMeasure(value=context.focus_measure)
    outputs = CameraFocusBrennerOutputs(
        outputImage=outputImage,
        outputFocusMeasure=outputFocusMeasure,
    )
    brennerResponse = CameraFocusBrennerResponse(outputs=outputs)
    brennerExecutor = CameraFocusBrenner(value=brennerResponse)
    configExecutor = ConfigExecutor(value=brennerExecutor)
    packageConfigs = PackageConfigs(executor=configExecutor)
    package = PackageHelper(packageModel=CameraFocusModel, packageConfigs=packageConfigs)
    packageModel = package.build_model(context)
    return packageModel


def build_tenengrad_response(context):
    outputImage = OutputImage(value=context.image)
    outputFocusMeasure = OutputFocusMeasure(value=context.focus_measure)
    outputBboxFocusMeasures = OutputBboxFocusMeasures(value=context.bbox_focus_measures)
    outputs = CameraFocusTenengradOutputs(
        outputImage=outputImage,
        outputFocusMeasure=outputFocusMeasure,
        outputBboxFocusMeasures=outputBboxFocusMeasures,
    )
    tenengradResponse = CameraFocusTenengradResponse(outputs=outputs)
    tenengradExecutor = CameraFocusTenengrad(value=tenengradResponse)
    configExecutor = ConfigExecutor(value=tenengradExecutor)
    packageConfigs = PackageConfigs(executor=configExecutor)
    package = PackageHelper(packageModel=CameraFocusModel, packageConfigs=packageConfigs)
    packageModel = package.build_model(context)
    return packageModel
