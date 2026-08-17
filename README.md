# CameraFocus

A NovaVision capsule package that connects to an IP camera, measures its focus,
and (optionally) controls the camera's focus and zoom.

It is a single, camera-connected executor. A **Mode** dropdown selects the
behaviour; the camera connection is entered once and shared across modes. Camera
control is **vendor-neutral over ONVIF** by default, with a Dahua HTTP-CGI
backend available as an option.

## Modes

| Mode | What it does | Outputs |
|------|--------------|---------|
| **Brenner** | Brenner focus map + overall focus measure | `outputImage` (focus map), `outputFocusMeasure` |
| **Tenengrad** | Tenengrad measure with overlays (zebra, focus peaking, HUD, grid, center) + per-detection measures | `+ outputBboxFocusMeasures` |
| **Stream** | Tenengrad measure + overlays **and** live camera focus/zoom control | `+ outputCameraStatus` |

In every mode the video is pulled live from the camera. Outputs are unified and
always present: `outputImage`, `outputFocusMeasure`, `outputBboxFocusMeasures`
(empty for Brenner), and `outputCameraStatus` (protocol, detected capabilities,
and the lens focus/zoom).

## Camera connection (shared parameters)

- **Camera Protocol** — `ONVIF` (default, multi-brand) or `Dahua HTTP-CGI`.
- **Camera IP**, **Camera Username**, **Camera Password** (plain text field so it
  is editable; the executor never logs it).
- **Camera HTTP/ONVIF Port** (default 80), **Camera RTSP Port** (default 554),
  **Camera Channel** (default 1), **Stream Subtype** (Main / Sub — use **Sub**
  for the smoothest live preview).

**Prerequisite:** the executor's runtime must be able to reach the camera IP on
the network (the camera and the runtime on the same LAN, or a routable path). For
the ONVIF protocol the runtime image must have `onvif-zeep` installed (like
`opencv-python-headless`).

### Enabling ONVIF on the camera

ONVIF must be enabled on the camera and an ONVIF user must exist (often the admin
account works). On Dahua: *Setting → Network → ONVIF*, enable it and set/confirm
the ONVIF authentication. Then use that username/password here.

## Stream mode — focus/zoom control

**Focus Mode:**
- **Manual** — writes the `Focus Value` / `Zoom Value` (0.0–1.0) to the camera.
  If `Trigger Autofocus` is enabled it fires a one-push autofocus instead.
- **One-Push Autofocus** — fires the camera's own autofocus once.
- **Closed-Loop Autofocus** — continuously hill-climbs the Tenengrad focus
  measure to find the sharpest focus, without relying on the camera's autofocus.

The connected camera's capabilities (zoom / focus / autofocus) are auto-detected
and reported in `outputCameraStatus`; controls that a camera does not support are
skipped gracefully.

### How positioning works

- **Zoom** uses ONVIF `AbsoluteMove` where supported (exact and fast). If a
  camera exposes only continuous zoom, a timed continuous-move fallback is used.
- **Focus** tries ONVIF absolute `Move` first (portable); if the camera's lens
  does not track absolute focus, it falls back to a timed continuous-move seek.
- Absolute-positioning accuracy and speed depend on the camera. On a varifocal
  lens, focus and zoom can be coupled (changing one shifts the other); Manual
  mode sets focus first and then (re)asserts zoom so the zoom target holds.

## Local test client

`client.py` runs the executor without the platform or Redis.

```bash
# offline (synthetic frame, mock camera):
python client.py --mode tenengrad

# real camera over ONVIF:
python client.py --camera-ip 10.20.30.139 --camera-password PASS \
    --mode stream --focus-mode Manual --zoom 0.4 --focus 0.6
```

It prints the focus measure, per-box measures, and camera status (protocol +
capabilities), and writes the output image. The password is never printed.

## Architecture

- `src/models/PackageModel.py` — the schema (single `CameraFocus` executor, Mode
  dropdown, shared camera-connection configs).
- `src/executors/CameraFocus.py` — thin adapter: reads parameters, pulls a frame,
  runs the selected mode, and (in Stream mode) drives the camera.
- `src/classes/` — pure logic:
  - `RtspReader` (background-thread RTSP reader, keeps the latest frame),
  - `CameraBackend` (control interface) with `OnvifBackend` and `DahuaCgiBackend`,
  - `CameraController` (facade: reader + backend),
  - `FocusMeasures` (Brenner / Tenengrad), `Visualization`, `OverlayRenderer`,
    `AutofocusController` (closed-loop hill-climb), `InputGate`.
- `src/utils/response.py` — builds the unified response.

## Dependencies

`sdk`, `opencv-python-headless`, `numpy`, `requests`, `onvif-zeep`.
