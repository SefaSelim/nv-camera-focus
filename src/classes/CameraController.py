"""
CameraController — thin facade over an RtspReader (video) and a CameraBackend
(control).

The backend supplies the RTSP URL and performs focus/zoom/status control; the
reader owns the video stream. Video calls are served here, everything else is
delegated to the backend, so executors never touch protocol details.
"""

from components.CameraFocus.src.classes.RtspReader import RtspReader


class CameraController:
    def __init__(self, backend):
        self.backend = backend
        self.reader = None

    # ---- video ----
    def open_stream(self):
        """Resolve the stream URL from the backend and start reading it."""
        url = self.backend.rtsp_url()
        if not url:
            return False
        self.reader = RtspReader(url)
        return self.reader.open()

    def read_frame(self):
        if self.reader is None:
            if not self.open_stream():
                return None
        return self.reader.read_frame()

    def release(self):
        if self.reader is not None:
            self.reader.release()
            self.reader = None

    def close(self):
        self.release()
        self.backend.close()

    # ---- control: delegate to the backend ----
    def __getattr__(self, name):
        if name in ("backend", "reader"):
            raise AttributeError(name)
        return getattr(self.backend, name)

    def __repr__(self):
        return "CameraController(backend={})".format(type(self.backend).__name__)
