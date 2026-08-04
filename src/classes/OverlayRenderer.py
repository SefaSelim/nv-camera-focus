"""
Tenengrad visualization overlays.

Layer order (report Section 05 fix): peaking -> zebra -> center -> grid -> HUD.
Focus peaking is applied BEFORE zebra so the green peaking overlay cannot paint
over the exposure-clipping warning: exposure clipping is unrecoverable, so that
warning must stay visible.

All overlays assume a 3-channel BGR image (the camera frame). Colours below are
in BGR order.
"""

import cv2
import numpy as np

_ZEBRA_SPACING = 8
_ZEBRA_OPACITY = 0.5
_PEAKING_OPACITY = 0.6
_REFERENCE_HEIGHT = 720.0


def _resolution_scale(height, width):
    """Scale factor relative to a 720-px reference, clamped to [0.4, 2.5]."""
    scale = min(height, width) / _REFERENCE_HEIGHT
    return max(0.4, min(scale, 2.5))


def _blend_masked(image, mask, color, opacity):
    """Alpha-blend a flat colour onto the pixels selected by mask (in place).
    Only the masked pixels are touched -- not a full-frame cv2.addWeighted."""
    if not mask.any():
        return image
    color_arr = np.asarray(color, dtype=np.float32)
    region = image[mask].astype(np.float32)
    image[mask] = (region * (1.0 - opacity) + color_arr * opacity).astype(image.dtype)
    return image


def apply_zebra(image, gray, under, over):
    """Diagonal zebra stripes marking under- and over-exposed pixels. Pixels
    darker than `under` are painted blue, brighter than `over` red -- but only
    on the diagonal stripe pattern, blended at 50% opacity."""
    height, width = gray.shape[:2]
    rows, cols = np.ogrid[:height, :width]
    stripes = ((rows + cols) // _ZEBRA_SPACING) % 2 == 0

    under_mask = (gray < under) & stripes
    over_mask = (gray > over) & stripes

    _blend_masked(image, under_mask, (255, 0, 0), _ZEBRA_OPACITY)   # blue, BGR
    _blend_masked(image, over_mask, (0, 0, 255), _ZEBRA_OPACITY)    # red, BGR
    return image


def apply_focus_peaking(image, focus_matrix, percentile=70.0):
    """Highlight the sharpest regions in green.

    Fix (report defect #1): the reference thresholds at a fixed fraction of the
    focus maximum (normalized > 30% of max), so a single specular highlight
    inflates the maximum and the overlay stops marking anything. Threshold at a
    real percentile of the focus matrix instead, so a constant fraction of the
    frame is always marked regardless of outliers."""
    threshold = np.percentile(focus_matrix, percentile)
    mask = focus_matrix > threshold
    _blend_masked(image, mask, (0, 255, 0), _PEAKING_OPACITY)       # green, BGR
    return image


def draw_center_marker(image):
    """White crosshair at the frame centre, sized by resolution."""
    height, width = image.shape[:2]
    scale = _resolution_scale(height, width)
    cx, cy = width // 2, height // 2
    size = int(20 * scale)
    thickness = max(1, int(round(2 * scale)))
    color = (255, 255, 255)
    cv2.line(image, (cx - size, cy), (cx + size, cy), color, thickness, cv2.LINE_AA)
    cv2.line(image, (cx, cy - size), (cx, cy + size), color, thickness, cv2.LINE_AA)
    return image


def draw_grid(image, divisions):
    """Composition grid with `divisions` cells per axis (draws divisions-1 inner
    lines each way). Draws nothing when divisions is 0."""
    if divisions <= 0:
        return image
    height, width = image.shape[:2]
    color = (128, 128, 128)
    thickness = 1
    for i in range(1, divisions):
        x = int(round(width * i / divisions))
        cv2.line(image, (x, 0), (x, height), color, thickness)
        y = int(round(height * i / divisions))
        cv2.line(image, (0, y), (width, y), color, thickness)
    return image


def _draw_text_with_outline(image, text, org, font_scale, color, thickness):
    """Draw text with a thick black outline first, then the colour on top, so it
    stays legible over any background."""
    cv2.putText(image, text, org, cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(image, text, org, cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                color, thickness, cv2.LINE_AA)


def _draw_histograms(image, original, gray, x, y, width, height):
    """Draw the exposure histograms inside the HUD panel.

    Fix (report secondary finding): the three colour channels are normalized
    against a SHARED maximum (the max across all three), so their bar heights
    are directly comparable to one another. The grayscale/luminance histogram is
    normalized independently."""
    bins = 32
    bar_w = width / float(bins)

    color_channels = []
    if original.ndim == 3 and original.shape[2] >= 3:
        color_channels = [
            (original[:, :, 0], (255, 0, 0)),   # B
            (original[:, :, 1], (0, 255, 0)),   # G
            (original[:, :, 2], (0, 0, 255)),   # R
        ]

    color_hists = [
        (np.histogram(ch, bins=bins, range=(0, 255))[0], col)
        for ch, col in color_channels
    ]
    shared_max = max((h.max() for h, _ in color_hists), default=0)
    shared_max = shared_max if shared_max > 0 else 1

    for hist, col in color_hists:
        for i, v in enumerate(hist):
            bar_h = int(v / shared_max * height)
            px = int(x + i * bar_w)
            cv2.line(image, (px, y + height), (px, y + height - bar_h), col, 1)

    # grayscale histogram, normalized on its own maximum
    gray_hist = np.histogram(gray, bins=bins, range=(0, 255))[0]
    gray_max = gray_hist.max() if gray_hist.max() > 0 else 1
    points = []
    for i, v in enumerate(gray_hist):
        bar_h = int(v / gray_max * height)
        px = int(x + i * bar_w)
        points.append((px, y + height - bar_h))
    if len(points) > 1:
        cv2.polylines(image, [np.array(points, np.int32)], False,
                      (200, 200, 200), 1, cv2.LINE_AA)


def draw_hud(image, focus_value, gray, original):
    """Heads-up display panel with the focus score, basic exposure stats, and
    the exposure histograms. The panel is sized to its content via
    cv2.getTextSize, advancing a cursor_y per line, and text is drawn with an
    outline. Everything scales against the 720-px reference."""
    height, width = image.shape[:2]
    scale = _resolution_scale(height, width)
    font_scale = 0.6 * scale
    thickness = max(1, int(round(scale)))
    pad = int(round(10 * scale))
    line_gap = int(round(4 * scale))

    lines = [
        "Tenengrad: {:.1f}".format(focus_value),
        "Mean: {:.1f}".format(float(gray.mean())),
        "Min/Max: {}/{}".format(int(gray.min()), int(gray.max())),
    ]

    sizes = []
    text_w = 0
    line_h = 0
    for line in lines:
        (tw, th), baseline = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        sizes.append((tw, th, baseline))
        text_w = max(text_w, tw)
        line_h = max(line_h, th + baseline)

    hist_w = max(text_w, int(round(160 * scale)))
    hist_h = int(round(60 * scale))

    panel_w = min(hist_w + 2 * pad, width)
    panel_h = min(pad + len(lines) * (line_h + line_gap) + pad + hist_h + pad, height)

    x0, y0 = pad, pad
    x1, y1 = min(x0 + panel_w, width), min(y0 + panel_h, height)

    overlay = image.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.4, image, 0.6, 0, image)

    cursor_y = y0 + pad + line_h
    for line, (tw, th, baseline) in zip(lines, sizes):
        _draw_text_with_outline(image, line, (x0 + pad, cursor_y - baseline),
                                font_scale, (255, 255, 255), thickness)
        cursor_y += line_h + line_gap

    hist_x = x0 + pad
    hist_y = cursor_y
    if hist_y + hist_h <= y1:
        _draw_histograms(image, original, gray, hist_x, hist_y,
                         min(hist_w, x1 - hist_x - pad), hist_h)
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
