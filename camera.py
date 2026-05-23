"""
Developer 1 — camera capture for MacBook, Piper Dabai DC1, and Linux /dev/video*.

Why two capture backends?
-------------------------
**OpenCV (fast)** — single process, low latency. Used for the laptop webcam and on
Linux for Piper via V4L2 (/dev/video*).

**ffmpeg AVFoundation (correct on macOS Piper)** — opens the Dabai by *device name*
("Dabai DC1"). Required on Mac when multiple cameras are present because OpenCV
device *indices* do not match AVFoundation/ffmpeg ordering (index 1 may be iPhone
Continuity, not the Piper).

Trade-off: ffmpeg runs a subprocess and pipes raw frames → lower FPS on Mac, but
the correct camera feed. OpenCV index 0 is fast but is the MacBook built-in webcam.

Capture paths
-------------
Laptop (Mac)::

    vision.py → OpenCV VideoCapture(0) → AVFoundation → frame

Piper (Mac, recommended)::

    vision.py → ffmpeg "Dabai DC1" → AVFoundation → raw BGR pipe → frame

Piper (Linux, demo machine)::

    vision.py → OpenCV /dev/videoN (V4L2) → frame

Configuration (config.py)
-------------------------
- ``CAMERA_SOURCE`` — ``"piper"``, ``"laptop"``, ``0``, ``"/dev/video0"``, etc.
- ``CAMERA_BACKEND`` — ``"auto"`` | ``"opencv"`` | ``"ffmpeg"``
- ``PIPER_CAMERA_NAME`` — exact AVFoundation name on macOS (default ``"Dabai DC1"``)
- ``PIPER_OPENCV_INDEX`` — optional OpenCV index if you map Piper manually on Mac
- ``CAMERA_WIDTH`` / ``CAMERA_HEIGHT`` / ``CAMERA_FPS`` — resolution tuning

Run flags (override config for one session)
-------------------------------------------
::

    # Piper on Mac (correct Dabai, auto → ffmpeg)
    python vision.py --camera piper
    python main.py --camera piper

    # Laptop webcam (fast dev)
    python vision.py --camera laptop

    # Force backend
    python vision.py --camera piper --camera-backend ffmpeg   # correct, slower (Mac default)
    python vision.py --camera piper --camera-backend opencv   # fast only if PIPER_OPENCV_INDEX is set

    # Diagnostics
    python camera.py --list
    python camera.py --preview
    python camera.py --pick       # cycle cameras; y/n to find Piper OpenCV index
    python camera.py --pick-opencv   # OpenCV only (window shows faster on Mac)

See also: CAMERA.md (hardware + Orbbec SDK), README.md (Camera section), task-vision.md (Setup).
"""

from __future__ import annotations

import platform
import re
import select
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

import config

# Piper kit ships with Orbbec Dabai DC1 (UVC). Same device on Mac and Linux.
_PIPER_CAMERA_NAMES = ("dabai", "orbbec", "dc1", "uvc camera vendorid_11205")
_AVFOUNDATION_PREFIX = "avfoundation:"


@dataclass(frozen=True)
class CameraProbe:
    index: int
    opens: bool
    reads: bool
    width: int
    height: int
    backend: str
    device_path: str | None = None


def _backend_flag() -> int:
    if platform.system() == "Darwin":
        return cv2.CAP_AVFOUNDATION
    if platform.system() == "Linux":
        return cv2.CAP_V4L2
    return cv2.CAP_ANY


def _open_capture(source: int | str, backend: int | None = None):
    flag = backend if backend is not None else _backend_flag()
    if isinstance(source, str) and source.startswith("/dev/"):
        return cv2.VideoCapture(source, flag)
    return cv2.VideoCapture(int(source), flag)


def _is_avfoundation_source(source: int | str) -> bool:
    return isinstance(source, str) and source.startswith(_AVFOUNDATION_PREFIX)


def _avfoundation_device_name(source: str) -> str:
    return source[len(_AVFOUNDATION_PREFIX) :]


def _ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def list_avfoundation_devices() -> list[tuple[int, str]]:
    """Parse `ffmpeg -f avfoundation -list_devices true` → [(index, name), ...]."""
    ffmpeg = _ffmpeg_path()
    if not ffmpeg or platform.system() != "Darwin":
        return []
    try:
        proc = subprocess.run(
            [ffmpeg, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    devices: list[tuple[int, str]] = []
    in_video = False
    for line in proc.stderr.splitlines():
        if "AVFoundation video devices" in line:
            in_video = True
            continue
        if "AVFoundation audio devices" in line:
            break
        if not in_video:
            continue
        match = re.search(r"\[(\d+)\]\s*(.+)", line)
        if match:
            devices.append((int(match.group(1)), match.group(2).strip()))
    return devices


def find_piper_avfoundation_name() -> str | None:
    """Exact device name for ffmpeg/AVFoundation (macOS)."""
    configured = getattr(config, "PIPER_CAMERA_NAME", None)
    if configured:
        return str(configured)

    for _idx, name in list_avfoundation_devices():
        lower = name.lower()
        if any(tag in lower for tag in _PIPER_CAMERA_NAMES):
            return name

    for name in _system_camera_names():
        if any(tag in name for tag in _PIPER_CAMERA_NAMES):
            # system_profiler title-case, e.g. "dabai dc1" → "Dabai DC1"
            return name.title().replace("Dc1", "DC1")
    return None


def probe_camera(
    index: int, *, backend: int | None = None, warmup_reads: int = 5
) -> CameraProbe:
    cap = _open_capture(index, backend)
    opens = cap.isOpened()
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if opens else 0
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if opens else 0
    backend_name = cap.getBackendName() if opens else ""
    reads = False
    if opens:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        for _ in range(warmup_reads):
            ok, _ = cap.read()
            if ok:
                reads = True
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or width
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or height
                break
            time.sleep(0.05)
    cap.release()
    return CameraProbe(
        index=index,
        opens=opens,
        reads=reads,
        width=width,
        height=height,
        backend=backend_name,
    )


def probe_cameras(max_index: int = 6) -> list[CameraProbe]:
    found: list[CameraProbe] = []
    for i in range(max_index):
        probe = probe_camera(i)
        if probe.opens:
            found.append(probe)
    return found


def list_cameras(max_index: int = 6) -> list[int]:
    return [p.index for p in probe_cameras(max_index) if p.reads]


def _system_camera_names() -> list[str]:
    names: list[str] = []
    if platform.system() == "Darwin":
        try:
            out = subprocess.run(
                ["system_profiler", "SPCameraDataType"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            for line in out.stdout.splitlines():
                line = line.strip()
                if line.endswith(":") and not line.startswith("Camera"):
                    names.append(line[:-1].lower())
        except (OSError, subprocess.SubprocessError):
            pass
    elif platform.system() == "Linux":
        try:
            out = subprocess.run(
                ["v4l2-ctl", "--list-devices"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            for block in out.stdout.split("\n\n"):
                first = block.strip().splitlines()
                if first:
                    names.append(first[0].strip().lower())
        except (OSError, subprocess.SubprocessError, FileNotFoundError):
            pass
    return names


def _linux_piper_device_path() -> str | None:
    try:
        out = subprocess.run(
            ["v4l2-ctl", "--list-devices"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return None

    blocks = re.split(r"\n\s*\n", out.stdout.strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0].lower()
        if not any(tag in title for tag in _PIPER_CAMERA_NAMES):
            continue
        for line in lines[1:]:
            if line.startswith("/dev/video"):
                return line.split()[0]
    return None


def _piper_camera_reported() -> bool:
    return any(
        any(tag in name for tag in _PIPER_CAMERA_NAMES) for name in _system_camera_names()
    )


def find_piper_camera_source() -> str | int | None:
    """
    Resolve Piper / Dabai DC1 to a capture source for the active backend.

    auto:  ffmpeg by name on macOS; V4L2 path on Linux
    ffmpeg: AVFoundation device name on macOS (requires ffmpeg installed)
    opencv: /dev/video* on Linux; on macOS only if PIPER_OPENCV_INDEX is set
    """
    backend = getattr(config, "CAMERA_BACKEND", "auto").lower()

    if backend in ("auto", "ffmpeg") and platform.system() == "Darwin":
        if backend != "opencv":
            name = find_piper_avfoundation_name()
            if name and _ffmpeg_path():
                return f"{_AVFOUNDATION_PREFIX}{name}"
            if backend == "ffmpeg":
                return None

    if backend in ("auto", "opencv"):
        opencv_idx = getattr(config, "PIPER_OPENCV_INDEX", None)
        if opencv_idx is not None:
            return int(opencv_idx)

        dev = _linux_piper_device_path()
        if dev:
            cap = _open_capture(dev)
            if cap.isOpened():
                ok, _ = cap.read()
                cap.release()
                if ok:
                    return dev

    return None


def resolve_camera_source(source=None) -> int | str:
    if source is None:
        source = getattr(config, "CAMERA_SOURCE", None)

    if source is None or source == "":
        return config.CAMERA_INDEX

    if isinstance(source, int):
        return source

    text = str(source).strip()
    lower = text.lower()
    if lower.startswith("/dev/video"):
        return text

    if lower.isdigit():
        return int(lower)

    if lower.startswith("avfoundation:"):
        return text

    if lower in ("piper", "dabai", "orbbec"):
        picked = find_piper_camera_source()
        if picked is not None:
            return picked
        backend = getattr(config, "CAMERA_BACKEND", "auto")
        raise RuntimeError(
            "Piper camera (Dabai DC1) not found. Plug in USB, grant camera permission, "
            f"backend={backend!r}. On Mac use --camera-backend ffmpeg (needs brew install ffmpeg). "
            "Run: python camera.py --list"
        )

    if lower in ("laptop", "webcam", "builtin", "built-in"):
        return config.CAMERA_INDEX

    if lower == "auto":
        if _piper_camera_reported():
            picked = find_piper_camera_source()
            if picked is not None:
                return picked
        return config.CAMERA_INDEX

    raise ValueError(f"Unknown CAMERA_SOURCE: {source!r}")


def apply_camera_overrides(
    *,
    camera: str | int | None = None,
    camera_backend: str | None = None,
) -> None:
    """Override config camera settings for this process (CLI flags)."""
    if camera is not None:
        if isinstance(camera, int) or (isinstance(camera, str) and camera.isdigit()):
            config.CAMERA_SOURCE = int(camera)
        else:
            config.CAMERA_SOURCE = camera
    if camera_backend is not None:
        config.CAMERA_BACKEND = camera_backend.lower()


def add_camera_cli(parser) -> None:
    """Register --camera and --camera-backend on an argparse parser."""
    parser.add_argument(
        "--camera",
        metavar="SOURCE",
        help='Camera: piper, laptop, 0, 1, /dev/video0 (overrides config CAMERA_SOURCE)',
    )
    parser.add_argument(
        "--camera-backend",
        choices=("auto", "opencv", "ffmpeg"),
        help="Capture backend: auto (default), opencv (fast), ffmpeg (Mac Piper by name)",
    )
    parser.add_argument(
        "--orbbec-sdk",
        action="store_true",
        help="Use Orbbec pyorbbecsdk capture (RGB+depth) instead of OpenCV/ffmpeg",
    )


def configure_orbbec_from_args(args) -> None:
    if getattr(args, "orbbec_sdk", False):
        config.ENABLE_ORBBEC_SDK = True


def configure_camera_from_args(args) -> None:
    """Apply argparse namespace from add_camera_cli."""
    apply_camera_overrides(
        camera=getattr(args, "camera", None),
        camera_backend=getattr(args, "camera_backend", None),
    )
    configure_orbbec_from_args(args)


def open_camera(index: int | str | None = None):
    """
    Factory: Orbbec SDK when ``ENABLE_ORBBEC_SDK`` else ``Camera``.

    Orbbec path requires ``pip install -r requirements-orbbec.txt``.
    """
    if getattr(config, "ENABLE_ORBBEC_SDK", False):
        from orbbec_camera import OrbbecCamera

        return OrbbecCamera()
    return Camera(index=index)


class _FfmpegAvFoundationCamera:
    """Capture from a named AVFoundation device via ffmpeg (macOS Piper camera)."""

    def __init__(self, device_name: str, *, wait_for_first_frame: bool = True):
        self.device_name = device_name
        self._ffmpeg = _ffmpeg_path()
        if not self._ffmpeg:
            raise RuntimeError("ffmpeg not found — install with: brew install ffmpeg")

        self._fps = int(getattr(config, "CAMERA_FPS", 30))
        self._width = int(getattr(config, "CAMERA_WIDTH", None) or 640)
        self._height = int(getattr(config, "CAMERA_HEIGHT", None) or 480)
        self._proc: subprocess.Popen | None = None
        self._frame_bytes = 0
        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._wait_for_first_frame = wait_for_first_frame
        self._start()

    def _start(self) -> None:
        width, height = self._width, self._height

        cmd = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-probesize",
            "32",
            "-analyzeduration",
            "0",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-f",
            "avfoundation",
            "-framerate",
            str(self._fps),
            "-video_size",
            f"{width}x{height}",
            "-i",
            self.device_name,
            "-an",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "pipe:1",
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self._width = width
        self._height = height
        self._frame_bytes = width * height * 3

        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        if self._wait_for_first_frame:
            deadline = threading.Event()

            def _wait_first_frame():
                while not deadline.wait(0.05):
                    with self._lock:
                        if self._latest is not None:
                            return

            _wait_first_frame()
            with self._lock:
                if self._latest is None:
                    self.release()
                    raise RuntimeError(
                        f"Could not read from AVFoundation device {self.device_name!r}. "
                        "Check USB connection and camera permission."
                    )

    def _reader_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        stdout = self._proc.stdout
        frame_bytes = self._frame_bytes
        shape = (self._height, self._width, 3)

        while self._running and self._proc.poll() is None:
            # Drain pipe: keep only the newest complete frame (cuts latency).
            latest: np.ndarray | None = None
            while True:
                ready, _, _ = select.select([stdout], [], [], 0)
                if not ready:
                    break
                raw = stdout.read(frame_bytes)
                if len(raw) != frame_bytes:
                    if not self._running:
                        return
                    break
                latest = np.frombuffer(raw, dtype=np.uint8).reshape(shape)

            if latest is None:
                raw = stdout.read(frame_bytes)
                if len(raw) != frame_bytes:
                    continue
                latest = np.frombuffer(raw, dtype=np.uint8).reshape(shape)

            with self._lock:
                self._latest = latest.copy()

    @property
    def width(self) -> int:
        return int(self._width)

    @property
    def height(self) -> int:
        return int(self._height)

    def read_frame(self):
        with self._lock:
            if self._latest is None:
                return None
            return self._latest.copy()

    def release(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        with self._lock:
            self._latest = None


class Camera:
    """Low-latency camera: OpenCV index/path, or ffmpeg AVFoundation by name on macOS."""

    def __init__(self, index: int | str | None = None):
        if index is not None:
            self.source: int | str = index
        else:
            self.source = resolve_camera_source()

        self._cap = None
        self._ffmpeg_cam: _FfmpegAvFoundationCamera | None = None

        if _is_avfoundation_source(self.source):
            name = _avfoundation_device_name(self.source)
            self._ffmpeg_cam = _FfmpegAvFoundationCamera(name)
            self.index = -1
            print(
                f"[camera] Using AVFoundation {name!r} "
                f"({self._ffmpeg_cam.width}x{self._ffmpeg_cam.height}) via ffmpeg"
            )
            return

        self._cap = _open_capture(self.source)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, 30)

        width = getattr(config, "CAMERA_WIDTH", None)
        height = getattr(config, "CAMERA_HEIGHT", None)
        if width:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        if height:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))

        if not self._cap.isOpened():
            available = list_cameras()
            hint = f" OpenCV indices: {available}" if available else ""
            raise RuntimeError(
                f"Could not open camera {self.source!r}.{hint} "
                "Run: python camera.py --list"
            )

        ok, _ = self._cap.read()
        if not ok:
            self._cap.release()
            raise RuntimeError(
                f"Camera {self.source!r} opened but returned no frames. "
                "Run: python camera.py --list"
            )

        self.index = self.source if isinstance(self.source, int) else -1
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[camera] Using OpenCV source {self.source!r} ({w}x{h})")

    def read_frame(self):
        if self._ffmpeg_cam is not None:
            return self._ffmpeg_cam.read_frame()
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self):
        if self._ffmpeg_cam is not None:
            self._ffmpeg_cam.release()
            self._ffmpeg_cam = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def _print_probe_table(probes: list[CameraProbe]) -> None:
    if not probes:
        print("No OpenCV cameras found.")
        return
    print(f"{'idx':>4}  {'read':>4}  {'size':>12}  backend")
    for p in probes:
        size = f"{p.width}x{p.height}" if p.width else "?"
        print(f"{p.index:>4}  {str(p.reads):>4}  {size:>12}  {p.backend}")


def _linux_video_device_paths() -> list[str]:
    """All /dev/video* nodes from v4l2-ctl (Linux)."""
    try:
        out = subprocess.run(
            ["v4l2-ctl", "--list-devices"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return []

    paths: list[str] = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("/dev/video"):
            paths.append(line.split()[0])
    return paths


def _pick_candidates(*, opencv_only: bool = False) -> list[tuple[str, int | str]]:
    """(label, source) pairs to try in interactive picker."""
    candidates: list[tuple[str, int | str]] = []
    seen: set[str] = set()

    # OpenCV indices first — fast to open; best for finding PIPER_OPENCV_INDEX
    for i in range(8):
        probe = probe_camera(i, warmup_reads=8)
        if not probe.opens:
            continue
        key = f"idx:{i}"
        if key in seen:
            continue
        seen.add(key)
        size = f"{probe.width}x{probe.height}" if probe.width else "?"
        note = "" if probe.reads else " (warmup — preview may take a moment)"
        candidates.append((f"OpenCV index {i} ({size}){note}", i))

    if platform.system() == "Linux":
        for dev in _linux_video_device_paths():
            key = f"dev:{dev}"
            if key in seen:
                continue
            cap = _open_capture(dev)
            if not cap.isOpened():
                cap.release()
                continue
            ok = False
            for _ in range(8):
                ok, _ = cap.read()
                if ok:
                    break
                time.sleep(0.05)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if not ok:
                continue
            seen.add(key)
            candidates.append((f"{dev} ({w}x{h})", dev))

    if opencv_only:
        return candidates

    # macOS: named AVFoundation (ffmpeg) — slower to start; listed last
    if platform.system() == "Darwin":
        for idx, name in list_avfoundation_devices():
            lower = name.lower()
            if "desk view" in lower or "capture screen" in lower:
                continue
            key = f"avf:{name}"
            if key in seen:
                continue
            seen.add(key)
            candidates.append((f"AVFoundation [{idx}] {name}", f"{_AVFOUNDATION_PREFIX}{name}"))

    return candidates


class _PickSession:
    """Handle OpenCV or ffmpeg source in the camera picker loop."""

    def __init__(self, source: int | str):
        self.source = source
        self._cap = None
        self._ffmpeg: _FfmpegAvFoundationCamera | None = None
        self._ffmpeg_name: str | None = None
        if _is_avfoundation_source(source):
            self._ffmpeg_name = _avfoundation_device_name(source)
        else:
            self._cap = _open_capture(source)
            if self._cap.isOpened():
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                width = getattr(config, "CAMERA_WIDTH", None)
                height = getattr(config, "CAMERA_HEIGHT", None)
                if width:
                    self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
                if height:
                    self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))

    def _ensure_ffmpeg(self) -> bool:
        if self._ffmpeg_name is None:
            return self._ffmpeg is not None
        if self._ffmpeg is not None:
            return True
        try:
            self._ffmpeg = _FfmpegAvFoundationCamera(
                self._ffmpeg_name, wait_for_first_frame=False
            )
            return True
        except RuntimeError:
            return False

    @property
    def opened(self) -> bool:
        if self._ffmpeg_name is not None:
            return True
        return self._cap is not None and self._cap.isOpened()

    def read_frame(self, *, warmup_attempts: int = 45):
        """Read a frame; retry on failure (USB cameras often need warmup)."""
        if self._ffmpeg_name is not None and not self._ensure_ffmpeg():
            return None

        for attempt in range(warmup_attempts):
            if self._ffmpeg is not None:
                frame = self._ffmpeg.read_frame()
            else:
                ok, frame = self._cap.read()
                frame = frame if ok else None
            if frame is not None:
                return frame
            time.sleep(0.05 if attempt < 10 else 0.1)
        return None

    def release(self) -> None:
        if self._ffmpeg is not None:
            self._ffmpeg.release()
            self._ffmpeg = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def _print_pick_result(source: int | str, label: str) -> None:
    print(f"\nSelected: {label}")
    if _is_avfoundation_source(source):
        name = _avfoundation_device_name(source)
        print("\nThis is the ffmpeg-by-name path (correct on Mac, slower than OpenCV).")
        print("Add to config.py:")
        print(f'PIPER_CAMERA_NAME = "{name}"')
        print('CAMERA_SOURCE = "piper"')
        print('CAMERA_BACKEND = "ffmpeg"')
        print("\nOne-shot run:")
        print("python vision.py --camera piper --camera-backend ffmpeg")
        return
    if isinstance(source, int):
        print("\nAdd to config.py for fast OpenCV Piper capture:")
        print(f"PIPER_OPENCV_INDEX = {source}")
        print('CAMERA_SOURCE = "piper"')
        print('CAMERA_BACKEND = "opencv"')
        print("\nOne-shot run:")
        print(f"python vision.py --camera {source} --camera-backend opencv")
        print(f"python main.py --camera {source} --camera-backend opencv")
    else:
        print("\nAdd to config.py:")
        print(f'CAMERA_SOURCE = "{source}"')
        print('CAMERA_BACKEND = "opencv"')
        print("\nOne-shot run:")
        print(f"python vision.py --camera {source} --camera-backend opencv")


def _draw_pick_overlay(frame, label: str, index: int, total: int) -> None:
    lines = [
        f"Camera {index}/{total}: {label}",
        "Is this the Piper / camera you want?",
        "y = yes (save)   n = next   q = quit",
    ]
    y = 28
    for line in lines:
        cv2.putText(
            frame,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0),
            2,
        )
        y += 28


def _show_pick_placeholder(window: str, label: str, index: int, total: int, note: str = "") -> None:
    """Show a visible window immediately while the camera starts."""
    h, w = 480, 640
    placeholder = np.zeros((h, w, 3), dtype=np.uint8)
    text = label + (f" — {note}" if note else "")
    _draw_pick_overlay(placeholder, text, index, total)
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 960, 540)
    cv2.imshow(window, placeholder)
    cv2.waitKey(1)


def _cli_pick(*, opencv_only: bool = False) -> int:
    candidates = _pick_candidates(opencv_only=opencv_only)
    if not candidates:
        print("No cameras found. Try: python camera.py --list")
        return 1

    print("Camera picker — live preview for each device")
    print("  y = yes, save this camera")
    print("  n = next camera")
    print("  q = quit without saving")
    print("  (focus the 'Camera Picker' window — it may open behind this terminal)")
    if opencv_only:
        print("  Mode: OpenCV indices only (fast)")
    print(f"Found {len(candidates)} candidate(s):")
    for label, _ in candidates:
        print(f"  - {label}")
    print()

    window = "Camera Picker"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    try:
        for i, (label, source) in enumerate(candidates, start=1):
            time.sleep(0.35)
            print(f"Opening [{i}/{len(candidates)}] {label} ...", flush=True)
            _show_pick_placeholder(window, label, i, len(candidates), note="starting")

            session = _PickSession(source)
            if not session.opened:
                session.release()
                print(f"Skipping {label} (failed to open)")
                continue

            print(f"Showing [{i}/{len(candidates)}] {label} — press y/n/q in the preview window", flush=True)

            miss_streak = 0
            while True:
                frame = session.read_frame(warmup_attempts=1 if miss_streak else 45)
                if frame is None:
                    miss_streak += 1
                    if miss_streak == 1:
                        print(f"  Waiting for frames from {label}...")
                    if miss_streak >= 60:
                        print(f"  No frames from {label} after ~6s, skipping.")
                        break
                    cv2.waitKey(50)
                    continue

                miss_streak = 0
                preview = frame.copy()
                _draw_pick_overlay(preview, label, i, len(candidates))
                cv2.imshow(window, preview)
                key = cv2.waitKey(1) & 0xFF

                if key in (ord("y"), ord("Y")):
                    session.release()
                    cv2.destroyAllWindows()
                    _print_pick_result(source, label)
                    return 0
                if key in (ord("n"), ord("N")):
                    break
                if key in (ord("q"), ord("Q")):
                    session.release()
                    cv2.destroyAllWindows()
                    print("Quit — no camera saved.")
                    return 0

            session.release()
            try:
                cv2.destroyWindow(window)
            except cv2.error:
                pass

        cv2.destroyAllWindows()
        print("No camera selected (went through all candidates).")
        return 0
    finally:
        cv2.destroyAllWindows()


def _cli_list() -> int:
    names = _system_camera_names()
    if names:
        print("System cameras:", ", ".join(names))

    avf = list_avfoundation_devices()
    if avf:
        print("\nAVFoundation (ffmpeg) video devices:")
        for idx, name in avf:
            print(f"  [{idx}] {name}")

    print("\nOpenCV indices (may not match AVFoundation order):")
    _print_probe_table(probe_cameras(8))

    try:
        resolved = resolve_camera_source(getattr(config, "CAMERA_SOURCE", "auto"))
        print(f"\nconfig CAMERA_SOURCE → {resolved!r}")
    except RuntimeError as exc:
        print(f"\nconfig CAMERA_SOURCE → error: {exc}")

    piper = find_piper_camera_source()
    print(f"Piper pick: {piper!r}")
    print(f"CAMERA_BACKEND: {getattr(config, 'CAMERA_BACKEND', 'auto')!r}")
    return 0


def _cli_preview(source: str | None) -> int:
    import time

    src = resolve_camera_source(source) if source else resolve_camera_source()
    cam = Camera(index=src)
    print(f"Preview {src!r} — press q to quit")
    t_prev = time.monotonic()
    try:
        while True:
            frame = cam.read_frame()
            if frame is None:
                continue
            now = time.monotonic()
            fps = 1.0 / max(now - t_prev, 1e-6)
            t_prev = now
            cv2.putText(
                frame,
                f"fps: {fps:.0f}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
            cv2.imshow("Camera Preview", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: python camera.py [--list] [--preview [SOURCE]] [--pick] [--pick-opencv]")
        print("  --list         Show AVFoundation + OpenCV cameras and Piper auto-pick")
        print("  --preview      Live view + FPS (default: config CAMERA_SOURCE)")
        print("  --pick         Cycle all cameras; y=yes n=next q=quit")
        print("  --pick-opencv  Same but OpenCV indices only (faster; use to map Piper index)")
        print("")
        print("Backends: see module docstring and README.md § Camera")
        return 0
    if argv[0] == "--list":
        return _cli_list()
    if argv[0] == "--preview":
        src = argv[1] if len(argv) > 1 else None
        return _cli_preview(src)
    if argv[0] == "--pick":
        return _cli_pick(opencv_only=False)
    if argv[0] == "--pick-opencv":
        return _cli_pick(opencv_only=True)
    print(f"Unknown option: {argv[0]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
