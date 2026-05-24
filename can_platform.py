"""
Platform-specific PiPER CAN setup.

Linux (VM or bare metal): SocketCAN ``can0`` via ``gs_usb`` kernel module + ``can-up.sh``.
macOS: no ``can0`` — candleLight uses python-can ``gs_usb`` (USB userspace), not SocketCAN.

This repo uses ``piper_sdk`` (not AgileX's newer ``pyAgxArm``, which is intended for
Mac-native use with serial/SLCAN CAN hardware). The Linux VM path is a workaround for
the kit candleLight adapter on Mac — see MAC-ROBOT.md and ubuntu_shared/MAC-QEMU-ROBOT-VM.md.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Type

import config

_CANDLELIGHT_VID_PID = "1d50:606f"


@dataclass(frozen=True)
class CanProfile:
    """Arguments for piper_sdk connect (see demo V2/piper_set_can.py)."""

    bustype: str
    channel: str
    judge_flag: bool
    use_create_can_bus: bool
    label: str


def system_name() -> str:
    return platform.system()


def is_linux() -> bool:
    return system_name() == "Linux"


def is_darwin() -> bool:
    return system_name() == "Darwin"


def resolve_can_profile() -> CanProfile:
    """Map config.CAN_BUSTYPE / CAN_CHANNEL to a piper_sdk + python-can profile."""
    bustype = (config.CAN_BUSTYPE or "auto").lower()
    channel = config.CAN_CHANNEL

    if bustype == "auto":
        if is_linux():
            bustype = "socketcan"
            channel = config.CAN_INTERFACE if channel in ("", "auto") else channel
        elif is_darwin():
            bustype = "gs_usb"
            channel = "0" if channel in ("", "auto") else channel
        else:
            bustype = "socketcan"
            channel = config.CAN_INTERFACE if channel in ("", "auto") else channel

    if channel in ("", "auto"):
        if bustype == "socketcan":
            channel = config.CAN_INTERFACE
        elif bustype == "gs_usb":
            channel = "0"
        else:
            channel = config.CAN_INTERFACE

    if bustype == "socketcan":
        return CanProfile(
            bustype="socketcan",
            channel=channel,
            judge_flag=True,
            use_create_can_bus=False,
            label=f"socketcan:{channel}",
        )

    return CanProfile(
        bustype=bustype,
        channel=str(channel),
        judge_flag=False,
        use_create_can_bus=True,
        label=f"{bustype}:{channel}",
    )


def mac_candlelight_visible() -> bool:
    """True if system_profiler reports the kit candleLight adapter on macOS."""
    if not is_darwin():
        return False
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPUSBDataType"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    lower = out.lower()
    return "candlelight" in lower or _CANDLELIGHT_VID_PID.replace(":", "") in lower.replace(" ", "")


def gs_usb_dependencies_ok() -> tuple[bool, str]:
    """Check python-can gs_usb backend dependencies (pyusb / libusb)."""
    try:
        import usb  # noqa: F401
    except ImportError:
        return False, 'pip install "python-can[gs-usb]"'
    try:
        import can

        can.interface.Bus  # noqa: B018 — ensure can loads
    except ImportError as exc:
        return False, str(exc)
    return True, "ok"


def probe_gs_usb_open(channel: str | int = 0, bitrate: int | None = None) -> tuple[bool, str]:
    """Try opening gs_usb once (read-only). Does not send arm commands."""
    ok, hint = gs_usb_dependencies_ok()
    if not ok:
        return False, hint
    import can

    br = bitrate if bitrate is not None else config.CAN_BITRATE
    try:
        bus = can.interface.Bus(interface="gs_usb", channel=channel, bitrate=br)
        bus.shutdown()
        return True, f"gs_usb channel={channel} @ {br}"
    except Exception as exc:
        msg = str(exc)
        if "Access denied" in msg or "Errno 13" in msg:
            return False, (
                f"{msg} — macOS often blocks libusb on candleLight (gs_usb). "
                "Try: quit UTM, unplug/replug, run from Terminal.app; "
                "if still fails use Linux (QEMU UTM VM USB passthrough) — see MAC-ROBOT.md"
            )
        return False, msg


def connect_piper_interface(piper_cls: Type[Any]) -> Any:
    """
    Construct a connected C_PiperInterface (or V2) for the current platform.

    Caller should call EnableArm after this returns (robot.py does).
    """
    profile = resolve_can_profile()
    bitrate = config.CAN_BITRATE

    if not profile.use_create_can_bus:
        piper = piper_cls(
            profile.channel,
            judge_flag=profile.judge_flag,
            can_auto_init=True,
        )
        return piper

    piper = piper_cls(can_auto_init=False)
    piper.CreateCanBus(
        can_name=profile.channel,
        bustype=profile.bustype,
        expected_bitrate=bitrate,
        judge_flag=profile.judge_flag,
    )
    return piper


def can_probe_available() -> bool:
    """Whether this OS has a probe we can run (ip link or gs_usb)."""
    if is_linux():
        return True
    if is_darwin():
        return True
    return False


def print_mac_setup_hint() -> None:
    print("  Mac: see projects/lightsaber/MAC-ROBOT.md")
    print("       brew install libusb && pip install \"python-can[gs-usb]\"")
    print("       python robot_discover.py   # on Mac host, adapter plugged into Mac")
