"""
CameraController — thin facade over a shared RtspReader (video) and a
CameraBackend (control).

Video (open_stream / read_frame / release) is served by the RtspReader; all
control calls (get_status, set_zoom, set_focus, set_autofocus, trigger_autofocus,
capabilities, and legacy aliases like get_focus_status / set_focus_zoom /
set_continuous_autofocus) are delegated to the backend. Defaults to the Dahua
CGI backend; pass a different backend (e.g. OnvifBackend) to control other
cameras without changing the executor.
"""

from components.CameraFocus.src.classes.RtspReader import RtspReader
from components.CameraFocus.src.classes.DahuaCgiBackend import DahuaCgiBackend


class CameraController:
    def __init__(self, ip, username, password, http_port=80, rtsp_port=554,
                 channel=1, subtype=0, timeout=5.0, backend=None):
        if backend is None:
            backend = DahuaCgiBackend(ip, username, password, http_port,
                                      rtsp_port, channel, subtype, timeout)
        self.backend = backend
        self.reader = RtspReader(backend.rtsp_url())

    # ---- video ----
    def open_stream(self):
        return self.reader.open()

    def read_frame(self):
        return self.reader.read_frame()

    def release(self):
        self.reader.release()

    def close(self):
        self.release()
        self.backend.close()

    # ---- control: delegate everything else to the backend ----
    def __getattr__(self, name):
        # Only reached for attributes not defined on the facade. Avoid recursion
        # before backend/reader are set.
        if name in ("backend", "reader"):
            raise AttributeError(name)
        return getattr(self.backend, name)

    def __repr__(self):
        return "CameraController(backend={})".format(type(self.backend).__name__)
