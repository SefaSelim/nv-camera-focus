
from sdks.novavision.src.helper.package import PackageHelper
from components.CameraFocus.src.models.PackageModel import (
    PackageModel, PackageConfigs, ConfigExecutor,
    CameraFocus, CameraFocusResponse, CameraFocusOutputs,
    OutputImage, OutputFocusMeasure, OutputBboxFocusMeasures, OutputCameraStatus,
)


def build_response(context):
    outputImage = OutputImage(value=context.image)
    outputFocusMeasure = OutputFocusMeasure(value=context.focus_measure)
    outputBboxFocusMeasures = OutputBboxFocusMeasures(value=context.bbox_focus_measures)
    outputCameraStatus = OutputCameraStatus(value=context.camera_status)
    outputs = CameraFocusOutputs(
        outputImage=outputImage,
        outputFocusMeasure=outputFocusMeasure,
        outputBboxFocusMeasures=outputBboxFocusMeasures,
        outputCameraStatus=outputCameraStatus,
    )
    response = CameraFocusResponse(outputs=outputs)
    executor = CameraFocus(value=response)
    configExecutor = ConfigExecutor(value=executor)
    packageConfigs = PackageConfigs(executor=configExecutor)
    package = PackageHelper(packageModel=PackageModel, packageConfigs=packageConfigs)
    packageModel = package.build_model(context)
    return packageModel
