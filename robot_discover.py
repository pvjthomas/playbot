#!/usr/bin/env python3
"""
Step 1 — verify PiPER hardware path (no arm motion).

Linux: USB-CAN adapter → SocketCAN (can0) → CAN traffic → PiPER feedback.
macOS: candleLight on host → python-can gs_usb → PiPER feedback (see MAC-ROBOT.md).

  python robot_discover.py

Does NOT enable motors or send JointCtrl.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time

import config
from can_platform import (
    is_darwin,
    is_linux,
    mac_candlelight_visible,
    print_mac_setup_hint,
    probe_gs_usb_open,
    resolve_can_profile,
)

# Common gs_usb / USB-CAN IDs (candleLight, CANable, Geschwister Schneider, etc.)
_KNOWN_CAN_USB = frozenset(
    {
        "1d50:606f",
        "1209:2323",
        "1209:ca01",
        "1cd2:606f",
        "16d0:0f30",
        "16d0:10b8",
        "0c72:000c",  # PEAK PCAN-USB
        "04d8:0053",  # Microchip USB-CAN
    }
)

# UTM virtual devices — not the robot
_UTM_USB_IGNORE = frozenset(
    {
        "05ac:8105",
        "05ac:8106",
        "05ac:1503",
    }
)


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return 0, out
    except subprocess.CalledProcessError as exc:
        return exc.returncode, exc.output or ""
    except FileNotFoundError:
        return 127, ""


def _status(label: str, ok: bool | None, detail: str = "") -> bool:
    """ok=None → SKIP. Returns False only on hard FAIL."""
    if ok is None:
        tag = "SKIP"
    elif ok:
        tag = "OK"
    else:
        tag = "FAIL"
    line = f"  [{tag}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok is not False


def _parse_lsusb_ids(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        m = re.match(r"Bus \d+ Device \d+: ID ([0-9a-f]{4}):([0-9a-f]{4})\s*(.*)", line, re.I)
        if m:
            vid, pid, desc = m.group(1).lower(), m.group(2).lower(), m.group(3).strip()
            rows.append((f"{vid}:{pid}", desc, line.strip()))
    return rows


def check_usb_linux() -> bool:
    print("\n[1/4] USB devices (lsusb)")
    code, out = _run(["lsusb"])
    if code == 127:
        return _status("lsusb", False, "install usbutils: sudo apt install usbutils")

    rows = _parse_lsusb_ids(out)
    if not rows:
        return _status("USB list", False, "no devices")

    can_like: list[str] = []
    other: list[str] = []
    for key, _desc, full in rows:
        if key in _UTM_USB_IGNORE:
            continue
        if key in _KNOWN_CAN_USB:
            can_like.append(full)
        elif "can" in full.lower() or "gs_usb" in full.lower() or "candle" in full.lower():
            can_like.append(full)
        else:
            other.append(full)

    for line in can_like:
        print(f"       {line}")
    for line in other[:8]:
        print(f"       {line}")
    if len(other) > 8:
        print(f"       ... and {len(other) - 8} more")

    if can_like:
        return _status("USB-CAN adapter", True, f"{len(can_like)} candidate(s)")

    only_utm_virtual = all(
        key in _UTM_USB_IGNORE or key.startswith("1d6b:")
        for key, _, _ in rows
    )
    extra = ""
    if only_utm_virtual:
        extra = (
            " (only UTM virtual USB — Apple Virtualization cannot pass host USB; "
            "use QEMU VM + USB sharing, or run robot on Mac — "
            "projects/ubuntu_shared/USB-PASSTHROUGH.md, projects/lightsaber/MAC-ROBOT.md)"
        )
    return _status(
        "USB-CAN adapter",
        False,
        "none found — plug adapter into Mac host OR pass USB to VM" + extra,
    )


def check_usb_mac() -> bool:
    print("\n[1/4] USB (macOS system_profiler)")
    visible = mac_candlelight_visible()
    if visible:
        return _status("candleLight USB", True, "seen on Mac USB bus")
    return _status(
        "candleLight USB",
        False,
        "not found — plug candleLight into Mac (not only into VM)",
    )


def check_can_interface_linux() -> bool:
    print(f"\n[2/4] SocketCAN interface ({config.CAN_INTERFACE})")
    iface = config.CAN_INTERFACE
    code, out = _run(["ip", "-details", "link", "show", iface])
    if code != 0:
        _, mod = _run(["lsmod"])
        gs = "gs_usb" in mod
        hint = "pass USB-CAN to VM in UTM, or use MAC-ROBOT.md on Mac host"
        if not gs:
            hint += "; kernel module gs_usb not loaded (plug adapter in)"
        return _status(iface, False, f"missing — {hint}")

    up = "state UP" in out or "<UP," in out or ",UP," in out
    bitrate_m = re.search(r"bitrate (\d+)", out)
    bitrate = bitrate_m.group(1) if bitrate_m else "?"
    print(f"       {out.splitlines()[0] if out else iface}")
    if not up:
        return _status(
            iface,
            False,
            "exists but DOWN — run: bash projects/ubuntu_shared/can-up.sh",
        )
    return _status(iface, True, f"UP, bitrate {bitrate}")


def check_can_interface_mac() -> bool:
    profile = resolve_can_profile()
    print(f"\n[2/4] python-can ({profile.label})")
    ok, detail = probe_gs_usb_open(profile.channel, config.CAN_BITRATE)
    if ok:
        return _status("gs_usb bus", True, detail)
    return _status("gs_usb bus", False, detail)


def check_can_traffic_linux(timeout_sec: float = 2.0) -> bool:
    print(f"\n[3/4] CAN bus traffic ({timeout_sec}s candump, read-only)")
    if subprocess.call(["which", "candump"], stdout=subprocess.DEVNULL) != 0:
        return _status("candump", None, "can-utils not installed (sudo apt install can-utils)")

    iface = config.CAN_INTERFACE
    try:
        proc = subprocess.run(
            ["timeout", str(timeout_sec), "candump", iface],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 1,
        )
        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        lines = []

    if lines:
        print(f"       saw {len(lines)} frame(s); first: {lines[0][:80]}")
        return _status("CAN frames", True, "bus is active")

    return _status(
        "CAN frames",
        False,
        "no frames — arm powered? CAN wiring? bitrate 1000000?",
    )


def check_can_traffic_mac() -> bool:
    print("\n[3/4] CAN traffic (macOS)")
    return _status(
        "candump",
        None,
        "skipped on macOS — use PiPER feedback step; optional: pip install cantools",
    )


def check_piper_feedback() -> bool:
    print("\n[4/4] PiPER feedback (piper_sdk listen, no EnableArm / no motion)")
    try:
        from piper_sdk import C_PiperInterface
    except ImportError as exc:
        return _status("piper_sdk", False, str(exc))

    profile = resolve_can_profile()
    try:
        if profile.use_create_can_bus:
            piper = C_PiperInterface(can_auto_init=False)
            piper.CreateCanBus(
                can_name=profile.channel,
                bustype=profile.bustype,
                expected_bitrate=config.CAN_BITRATE,
                judge_flag=profile.judge_flag,
            )
        else:
            piper = C_PiperInterface(
                profile.channel,
                judge_flag=profile.judge_flag,
                can_auto_init=True,
            )
        piper.ConnectPort(piper_init=False)
    except Exception as exc:
        return _status("SDK connect", False, str(exc))

    try:
        deadline = time.monotonic() + 3.0
        best_hz = 0.0
        last = None
        while time.monotonic() < deadline:
            msg = piper.GetArmJointMsgs()
            last = msg
            hz = getattr(msg, "Hz", 0.0) or 0.0
            best_hz = max(best_hz, hz)
            if hz > 1.0:
                js = msg.joint_state
                degs = [
                    js.joint_1 / 1000.0,
                    js.joint_2 / 1000.0,
                    js.joint_3 / 1000.0,
                    js.joint_4 / 1000.0,
                    js.joint_5 / 1000.0,
                    js.joint_6 / 1000.0,
                ]
                detail = f"Hz={hz:.1f} joints(deg)={[round(d, 1) for d in degs]}"
                return _status("PiPER on bus", True, detail)
            time.sleep(0.1)

        if last is not None and best_hz > 0:
            return _status("PiPER on bus", True, f"weak feed Hz={best_hz:.2f}")
        return _status(
            "PiPER on bus",
            False,
            "no joint feedback — check arm power, teach pendant off, CAN H/L",
        )
    finally:
        try:
            piper.DisconnectPort()
        except Exception:
            pass


def main() -> int:
    profile = resolve_can_profile()
    print("PiPER device discovery (read-only, no motion)")
    print(f"  platform={sys.platform}  profile={profile.label}  bitrate={config.CAN_BITRATE}")

    ok = True

    if is_linux():
        usb_ok = check_usb_linux()
        ok = ok and usb_ok
        if not usb_ok:
            _status("SocketCAN", None, "skipped — fix USB first")
            _status("CAN traffic", None, "skipped")
            _status("PiPER feedback", None, "skipped")
        else:
            can_ok = check_can_interface_linux()
            ok = ok and can_ok
            if not can_ok:
                _status("CAN traffic", None, "skipped — bring can0 up")
                _status("PiPER feedback", None, "skipped")
            else:
                ok = ok and check_can_traffic_linux()
                ok = ok and check_piper_feedback()
    elif is_darwin():
        usb_ok = check_usb_mac()
        ok = ok and usb_ok
        if not usb_ok:
            _status("gs_usb", None, "skipped — plug adapter into Mac")
            _status("PiPER feedback", None, "skipped")
        else:
            can_ok = check_can_interface_mac()
            ok = ok and can_ok
            if not can_ok:
                print()
                print_mac_setup_hint()
                _status("PiPER feedback", None, "skipped — fix gs_usb first")
            else:
                check_can_traffic_mac()
                ok = ok and check_piper_feedback()
    else:
        print(f"\n  Unsupported platform {sys.platform} — use Linux or macOS")
        return 1

    print()
    if ok:
        print("PASS — robot path looks good. Next: python robot_smoke.py --connect")
        return 0

    print("NOT READY — see fix hints above.")
    if is_linux():
        print("  Linux VM: UTM USB → candleLight → can-up.sh → robot_discover.py")
        print("  Or Mac:   plug adapter into Mac → MAC-ROBOT.md → robot_discover.py")
    else:
        print_mac_setup_hint()
    return 1


if __name__ == "__main__":
    sys.exit(main())
