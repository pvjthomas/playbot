"""
Orbbec Python SDK loader — optional dependency for depth / IR / IMU.

Default vision uses OpenCV/ffmpeg (`camera.py`). Enable the SDK path with
``ENABLE_ORBBEC_SDK = True`` in ``config.py`` (see ``orbbec_camera.py``).

Install (optional):
    pip install -r requirements-orbbec.txt

Docs: CAMERA.md
"""

from __future__ import annotations

import importlib
import platform
from dataclasses import dataclass
from typing import Any

INSTALL_DOC = "projects/lightsaber/CAMERA.md"
INSTALL_CMD = "pip install -r requirements-orbbec.txt"


class OrbbecSdkUnavailableError(ImportError):
    """Raised when Orbbec SDK features are requested but the package cannot load."""


@dataclass(frozen=True)
class OrbbecSdkStatus:
    installed: bool
    import_error: str | None
    module_name: str | None
    platform_note: str | None = None


def _platform_note() -> str | None:
    system = platform.system()
    machine = platform.machine()
    if system == "Darwin" and machine == "x86_64":
        return (
            "Intel macOS: pyorbbecsdk wheels may be arm64-only. "
            "Use Ubuntu at the arm, or keep ENABLE_ORBBEC_SDK=False and OpenCV/ffmpeg capture."
        )
    if system == "Linux":
        return (
            "Linux: prefer pyorbbecsdk2 from PyPI or a wheel from "
            "https://github.com/orbbec/pyorbbecsdk/releases"
        )
    return None


def sdk_status() -> OrbbecSdkStatus:
    """Probe whether ``import pyorbbecsdk`` works in this venv."""
    last_error = "not installed"
    for name in ("pyorbbecsdk",):
        try:
            importlib.import_module(name)
            return OrbbecSdkStatus(
                installed=True,
                import_error=None,
                module_name=name,
                platform_note=_platform_note(),
            )
        except ImportError as exc:
            last_error = str(exc)
    return OrbbecSdkStatus(
        installed=False,
        import_error=last_error,
        module_name=None,
        platform_note=_platform_note(),
    )


def sdk_available() -> bool:
    return sdk_status().installed


def import_sdk() -> Any:
    """Return the imported ``pyorbbecsdk`` module, or ``None`` if unavailable."""
    status = sdk_status()
    if not status.module_name:
        return None
    return importlib.import_module(status.module_name)


def require_sdk() -> Any:
    """Import SDK or raise with install instructions."""
    mod = import_sdk()
    if mod is not None:
        return mod
    status = sdk_status()
    hint = f"Run: {INSTALL_CMD}. See {INSTALL_DOC}."
    if status.platform_note:
        hint = f"{status.platform_note} {hint}"
    if status.import_error:
        hint = f"{status.import_error} — {hint}"
    raise OrbbecSdkUnavailableError(hint)


def install_hint() -> str:
    status = sdk_status()
    if status.installed:
        return f"Orbbec SDK loaded ({status.module_name})."
    parts = [f"Orbbec SDK not available. Run: {INSTALL_CMD}"]
    if status.import_error:
        parts.append(f"Import error: {status.import_error}")
    if status.platform_note:
        parts.append(status.platform_note)
    return " ".join(parts)
