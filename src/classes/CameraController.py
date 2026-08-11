"""
CameraController — connect to a Dahua motorized-varifocal IP camera, pull its
RTSP video stream, and control focus/zoom via the Dahua HTTP CGI API
(HTTP Digest auth).

The CGI endpoints below were verified on a Dahua IPC-HFW1431T-ZS-2812-S4:
  - read status : /cgi-bin/devVideoInput.cgi?action=getFocusStatus
  - absolute set: /cgi-bin/devVideoInput.cgi?action=adjustFocus&focus=<0-1>&zoom=<0-1>
  - one-push AF : /cgi-bin/devVideoInput.cgi?action=autoFocus
  - incremental: /cgi-bin/ptz.cgi?action=start|stop&channel=<ch>&code=<ZoomTele|
                 ZoomWide|FocusNear|FocusFar>&arg1=0&arg2=<speed>&arg3=0
  - continuous AF toggle: configManager.cgi setConfig VideoInFocus[0][*].AutoFocusTrace

All CGI URLs are isolated in this class so an ONVIF backend can be added later
without touching the executors. Credentials are passed in at construction time
and are NEVER logged.
"""

import os
import threading
import time

import cv2
import requests
from requests.auth import HTTPDigestAuth


class CameraController:
    def __init__(self, ip, username, password, http_port=80, rtsp_port=554,
                 channel=1, subtype=0, timeout=5.0):
        self.ip = ip
        self.http_port = int(http_port)
        self.rtsp_port = int(rtsp_port)
        self.channel = int(channel)
        self.subtype = int(subtype)
        self.timeout = float(timeout)

        # kept private, only used to build auth / RTSP URL; never logged
        self._username = username
        self._password = password
        self._session = requests.Session()
        self._session.auth = HTTPDigestAuth(username, password)

        self._capture = None
        self._reader = None
        self._stop_reader = False
        self._latest_frame = None
        self._frame_lock = threading.Lock()

    # ------------------------------------------------------------------ URLs
    def _http_base(self):
        return "http://{}:{}".format(self.ip, self.http_port)

    def rtsp_url(self):
        return "rtsp://{user}:{pwd}@{ip}:{port}/cam/realmonitor?channel={ch}&subtype={st}".format(
            user=self._username, pwd=self._password, ip=self.ip,
            port=self.rtsp_port, ch=self.channel, st=self.subtype,
        )

    def _safe_rtsp_url(self):
        """RTSP URL with credentials masked, for logging/repr."""
        return "rtsp://***:***@{ip}:{port}/cam/realmonitor?channel={ch}&subtype={st}".format(
            ip=self.ip, port=self.rtsp_port, ch=self.channel, st=self.subtype,
        )

    # ------------------------------------------------------------- HTTP CGI
    def _cgi_get(self, path, params=None):
        """GET a CGI endpoint; return response text or None on failure.
        Never includes the password in the returned/raised value."""
        try:
            resp = self._session.get(self._http_base() + path, params=params,
                                     timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            return None

    @staticmethod
    def _parse_kv(text):
        result = {}
        if not text:
            return result
        for line in text.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
        return result

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def get_focus_status(self):
        """Return current lens status as a dict:
        {focus, zoom, focus_steps, zoom_steps, lens_adjust_status, status, raw}.
        Values are None if unavailable."""
        text = self._cgi_get("/cgi-bin/devVideoInput.cgi", {"action": "getFocusStatus"})
        kv = self._parse_kv(text)
        return {
            "focus": self._to_float(kv.get("status.Focus")),
            "zoom": self._to_float(kv.get("status.Zoom")),
            "focus_steps": self._to_int(kv.get("status.FocusMotorSteps")),
            "zoom_steps": self._to_int(kv.get("status.ZoomMotorSteps")),
            "lens_adjust_status": self._to_int(kv.get("status.LenAdjustStatus")),
            "status": kv.get("status.Status"),
            "raw": text,
        }

    @staticmethod
    def _clamp01(value):
        return max(0.0, min(1.0, float(value)))

    def set_focus_zoom(self, focus, zoom):
        """Set absolute focus and zoom (both 0.0-1.0). Returns True on 'OK'."""
        text = self._cgi_get("/cgi-bin/devVideoInput.cgi", {
            "action": "adjustFocus",
            "focus": "{:.4f}".format(self._clamp01(focus)),
            "zoom": "{:.4f}".format(self._clamp01(zoom)),
        })
        return text is not None and "OK" in text

    def trigger_autofocus(self):
        """Fire a one-push autofocus. Returns True on 'OK'."""
        text = self._cgi_get("/cgi-bin/devVideoInput.cgi", {"action": "autoFocus"})
        return text is not None and "OK" in text

    def _ptz(self, action, code, speed):
        return self._cgi_get("/cgi-bin/ptz.cgi", {
            "action": action, "channel": self.channel, "code": code,
            "arg1": 0, "arg2": speed, "arg3": 0,
        })

    def _ptz_pulse(self, code, speed, duration):
        started = self._ptz("start", code, speed)
        if started is None:
            return False
        time.sleep(max(0.0, float(duration)))
        stopped = self._ptz("stop", code, speed)
        return stopped is not None

    def step_focus(self, direction, speed=1, duration=0.3):
        """Nudge focus. direction: 'near' -> FocusNear, 'far' -> FocusFar."""
        code = "FocusNear" if str(direction).lower() == "near" else "FocusFar"
        return self._ptz_pulse(code, speed, duration)

    def step_zoom(self, direction, speed=1, duration=0.3):
        """Nudge zoom. direction: 'in'/'tele' -> ZoomTele, else ZoomWide."""
        code = "ZoomTele" if str(direction).lower() in ("in", "tele") else "ZoomWide"
        return self._ptz_pulse(code, speed, duration)

    def _seek(self, up_code, down_code, target, read_value,
              rate=0.30, speed=4, tolerance=0.04, max_passes=4):
        """Drive the lens to an absolute position (0-1) with OPEN-LOOP timed
        continuous moves.

        On this firmware the absolute 'adjustFocus' is unreliable/very slow, the
        status readout lags while the motor is moving (so closed-loop polling
        overshoots), and short low-speed pulses can't overcome the motor's
        start-up. But the motor runs at a roughly constant rate (~0.3 of the 0-1
        range per second at speed 4) and the status is accurate at rest. So:
        read the position while stopped, move for time = distance / rate, stop,
        settle, and repeat a couple of correction passes. Directions are fixed
        and known (up_code raises the value, down_code lowers it)."""
        target = self._clamp01(target)
        for _ in range(max_passes):
            current = read_value()
            if current is None:
                return False
            delta = target - current
            if abs(delta) <= tolerance:
                return True
            code = up_code if delta > 0 else down_code
            duration = min(abs(delta) / rate, 4.0)
            self._ptz("start", code, speed)
            time.sleep(duration)
            self._ptz("stop", code, speed)
            time.sleep(0.6)  # settle; the status readout is reliable at rest
        current = read_value()
        return current is not None and abs(current - target) <= tolerance

    def set_zoom(self, target, rate=0.30, speed=4, tolerance=0.04):
        """Set absolute zoom (0-1) with timed ZoomTele (in) / ZoomWide (out)."""
        return self._seek("ZoomTele", "ZoomWide", target,
                          lambda: self.get_focus_status().get("zoom"),
                          rate, speed, tolerance)

    def set_focus(self, target, rate=0.30, speed=4, tolerance=0.04):
        """Set absolute focus (0-1) with timed FocusFar (up) / FocusNear (down)."""
        return self._seek("FocusFar", "FocusNear", target,
                          lambda: self.get_focus_status().get("focus"),
                          rate, speed, tolerance)

    def set_continuous_autofocus(self, enabled):
        """Enable/disable the camera's own continuous autofocus tracking
        (VideoInFocus AutoFocusTrace). Disable this before driving focus manually
        or with the closed-loop controller so our commands are not overridden."""
        value = 1 if enabled else 0
        params = {"action": "setConfig"}
        # three profiles (general / day / night) reported by the camera
        for i in range(3):
            params["VideoInFocus[0][{}].AutoFocusTrace".format(i)] = value
        text = self._cgi_get("/cgi-bin/configManager.cgi", params)
        return text is not None and "OK" in text

    # ---------------------------------------------------------------- RTSP
    def open_stream(self):
        """Open the RTSP stream and start a background reader. Returns True if
        opened. A dedicated thread keeps draining the stream and holds only the
        latest frame, so processing that is slower than the camera's frame rate
        does not accumulate latency (the preview stays real-time)."""
        # Prefer TCP transport and a low buffer to keep latency down.
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        capture = cv2.VideoCapture(self.rtsp_url(), cv2.CAP_FFMPEG)
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except cv2.error:
            pass
        if not capture.isOpened():
            capture.release()
            self._capture = None
            return False
        self._capture = capture
        self._stop_reader = False
        self._latest_frame = None
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()
        return True

    def _reader_loop(self):
        while not self._stop_reader:
            capture = self._capture
            if capture is None:
                break
            ok, frame = capture.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            with self._frame_lock:
                self._latest_frame = frame

    def read_frame(self):
        """Return the most recent BGR frame, or None. Always the freshest frame
        the reader thread has decoded (older frames are dropped)."""
        if self._reader is None or not self._reader.is_alive():
            if not self.open_stream():
                return None
        for _ in range(60):
            with self._frame_lock:
                if self._latest_frame is not None:
                    return self._latest_frame
            time.sleep(0.02)
        return None

    def release(self):
        self._stop_reader = True
        reader = self._reader
        if reader is not None:
            reader.join(timeout=1.0)
            self._reader = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._latest_frame = None

    def close(self):
        self.release()
        try:
            self._session.close()
        except Exception:
            pass

    def __repr__(self):
        return "CameraController({}, channel={}, subtype={})".format(
            self._safe_rtsp_url(), self.channel, self.subtype)
