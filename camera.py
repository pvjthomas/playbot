"""Developer 1 — webcam capture."""

import cv2

import config


class Camera:
    """Low-latency OpenCV webcam."""

    def __init__(self, index: int | None = None):
        self.index = index if index is not None else config.CAMERA_INDEX
        self._cap = cv2.VideoCapture(self.index)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, 30)

        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open webcam index {self.index}. "
                "Try another index or grant camera permission."
            )

    def read_frame(self):
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self):
        self._cap.release()
