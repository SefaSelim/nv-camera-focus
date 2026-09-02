"""
Generate the figures used in the CameraFocus report.

Runs without a camera: the overlay/measure figures use the package's real
rendering and measurement code on a synthetic scene, and the autofocus figures
drive the real AutofocusController against a simulated lens.

    python resources/report/make_figures.py

Figures are written to resources/report/figures/.
"""
import os
import sys
import types

import cv2
import numpy as np

PKG = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_c = types.ModuleType("components"); _c.__path__ = []; sys.modules["components"] = _c
_cf = types.ModuleType("components.CameraFocus"); _cf.__path__ = [PKG]
sys.modules["components.CameraFocus"] = _cf; _c.CameraFocus = _cf

from components.CameraFocus.src.classes.FocusMeasures import FocusMeasures
from components.CameraFocus.src.classes.Visualization import Visualization
from components.CameraFocus.src.classes import OverlayRenderer
from components.CameraFocus.src.classes.AutofocusController import AutofocusController

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
FONT = cv2.FONT_HERSHEY_SIMPLEX
BLUE = "#2b6cb0"
RED = "#c53030"


def save(name, img):
    path = os.path.join(OUT, name + ".png")
    cv2.imwrite(path, img)
    print("  ", name + ".png", img.shape)


def savefig(name, fig):
    path = os.path.join(OUT, name + ".png")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print("  ", name + ".png")


def label(img, text):
    out = img.copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    bar = 34
    cv2.rectangle(out, (0, 0), (out.shape[1], bar), (0, 0, 0), -1)
    cv2.putText(out, text, (10, 24), FONT, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def grid(images, cols):
    rows = []
    for i in range(0, len(images), cols):
        row = list(images[i:i + cols])
        h = min(im.shape[0] for im in row)
        row = [cv2.resize(im, (int(im.shape[1] * h / im.shape[0]), h)) for im in row]
        while len(row) < cols:
            row.append(np.zeros_like(row[0]))
        rows.append(np.hstack(row))
    w = min(r.shape[1] for r in rows)
    rows = [cv2.resize(r, (w, int(r.shape[0] * w / r.shape[1]))) for r in rows]
    return np.vstack(rows)


def scene(blur=1, spec=False):
    """A synthetic office-like scene: smooth wall, a few objects with real edges,
    text, plus a crushed-shadow and a blown-highlight corner for the zebra layer.
    Kept low-noise so focus peaking marks edges rather than sensor grain."""
    h, w = 420, 620
    # smooth wall gradient
    grad = np.linspace(150, 205, w, dtype=np.float32)
    img = np.repeat(grad[None, :], h, axis=0)
    img = np.dstack([img * 0.97, img * 0.99, img]).astype(np.uint8)
    img = cv2.GaussianBlur(img, (31, 31), 0)

    # desk band
    cv2.rectangle(img, (0, 330), (w, h), (86, 104, 126), -1)
    cv2.line(img, (0, 330), (w, 330), (60, 74, 92), 3)

    # objects with clean edges
    cv2.rectangle(img, (60, 150), (200, 320), (72, 88, 110), -1)
    cv2.rectangle(img, (60, 150), (200, 320), (35, 45, 60), 2)
    cv2.putText(img, "NOVA", (74, 200), FONT, 0.9, (235, 240, 245), 2, cv2.LINE_AA)
    cv2.putText(img, "FOCUS", (74, 240), FONT, 0.9, (235, 240, 245), 2, cv2.LINE_AA)
    cv2.circle(img, (330, 240), 55, (120, 150, 190), -1)
    cv2.circle(img, (330, 240), 55, (50, 70, 100), 2)
    for i in range(7):                      # a resolution comb: fine detail
        x = 430 + i * 14
        cv2.line(img, (x, 170), (x, 300), (40, 50, 65), 3)
    cv2.putText(img, "1234567890", (420, 325), FONT, 0.5, (30, 35, 45), 1, cv2.LINE_AA)

    # exposure extremes for the zebra layer
    cv2.rectangle(img, (0, 0), (95, 80), (3, 3, 4), -1)
    cv2.rectangle(img, (w - 95, 0), (w, 80), (253, 253, 253), -1)

    if blur > 1:
        k = int(blur) * 2 + 1
        img = cv2.GaussianBlur(img, (k, k), 0)
    if spec:
        cv2.circle(img, (w - 160, 60), 7, (255, 255, 255), -1)
        cv2.circle(img, (w - 160, 60), 11, (255, 255, 255), 2)
    return img


def opts(**kw):
    o = {"show_zebra": False, "show_peaking": False, "show_center": False,
         "show_hud": False, "grid_divisions": 1, "under": 8, "over": 247}
    o.update(kw)
    return o


def fig_modes():
    img = scene()
    gray, fm, score = FocusMeasures.tenengrad(img)[0:3]
    bmat, bscore = FocusMeasures.brenner(img)
    save("fig01_modes", grid([
        label(img, "Kamera goruntusu (giris)"),
        label(Visualization.render_brenner(bmat, bscore),
              "Mode = Brenner  |  odak haritasi, skor %.0f" % bscore),
        label(OverlayRenderer.render(img.copy(), gray, fm, score,
              opts(show_peaking=True, show_hud=True, grid_divisions=3, show_center=True)),
              "Mode = Tenengrad  |  skor %.0f" % score),
        label(OverlayRenderer.render(img.copy(), gray, fm, score,
              opts(show_zebra=True, show_peaking=True, show_hud=True,
                   grid_divisions=3, show_center=True)),
              "Mode = Stream  |  olcum + kamera kontrolu"),
    ], 2))


def fig_overlays():
    img = scene()
    gray, fm, score = FocusMeasures.tenengrad(img)[0:3]
    items = [
        (img, "Katman yok"),
        (OverlayRenderer.render(img.copy(), gray, fm, score, opts(show_peaking=True)),
         "Focus peaking (en keskin %30)"),
        (OverlayRenderer.render(img.copy(), gray, fm, score, opts(show_zebra=True)),
         "Zebra: mavi = az pozlanmis, kirmizi = asiri"),
        (OverlayRenderer.render(img.copy(), gray, fm, score, opts(grid_divisions=3)),
         "Grid 3x3 (kompozisyon)"),
        (OverlayRenderer.render(img.copy(), gray, fm, score, opts(show_center=True)),
         "Merkez isareti"),
        (OverlayRenderer.render(img.copy(), gray, fm, score, opts(show_hud=True)),
         "HUD: skor + histogramlar"),
    ]
    save("fig02_overlays", grid([label(i, t) for i, t in items], 3))


def fig_blur_curve():
    blurs = list(range(1, 13))
    ten, bre = [], []
    for b in blurs:
        img = scene(blur=b)
        ten.append(FocusMeasures.tenengrad(img)[2])
        bre.append(FocusMeasures.brenner(img)[1])
    fig, ax = plt.subplots(figsize=(9, 4.0), dpi=150)
    ax.plot(blurs, np.array(ten) / max(ten), "o-", color=BLUE, label="Tenengrad (normalize)")
    ax.plot(blurs, np.array(bre) / max(bre), "s--", color=RED, label="Brenner (normalize)")
    ax.set_xlabel("Bulaniklik seviyesi (Gauss cekirdegi)")
    ax.set_ylabel("Normalize odak skoru")
    ax.set_title("Kademeli bulaniklik altinda iki olcunun degisimi")
    ax.grid(alpha=.3); ax.legend()
    savefig("fig03_blur_curve", fig)

    save("fig03_blur_samples", grid([
        label(scene(blur=1), "net  (Tenengrad %.0f)" % ten[0]),
        label(scene(blur=5), "orta bulanik  (%.0f)" % ten[4]),
        label(scene(blur=11), "cok bulanik  (%.0f)" % ten[10]),
    ], 3))


def _sharpness(focus, peak=0.62, noise=0.0, rng=None):
    base = 5000.0 / (1.0 + 60.0 * (focus - peak) ** 2)
    if noise and rng is not None:
        base *= rng.uniform(1.0 - noise, 1.0 + noise)
    return base


class SimLens:
    def __init__(self, focus=0.25):
        self.focus = focus
        self.history = []

    def get_status(self):
        return {"focus": self.focus}

    def set_focus(self, target):
        self.focus = max(0.0, min(1.0, float(target)))
        return True


def fig_focus_curve():
    xs = np.linspace(0.05, 0.95, 60)
    ys = [_sharpness(x) for x in xs]
    fig, ax = plt.subplots(figsize=(9, 4.0), dpi=150)
    ax.plot(xs, ys, color=BLUE)
    ax.axvline(0.62, color=RED, ls="--", label="en net odak (0.62)")
    ax.set_xlabel("Odak konumu (0-1)"); ax.set_ylabel("Tenengrad odak skoru")
    ax.set_title("Odak konumuna gore odak skoru - kapali dongunun tirmandigi egri")
    ax.grid(alpha=.3); ax.legend()
    savefig("fig04_focus_curve", fig)


def fig_closed_loop():
    rng = np.random.default_rng(7)
    lens = SimLens(0.25)
    state = AutofocusController.initial_state(step=0.05)
    pos, sc = [], []
    for _ in range(60):
        s = _sharpness(lens.focus, noise=0.10, rng=rng)
        pos.append(lens.focus); sc.append(s)
        state = AutofocusController.step(lens, s, state, None)
        if state.get("converged"):
            pos.append(lens.focus); sc.append(_sharpness(lens.focus, noise=0.10, rng=rng))
            break
    fig, ax1 = plt.subplots(figsize=(9, 4.2), dpi=150)
    ax1.plot(pos, "o-", color=BLUE, label="odak konumu")
    ax1.axhline(0.62, color="#718096", ls=":", label="en net odak")
    ax1.set_xlabel("Kapali dongu adimi"); ax1.set_ylabel("Odak konumu (0-1)", color=BLUE)
    ax2 = ax1.twinx(); ax2.plot(sc, "s--", color=RED, alpha=.7)
    ax2.set_ylabel("Tenengrad skoru", color=RED)
    ax1.set_title("Kapali dongu otofokus: 0.25'ten baslayip en net odaga tirmanma")
    ax1.grid(alpha=.3); ax1.legend(loc="lower right")
    savefig("fig05_closed_loop", fig)


def fig_recovery():
    rng = np.random.default_rng(11)
    lens = SimLens(0.55)
    state = AutofocusController.initial_state(step=0.05)
    pos, events = [], []
    for i in range(140):
        if i == 60:                       # someone defocuses from the camera UI
            lens.focus = 0.15
            events.append(i)
        s = _sharpness(lens.focus, noise=0.10, rng=rng)
        pos.append(lens.focus)
        state = AutofocusController.step(lens, s, state, None)
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)
    ax.plot(pos, color=BLUE)
    ax.axhline(0.62, color="#718096", ls=":", label="en net odak")
    for e in events:
        ax.axvline(e, color=RED, ls="--", label="odak disaridan bozuldu")
    ax.set_xlabel("Kapali dongu adimi"); ax.set_ylabel("Odak konumu (0-1)")
    ax.set_title("Otomatik yeniden odaklanma: lens disaridan oynatildiginda toparlanma")
    ax.grid(alpha=.3); ax.legend()
    savefig("fig06_refocus_recovery", fig)


def fig_peaking_fix():
    plain = scene()
    spec = scene(spec=True)
    _, fm_plain, _ = FocusMeasures.tenengrad(plain)[0:3]
    g, fm_spec, _ = FocusMeasures.tenengrad(spec)[0:3]

    def old(img, fm):
        out = img.copy()
        mx = fm.max()
        if mx <= 0:
            return out, 0.0
        norm = (fm / mx * 255).astype(np.uint8)
        mask = norm > int(30.0 * 255 / 100)
        out[mask] = (out[mask] * 0.4 + np.array([0, 255, 0], np.float32) * 0.6).astype(np.uint8)
        return out, 100.0 * mask.mean()

    old_plain, pct_old_plain = old(plain, fm_plain)
    old_spec, pct_old_spec = old(spec, fm_spec)
    new_spec = OverlayRenderer.render(spec.copy(), g, fm_spec, 0, opts(show_peaking=True))
    pct_new_spec = 100.0 * (fm_spec > np.percentile(fm_spec, 70.0)).mean()
    save("fig07_peaking_fix", grid([
        label(old_plain, "Referans yontem, parlak nokta yok: alan %.1f%%" % pct_old_plain),
        label(old_spec, "Referans yontem, parlak nokta var: alan %.1f%%" % pct_old_spec),
        label(new_spec, "Duzeltme (yuzdelik esik): alan %.1f%%" % pct_new_spec),
    ], 3))
    print("     peaking: eski %.2f%% -> parlak noktayla %.2f%% | yeni %.2f%%"
          % (pct_old_plain, pct_old_spec, pct_new_spec))


def fig_bbox():
    img = scene()
    h, w = img.shape[:2]
    sharp_box = (60, 150, 150, 150)
    blurred = img.copy()
    x, y, bw, bh = int(w * 0.55), int(h * 0.30), 200, 160
    blurred[y:y + bh, x:x + bw] = cv2.GaussianBlur(blurred[y:y + bh, x:x + bw], (21, 21), 0)
    boxes = [sharp_box, (x, y, bw, bh)]

    class BB:
        def __init__(s, l, t, ww, hh):
            s.left, s.top, s.width, s.height = l, t, ww, hh

    class Det:
        def __init__(s, bb):
            s.boundingBox = bb

    _, _, overall, per_box = FocusMeasures.tenengrad(blurred, [Det(BB(*b)) for b in boxes])
    ann = blurred.copy()
    for (bx, by, bwid, bhei), sc in zip(boxes, per_box):
        cv2.rectangle(ann, (bx, by), (bx + bwid, by + bhei), (0, 200, 255), 2)
        cv2.putText(ann, "%.0f" % sc, (bx + 6, by + 26), FONT, 0.7, (0, 200, 255), 2, cv2.LINE_AA)
    save("fig08_bbox_scores",
         label(ann, "Genel skor %.0f  |  bolge skorlari kutularda (sag bolge bulanik)" % overall))


def main():
    os.makedirs(OUT, exist_ok=True)
    print("figures ->", os.path.relpath(OUT, PKG))
    fig_modes()
    fig_overlays()
    fig_blur_curve()
    fig_focus_curve()
    fig_closed_loop()
    fig_recovery()
    fig_peaking_fix()
    fig_bbox()
    print("done.")


if __name__ == "__main__":
    main()
