"""
DahuaCgiBackend — Dahua HTTP-CGI camera control backend (CameraBackend).

Focus/zoom control and lens status over the Dahua HTTP CGI API (HTTP Digest
auth), verified on a Dahua IPC-HFW1431T-ZS-2812-S4:
  - status      : /cgi-bin/devVideoInput.cgi?action=getFocusStatus
  - one-push AF : /cgi-bin/devVideoInput.cgi?action=autoFocus
  - incremental : /cgi-bin/ptz.cgi?action=start|stop&channel=<ch>&code=<ZoomTele|
                  ZoomWide|FocusNear|FocusFar>&arg1=0&arg2=<speed>&arg3=0
  - AF tracking : configManager.cgi setConfig VideoInFocus[0][*].AutoFocusTrace

Absolute focus/zoom is done with OPEN-LOOP timed continuous moves: the camera's
absolute 'adjustFocus' is unreliable/slow on this firmware, so we read the
position at rest, move for time = distance / rate, stop, settle, and correct.
Credentials are kept private and never logged.
"""

import time

import requests
from requests.auth import HTTPDigestAuth

from components.CameraFocus.src.classes.CameraBackend import CameraBackend


class DahuaCgiBackend(CameraBackend):
    def __init__(self, ip, username, password, http_port=80, rtsp_port=554,
                 channel=1, subtype=0, timeout=5.0):
        self.ip = ip
        self.http_port = int(http_port)
        self.rtsp_port = int(rtsp_port)
        self.channel = int(channel)
        self.subtype = int(subtype)
        self.timeout = float(timeout)
        self._username = username
        self._password = password
        self._session = requests.Session()
        self._session.auth = HTTPDigestAuth(username, password)

    # ------------------------------------------------------------------ URLs
    def _http_base(self):
        return "http://{}:{}".format(self.ip, self.http_port)

    def rtsp_url(self):
        return "rtsp://{u}:{p}@{ip}:{port}/cam/realmonitor?channel={ch}&subtype={st}".format(
            u=self._username, p=self._password, ip=self.ip,
            port=self.rtsp_port, ch=self.channel, st=self.subtype)

    # ------------------------------------------------------------- HTTP CGI
    def _cgi_get(self, path, params=None):
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

    @staticmethod
    def _clamp01(value):
        return max(0.0, min(1.0, float(value)))

    # --------------------------------------------------------------- status
    def get_status(self):
        text = self._cgi_get("/cgi-bin/devVideoInput.cgi", {"action": "getFocusStatus"})
        kv = self._parse_kv(text)
        return {
            "focus": self._to_float(kv.get("status.Focus")),
            "zoom": self._to_float(kv.get("status.Zoom")),
            "focus_steps": self._to_int(kv.get("status.FocusMotorSteps")),
            "zoom_steps": self._to_int(kv.get("status.ZoomMotorSteps")),
            "lens_adjust_status": self._to_int(kv.get("status.LenAdjustStatus")),
            "status": kv.get("status.Status"),
        }

    # legacy alias used by the current executor / AutofocusController
    def get_focus_status(self):
        return self.get_status()

    # --------------------------------------------------------------- control
    def set_focus_zoom(self, focus, zoom):
        """Absolute focus+zoom via adjustFocus (kept for AutofocusController)."""
        text = self._cgi_get("/cgi-bin/devVideoInput.cgi", {
            "action": "adjustFocus",
            "focus": "{:.4f}".format(self._clamp01(focus)),
            "zoom": "{:.4f}".format(self._clamp01(zoom)),
        })
        return text is not None and "OK" in text

    def trigger_autofocus(self):
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
        code = "FocusNear" if str(direction).lower() == "near" else "FocusFar"
        return self._ptz_pulse(code, speed, duration)

    def step_zoom(self, direction, speed=1, duration=0.3):
        code = "ZoomTele" if str(direction).lower() in ("in", "tele") else "ZoomWide"
        return self._ptz_pulse(code, speed, duration)

    def _seek(self, up_code, down_code, target, read_value,
              rate=0.30, speed=4, tolerance=0.04, max_passes=4):
        """Open-loop timed continuous move to an absolute position (0-1): read at
        rest, move for time = distance / rate, stop, settle, correct."""
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
            time.sleep(0.6)
        current = read_value()
        return current is not None and abs(current - target) <= tolerance

    def set_zoom(self, target, rate=0.30, speed=4, tolerance=0.04):
        return self._seek("ZoomTele", "ZoomWide", target,
                          lambda: self.get_status().get("zoom"),
                          rate, speed, tolerance)

    def set_focus(self, target, rate=0.30, speed=4, tolerance=0.04):
        return self._seek("FocusFar", "FocusNear", target,
                          lambda: self.get_status().get("focus"),
                          rate, speed, tolerance)

    def set_autofocus(self, enabled):
        """Enable/disable the camera's continuous AF tracking (AutoFocusTrace)."""
        value = 1 if enabled else 0
        params = {"action": "setConfig"}
        for i in range(3):  # general / day / night profiles
            params["VideoInFocus[0][{}].AutoFocusTrace".format(i)] = value
        text = self._cgi_get("/cgi-bin/configManager.cgi", params)
        return text is not None and "OK" in text

    # legacy alias used by the current executor
    def set_continuous_autofocus(self, enabled):
        return self.set_autofocus(enabled)

    def capabilities(self):
        return {"zoom": True, "focus": True, "autofocus": True}

    def close(self):
        try:
            self._session.close()
        except Exception:
            pass
