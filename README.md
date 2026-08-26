# CameraFocus

A NovaVision capsule package that connects to an IP camera, measures its focus,
and (optionally) controls the camera's focus and zoom.

It is a single, camera-connected executor. A **Mode** dropdown selects the
behaviour; the camera connection is entered once and shared across modes. Video
and control both run over **ONVIF**, the vendor-neutral standard supported by
most IP cameras, so the same package works across brands.

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

- **Camera IP**, **Camera Username**, **Camera Password** (plain text field so it
  is editable; the executor never logs it).
- **Camera ONVIF Port** (default 80).
- **Stream Subtype** — selects the ONVIF media profile: **Main** (first profile,
  high resolution) or **Sub** (second profile, lighter). Use **Sub** for the
  smoothest live preview.

The RTSP stream URL is discovered from the camera over ONVIF, so no stream path,
RTSP port or channel has to be configured.

**Prerequisites:** the executor's runtime must reach the camera IP on the network
(same LAN or a routable path), and the runtime image must provide an ONVIF client
package — either `onvif-zeep` or `onvif-zeep-async`; the backend supports both.

### Enabling ONVIF on the camera

ONVIF must be enabled on the camera and an ONVIF user must exist (often the admin
account works). On Dahua: *Setting → Network → ONVIF*, enable it and set/confirm
the ONVIF authentication. Then use that username/password here.

## Stream mode — focus/zoom control

**Zoom Value** (0.0–1.0) applies in every focus mode. **Focus Mode** then decides
how focus is driven, and shows only the parameters that mode needs:

- **Manual** — you enter a **Focus Value** (0.0–1.0) and it is written to the
  camera. Zoom is applied first, then focus, because a zoom move shifts focus on
  a varifocal lens.
- **One-Push Autofocus** — fires the camera's own autofocus once (no extra
  parameters).
- **Closed-Loop Autofocus** — the package focuses by itself: it hill-climbs the
  Tenengrad focus measure with a configurable **Focus Search Step**, and keeps
  watching afterwards, restarting the search automatically when sharpness drops
  (scene change or a disturbed lens).

The connected camera's capabilities (zoom / focus / autofocus) are auto-detected
and reported in `outputCameraStatus`; controls that a camera does not support are
skipped gracefully.

### How positioning works

- **Zoom** uses ONVIF `AbsoluteMove` where supported (exact and fast); a timed
  continuous-move fallback covers cameras that only expose continuous zoom.
- **Focus** prefers ONVIF **relative** moves (nudge by a distance), which are
  precise and leave zoom untouched. Absolute and timed-continuous seeks are used
  as fallbacks when a camera does not advertise relative focus.
- Accuracy and speed depend on the camera. On a varifocal lens a zoom move shifts
  focus, so zoom is always applied before focus.

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
  - `CameraBackend` (control interface) implemented by `OnvifBackend`,
  - `CameraController` (facade: reader + backend),
  - `FocusMeasures` (Brenner / Tenengrad), `Visualization`, `OverlayRenderer`,
    `AutofocusController` (closed-loop hill-climb), `InputGate`.
- `src/utils/response.py` — builds the unified response.

## Dependencies

`sdk`, `opencv-python-headless`, `numpy`, `requests`, and an ONVIF client
(`onvif-zeep` or `onvif-zeep-async`).
