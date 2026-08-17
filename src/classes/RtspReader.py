"""
RtspReader — backend-agnostic RTSP video reader.

Opens an RTSP URL with OpenCV/FFMPEG over TCP and runs a daemon thread that
continuously drains the stream, keeping only the latest decoded frame. read_frame
returns the freshest frame and drops the backlog, so processing slower than the
camera's frame rate does not accumulate latency (the preview stays real-time).
This class knows nothing about Dahua or ONVIF.
"""

import os
import threading
import time

import cv2


class RtspReader:
    def __init__(self, rtsp_url):
        self._url = rtsp_url
        self._capture = None
        self._reader = None
        self._stop = False
        self._latest = None
        self._lock = threading.Lock()

    def open(self):
        """Open the stream and start the background reader. Returns True on open."""
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        capture = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except cv2.error:
            pass
        if not capture.isOpened():
            capture.release()
            self._capture = None
            return False
        self._capture = capture
        self._stop = False
        self._latest = None
        self._reader = threading.Thread(target=self._loop, daemon=True)
        self._reader.start()
        return True

    def _loop(self):
        while not self._stop:
            capture = self._capture
            if capture is None:
                break
            ok, frame = capture.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            with self._lock:
                self._latest = frame

    def read_frame(self):
        """Return the most recent BGR frame, or None (older frames are dropped)."""
        if self._reader is None or not self._reader.is_alive():
            if not self.open():
                return None
        for _ in range(60):
            with self._lock:
                if self._latest is not None:
                    return self._latest
            time.sleep(0.02)
        return None

    def release(self):
        self._stop = True
        reader = self._reader
        if reader is not None:
            reader.join(timeout=1.0)
            self._reader = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._latest = None
