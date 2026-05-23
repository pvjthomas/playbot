"""Developer 1 — webcam capture."""

import cv2

import config


def list_cameras(max_index: int = 4) -> list[int]:
    """Return indices that open successfully (use when CAMERA_INDEX fails)."""
    found: list[int] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            found.append(i)
        cap.release()
    return found


class Camera:
    """Low-latency OpenCV webcam."""

    def __init__(self, index: int | None = None):
        self.index = index if index is not None else config.CAMERA_INDEX
        self._cap = cv2.VideoCapture(self.index)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, 30)

        if not self._cap.isOpened():
            available = list_cameras()
            hint = f" Available indices: {available}" if available else ""
            raise RuntimeError(
                f"Could not open webcam index {self.index}.{hint} "
                "Grant camera permission in System Settings, or try another index."
            )

    def read_frame(self):
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self):
        self._cap.release()
