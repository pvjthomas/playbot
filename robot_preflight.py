"""
Read-only PiPER checks before LIVE motion (no EnableArm, no JointCtrl).

Used by robot_smoke.py before --connect / --live.
"""

from __future__ import annotations

import subprocess
import time
from typing import Any

from can_platform import connect_piper_interface, is_linux

import config

_FIRMWARE_QUERY_ID = 0x4AF
_FIRMWARE_FAIL = -0x4AF
_CTRL_MODE_NAMES = {
    0x00: "standby",
    0x01: "CAN",
    0x02: "teach",
}


def _status(label: str, ok: bool, detail: str = "") -> bool:
    tag = "OK" if ok else "FAIL"
    line = f"  [{tag}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def _joints_deg_from_feedback(msg: Any) -> list[float]:
    js = msg.joint_state
    return [getattr(js, f"joint_{i}") / 1000.0 for i in range(1, 7)]


def _open_listen_piper() -> Any:
    from piper_sdk import C_PiperInterface

    piper = connect_piper_interface(C_PiperInterface)
    # Match robot_discover.py — listen only, no PiperInit flood before joint read.
    piper.ConnectPort(piper_init=False)
    return piper


def _firmware_ok(fw: Any) -> bool:
    return not (fw == _FIRMWARE_FAIL or (isinstance(fw, int) and fw < 0))


def _check_can_still_up() -> bool:
    if not is_linux():
        return True
    try:
        out = subprocess.check_output(
            ["ip", "link", "show", config.CAN_INTERFACE], text=True, stderr=subprocess.STDOUT
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _status(f"{config.CAN_INTERFACE} still up", False, "missing after preflight")
    up = "state UP" in out or "<UP," in out or ",UP," in out
    return _status(f"{config.CAN_INTERFACE} still up", up, "UP" if up else "DOWN — re-run can-up.sh / utmctl usb connect")


def _check_firmware(piper: Any) -> bool:
    print("\n[preflight] Firmware version")
    piper.SearchPiperFirmwareVersion()
    deadline = time.monotonic() + 2.0
    fw: Any = _FIRMWARE_FAIL
    while time.monotonic() < deadline:
        time.sleep(0.1)
        fw = piper.GetPiperFirmwareVersion()
        if _firmware_ok(fw):
            break
        piper.SearchPiperFirmwareVersion()
    ok = _firmware_ok(fw)
    if not ok:
        print("  [SKIP] firmware — no reply (optional if status/CAN FPS look good)")
        return True
    return _status("GetPiperFirmwareVersion()", ok, repr(fw))


def _check_can_port(piper: Any) -> bool:
    print("\n[preflight] CAN port (SDK bus handle)")
    name = piper.GetCanName()
    arm_can = piper.GetCanBus()
    if arm_can is None:
        return _status("GetCanBus()", False, "no bus object")

    ok_name = bool(name)
    _status("GetCanName()", ok_name, repr(name))

    bus_state = arm_can.is_can_bus_ok()
    state_label = str(bus_state)
    for attr in dir(arm_can.CAN_STATUS):
        if getattr(arm_can.CAN_STATUS, attr, None) == bus_state:
            state_label = attr
            break
    ok_bus = bus_state == arm_can.CAN_STATUS.BUS_STATE_ACTIVE
    _status("CAN bus state", ok_bus, state_label)

    if is_linux() and hasattr(arm_can, "get_can_ports"):
        ports = arm_can.get_can_ports()
        print(f"       system CAN ports: {ports or '(none)'}")

    return ok_name and ok_bus


def _check_can_send_probe(piper: Any) -> bool:
    """Send firmware-query frame on our CAN port (no joint motion)."""
    print("\n[preflight] CAN transmit (probe frame, not JointCtrl)")
    arm_can = piper.GetCanBus()
    send_st = arm_can.SendCanMessage(
        _FIRMWARE_QUERY_ID,
        [0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    )
    ok = send_st == arm_can.CAN_STATUS.SEND_MESSAGE_SUCCESS
    detail = f"ID=0x{_FIRMWARE_QUERY_ID:03X} status={send_st}"
    return _status("SendCanMessage (probe)", ok, detail)


def _poll_arm_feedback(
    piper: Any, timeout_sec: float = 3.0
) -> tuple[bool, float, Any | None, bool, float, Any | None]:
    """Poll joint + status streams; return best Hz for each."""
    deadline = time.monotonic() + timeout_sec
    best_joint_hz = 0.0
    best_status_hz = 0.0
    last_joint = None
    last_status = None
    while time.monotonic() < deadline:
        last_joint = piper.GetArmJointMsgs()
        j_hz = getattr(last_joint, "Hz", 0.0) or 0.0
        best_joint_hz = max(best_joint_hz, j_hz)

        last_status = piper.GetArmStatus()
        s_hz = getattr(last_status, "Hz", 0.0) or 0.0
        best_status_hz = max(best_status_hz, s_hz)

        if j_hz > 1.0 and s_hz > 1.0:
            break
        time.sleep(0.05)

    joint_ok = best_joint_hz > 0
    status_ok = best_status_hz > 0
    return joint_ok, best_joint_hz, last_joint, status_ok, best_status_hz, last_status


def _check_arm_state(piper: Any) -> bool:
    print("\n[preflight] Arm state (read-only feedback)")
    ok = True

    joint_ok, joint_hz, joint_msg, status_ok, status_hz, status_msg = _poll_arm_feedback(piper)
    can_fps = piper.GetCanFps() or 0.0
    bus_alive = can_fps > 10.0

    if joint_ok and joint_msg is not None:
        degs = [round(d, 1) for d in _joints_deg_from_feedback(joint_msg)]
        ok = _status("joint feedback", True, f"Hz={joint_hz:.1f} deg={degs}") and ok
    elif status_ok and bus_alive:
        ok = _status(
            "joint feedback",
            True,
            f"via status/CAN (joint Hz={joint_hz:.1f}, status Hz={status_hz:.1f}, CAN FPS={can_fps:.0f})",
        ) and ok
    else:
        ok = _status(
            "joint feedback",
            False,
            f"no stream (joint Hz={joint_hz:.1f}, status Hz={status_hz:.1f}, CAN FPS={can_fps:.0f})",
        ) and ok

    arm_status = getattr(status_msg, "arm_status", None)
    if arm_status is not None and status_ok:
        mode = getattr(arm_status, "ctrl_mode", None)
        mode_name = _CTRL_MODE_NAMES.get(mode, f"0x{mode:02x}" if mode is not None else "?")
        ok = _status("control mode", True, f"{mode_name} (Hz={status_hz:.1f})") and ok
    elif joint_ok and bus_alive:
        mode = getattr(arm_status, "ctrl_mode", None) if arm_status else None
        mode_name = _CTRL_MODE_NAMES.get(mode, "?") if mode is not None else "ok (joint stream)"
        ok = _status("control mode", True, f"{mode_name} (status Hz={status_hz:.1f}, joint OK)") and ok
    elif arm_status is not None:
        ok = _status("control mode", False, f"no status stream (Hz={status_hz:.1f})") and ok
    else:
        ok = _status("GetArmStatus()", False, "no status") and ok

    enabled = piper.GetArmEnableStatus()
    if enabled:
        on = sum(1 for e in enabled if e)
        _status("motor enable flags", True, f"{on}/{len(enabled)} enabled (EnableArm not sent yet)")
    else:
        ok = _status("GetArmEnableStatus()", False, "empty") and ok

    if can_fps > 0:
        ok = _status("CAN FPS", True, f"{can_fps:.1f}") and ok
    else:
        ok = _status("CAN FPS", False, "no frames — check USB attach / arm power") and ok

    if not ok:
        print(
            "       hint: if CAN FPS was high then dropped to 0, re-attach USB on Mac "
            "(utmctl usb connect) and can-up.sh"
        )

    return ok


def run_preflight() -> int:
    """
    Connect listen-only, verify CAN port + probe send + firmware + state.
    Does not enable motors or send JointCtrl.
    """
    print("PiPER preflight (read-only, before LIVE motion)")
    piper = None
    try:
        piper = _open_listen_piper()
    except Exception as exc:
        print(f"  [FAIL] SDK connect — {exc}")
        return 1

    all_ok = True
    try:
        all_ok = _check_can_port(piper) and all_ok
        all_ok = _check_can_send_probe(piper) and all_ok
        # Arm feedback before slow firmware polling (matches robot_discover timing).
        all_ok = _check_arm_state(piper) and all_ok
        _check_firmware(piper)
        all_ok = _check_can_still_up() and all_ok
    finally:
        try:
            piper.DisconnectPort()
        except Exception:
            pass

    print()
    if all_ok:
        print("PREFLIGHT PASS — safe to try --connect or --live")
        return 0
    print("PREFLIGHT FAIL — fix CAN/arm before LIVE motion")
    return 1
