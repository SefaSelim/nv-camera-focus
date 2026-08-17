"""
CameraBackend — abstract control interface for an IP camera.

A backend knows how to reach one camera's control plane: it yields an RTSP URL
for the video (consumed by the shared RtspReader) and exposes focus/zoom/status
control, normalized to 0.0-1.0. Concrete backends are protocol-specific
(DahuaCgiBackend, OnvifBackend) so the executor and model contain no protocol
details. Implementations must never log credentials and must never raise out of
these methods (return None/False on failure).
"""


class CameraBackend:
    def rtsp_url(self):
        """Return the RTSP URL (with credentials) for the video stream."""
        raise NotImplementedError

    def get_status(self):
        """Return lens status as a dict, at least {"focus": float|None,
        "zoom": float|None, "status": str|None} with focus/zoom normalized 0-1."""
        raise NotImplementedError

    def set_zoom(self, target):
        """Set absolute zoom (0.0-1.0). Return True on success."""
        raise NotImplementedError

    def set_focus(self, target):
        """Set absolute focus (0.0-1.0). Return True on success."""
        raise NotImplementedError

    def set_autofocus(self, enabled):
        """Enable/disable the camera's own continuous autofocus. Disable before
        driving focus manually or with the closed-loop controller. Return True on
        success."""
        raise NotImplementedError

    def trigger_autofocus(self):
        """Fire a one-shot autofocus. Return True on success."""
        raise NotImplementedError

    def capabilities(self):
        """Return {"zoom": bool, "focus": bool, "autofocus": bool} describing
        which controls the connected camera actually supports."""
        raise NotImplementedError

    def close(self):
        """Release any control-plane resources (sessions, clients)."""
        pass
