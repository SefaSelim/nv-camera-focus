"""
Tenengrad visualization overlays.

SKELETON: the individual layer functions currently return the image unchanged;
their bodies are filled in in the next step. The render() orchestrator, the
layer order, and the zero-copy fast path are already implemented so the package
is runnable at this stage.

Layer order (report Section 05 fix): peaking -> zebra -> center -> grid -> HUD.
Focus peaking is applied BEFORE zebra so the green peaking overlay cannot paint
over the exposure-clipping warning, which must stay visible.
"""

import cv2
import numpy as np


def apply_zebra(image, gray, under, over):
    return image


def apply_focus_peaking(image, focus_matrix):
    return image


def draw_center_marker(image):
    return image


def draw_grid(image, divisions):
    return image


def draw_hud(image, focus_value, gray, original):
    return image


def render(image, gray, focus_matrix, focus_value, options):
    """
    Apply the enabled overlay layers in order and return the annotated image.

    options keys: show_zebra, show_peaking, show_center, show_hud (bools),
    grid_divisions (int, 0 = no grid), under, over (0-255 exposure thresholds).

    Zero-copy fast path: if no layer is enabled, the input image is returned as
    the same object WITHOUT copying (report Section 04 optimization).
    """
    divisions = options.get("grid_divisions") or 0
    any_layer = (
        options.get("show_zebra")
        or options.get("show_peaking")
        or options.get("show_center")
        or options.get("show_hud")
        or divisions > 0
    )
    if not any_layer:
        return image

    original = image
    canvas = image.copy()

    if options.get("show_peaking"):
        canvas = apply_focus_peaking(canvas, focus_matrix)
    if options.get("show_zebra"):
        canvas = apply_zebra(canvas, gray, options.get("under"), options.get("over"))
    if options.get("show_center"):
        canvas = draw_center_marker(canvas)
    if divisions > 0:
        canvas = draw_grid(canvas, divisions)
    if options.get("show_hud"):
        canvas = draw_hud(canvas, focus_value, gray, original)

    return canvas
