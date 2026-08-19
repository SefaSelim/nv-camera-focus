"""
OnvifBackend — vendor-neutral camera control over ONVIF (onvif-zeep).

Video URI via the Media service, zoom via the PTZ service, focus via the Imaging
service. Focus/zoom are exposed to the rest of the package normalized 0.0-1.0.

Verified on a Dahua IPC-HFW1431T-ZS-2812-S4:
  - Media GetProfiles -> profile token + VideoSourceConfiguration.SourceToken;
    GetStreamUri -> RTSP URL (credentials injected for the reader).
  - Zoom: PTZ AbsoluteMove Position.Zoom.x is exact and fast (0..1).
  - Focus: Imaging Move Absolute did NOT move this Dahua's lens, but Imaging
    Continuous focus does -> absolute is tried first (portable), then a timed
    continuous-move fallback (read-at-rest / move-by-time / stop / correct).

Every ONVIF call is wrapped in try/except; failures return None/False instead of
raising. Credentials are kept private and never logged.
"""

import time

from components.CameraFocus.src.classes.CameraBackend import CameraBackend

try:
    from onvif import ONVIFCamera
except Exception:  # onvif-zeep not installed in this runtime
    ONVIFCamera = None


class OnvifBackend(CameraBackend):
    def __init__(self, ip, username, password, port=80, subtype=0, timeout=5.0):
        self.ip = ip
        self.port = int(port)
        self.subtype = int(subtype)
        self.timeout = float(timeout)
        self._username = username
        self._password = password

        self._cam = None
        self._media = None
        self._ptz = None
        self._imaging = None
        self._profile_token = None
        self._vsource_token = None
        self._focus_range = (0.0, 1.0)
        self._caps = None
        self._zoom_mode = None   # None (unknown) | "absolute" | "continuous"
        self._focus_mode = None
        self._focus_relative = None  # True if the camera supports relative focus

    # --------------------------------------------------------------- connect
    def _connect(self):
        if self._cam is not None:
            return True
        if ONVIFCamera is None:
            return False
        try:
            cam = ONVIFCamera(self.ip, self.port, self._username, self._password)
            media = cam.create_media_service()
            profile = media.GetProfiles()[0]
            self._profile_token = profile.token
            try:
                self._vsource_token = profile.VideoSourceConfiguration.SourceToken
            except Exception:
                self._vsource_token = None
            self._cam = cam
            self._media = media
            try:
                self._ptz = cam.create_ptz_service()
            except Exception:
                self._ptz = None
            try:
                self._imaging = cam.create_imaging_service()
            except Exception:
                self._imaging = None
            self._detect_focus_range()
            return True
        except Exception:
            self._cam = None
            return False

    def _detect_focus_range(self):
        if not (self._imaging and self._vsource_token):
            return
        try:
            mo = self._imaging.GetMoveOptions({"VideoSourceToken": self._vsource_token})
        except Exception:
            return
        try:
            mn = float(mo.Absolute.Position.Min)
            mx = float(mo.Absolute.Position.Max)
            if mx > mn:
                self._focus_range = (mn, mx)
        except Exception:
            pass
        self._focus_relative = getattr(mo, "Relative", None) is not None

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _clamp01(value):
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_focus_range(self, t01):
        mn, mx = self._focus_range
        return mn + self._clamp01(t01) * (mx - mn)

    def _from_focus_range(self, pos):
        pos = self._to_float(pos)
        if pos is None:
            return None
        mn, mx = self._focus_range
        if mx <= mn:
            return pos
        return (pos - mn) / (mx - mn)

    def _inject_credentials(self, uri):
        if not uri or "://" not in uri:
            return uri
        scheme, rest = uri.split("://", 1)
        host_part = rest.split("/", 1)[0]
        if "@" in host_part:
            return uri
        return "{}://{}:{}@{}".format(scheme, self._username, self._password, rest)

    # -------------------------------------------------------------- interface
    def rtsp_url(self):
        if not self._connect():
            return None
        try:
            req = self._media.create_type("GetStreamUri")
            req.StreamSetup = {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}}
            req.ProfileToken = self._profile_token
            uri = self._media.GetStreamUri(req).Uri
        except Exception:
            return None
        return self._inject_credentials(uri)

    def _read_zoom(self):
        if not (self._ptz and self._profile_token):
            return None
        try:
            return self._to_float(self._ptz.GetStatus({"ProfileToken": self._profile_token}).Position.Zoom.x)
        except Exception:
            return None

    def _read_focus(self):
        if not (self._imaging and self._vsource_token):
            return None
        try:
            pos = self._imaging.GetStatus({"VideoSourceToken": self._vsource_token}).FocusStatus20.Position
            return self._from_focus_range(pos)
        except Exception:
            return None

    def get_status(self):
        self._connect()
        return {"focus": self._read_focus(), "zoom": self._read_zoom(), "status": "Onvif"}

    def capabilities(self):
        self._connect()
        if self._caps is None:
            zoom = focus = autofocus = False
            if self._ptz and self._profile_token:
                zoom = self._read_zoom() is not None
            if self._imaging and self._vsource_token:
                try:
                    mo = self._imaging.GetMoveOptions({"VideoSourceToken": self._vsource_token})
                    focus = getattr(mo, "Absolute", None) is not None or \
                        getattr(mo, "Continuous", None) is not None
                except Exception:
                    pass
                try:
                    s = self._imaging.GetImagingSettings({"VideoSourceToken": self._vsource_token})
                    autofocus = getattr(getattr(s, "Focus", None), "AutoFocusMode", None) is not None
                except Exception:
                    pass
            self._caps = {"zoom": bool(zoom), "focus": bool(focus), "autofocus": bool(autofocus)}
        return self._caps

    def set_autofocus(self, enabled):
        self._connect()
        if not (self._imaging and self._vsource_token):
            return False
        try:
            s = self._imaging.GetImagingSettings({"VideoSourceToken": self._vsource_token})
            s.Focus.AutoFocusMode = "AUTO" if enabled else "MANUAL"
            self._imaging.SetImagingSettings({"VideoSourceToken": self._vsource_token, "ImagingSettings": s})
            return True
        except Exception:
            return False

    def trigger_autofocus(self):
        return self.set_autofocus(True)

    def set_zoom(self, target):
        self._connect()
        if not (self._ptz and self._profile_token):
            return False
        return self._position("zoom", self._clamp01(target))

    def set_focus(self, target):
        self._connect()
        if not (self._imaging and self._vsource_token):
            return False
        # Prefer RELATIVE focus moves where available: they are the natural
        # primitive for focus (nudge by a distance), and on cameras where the
        # absolute/continuous focus commands disturb the zoom motor (observed on
        # Dahua varifocal lenses) the relative move leaves zoom untouched.
        if self._focus_relative:
            return self._seek_relative(self._clamp01(target))
        return self._position("focus", self._clamp01(target))

    def _rel_move(self, distance):
        try:
            self._imaging.Move({"VideoSourceToken": self._vsource_token,
                                "Focus": {"Relative": {"Distance": distance}}})
            return True
        except Exception:
            return False

    def _seek_relative(self, target, tolerance=0.03, max_passes=3, settle=1.2):
        """Move focus to an absolute 0-1 target using relative nudges
        (distance = target - current), verifying and correcting between passes."""
        for _ in range(max_passes):
            current = self._read_focus()
            if current is None:
                return False
            delta = target - current
            if abs(delta) <= tolerance:
                return True
            if not self._rel_move(delta):
                return False
            time.sleep(settle)
        current = self._read_focus()
        return current is not None and abs(current - target) <= tolerance

    def close(self):
        pass

    # --------------------------------------------- absolute / continuous moves
    def _abs_move(self, kind, target):
        try:
            if kind == "zoom":
                self._ptz.AbsoluteMove({"ProfileToken": self._profile_token,
                                        "Position": {"Zoom": {"x": target}}})
            else:
                self._imaging.Move({"VideoSourceToken": self._vsource_token,
                                    "Focus": {"Absolute": {"Position": self._to_focus_range(target)}}})
            return True
        except Exception:
            return False

    def _cont_move(self, kind, speed):
        try:
            if kind == "zoom":
                self._ptz.ContinuousMove({"ProfileToken": self._profile_token,
                                          "Velocity": {"Zoom": {"x": speed}}})
            else:
                self._imaging.Move({"VideoSourceToken": self._vsource_token,
                                    "Focus": {"Continuous": {"Speed": speed}}})
            return True
        except Exception:
            return False

    def _cont_stop(self, kind):
        try:
            if kind == "zoom":
                self._ptz.Stop({"ProfileToken": self._profile_token, "PanTilt": True, "Zoom": True})
            else:
                self._imaging.Stop({"VideoSourceToken": self._vsource_token})
        except Exception:
            pass

    def _read(self, kind):
        return self._read_zoom() if kind == "zoom" else self._read_focus()

    def _position(self, kind, target, tolerance=0.05):
        """Move an axis to an absolute 0-1 target. On first use, try AbsoluteMove
        and verify it tracked; if it did not (some cameras' focus), remember to
        use the timed continuous-move fallback thereafter."""
        mode_attr = "_zoom_mode" if kind == "zoom" else "_focus_mode"
        mode = getattr(self, mode_attr)

        if mode == "absolute":
            return self._abs_move(kind, target)

        if mode is None:
            if self._abs_move(kind, target):
                time.sleep(2.0)
                after = self._read(kind)
                if after is not None and abs(after - target) <= 0.06:
                    setattr(self, mode_attr, "absolute")
                    return True
            setattr(self, mode_attr, "continuous")

        return self._seek_continuous(kind, target, tolerance)

    def _seek_continuous(self, kind, target, tolerance=0.05):
        """Open-loop timed continuous move: read at rest, move for
        time = distance / rate in the right direction, stop, settle, correct.
        rate/speed are per-axis (focus moves much slower than zoom on typical
        ONVIF cameras)."""
        if kind == "zoom":
            rate, speed, max_passes = 0.30, 0.7, 4
        else:
            rate, speed, max_passes = 0.10, 1.0, 5
        for _ in range(max_passes):
            current = self._read(kind)
            if current is None:
                return False
            delta = target - current
            if abs(delta) <= tolerance:
                return True
            velocity = speed if delta > 0 else -speed
            duration = min(abs(delta) / rate, 4.0)
            self._cont_move(kind, velocity)
            time.sleep(duration)
            self._cont_stop(kind)
            time.sleep(0.6)
        current = self._read(kind)
        return current is not None and abs(current - target) <= tolerance
