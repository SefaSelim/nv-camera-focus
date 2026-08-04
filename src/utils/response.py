
from sdks.novavision.src.helper.package import PackageHelper
from components.CameraFocus.src.models.CameraFocusModel import (
    CameraFocusModel, PackageConfigs, ConfigExecutor,
    CameraFocusBrenner, CameraFocusBrennerResponse, CameraFocusBrennerOutputs,
    OutputImage, OutputFocusMeasure,
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
