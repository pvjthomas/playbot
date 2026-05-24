"""
Read-only PiPER checks before LIVE motion (no EnableArm, no JointCtrl).

Used by robot_smoke.py before --connect / --live.
"""

from __future__ import annotations

import time
from typing import Any

from can_platform import connect_piper_interface, is_linux

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
    piper.ConnectPort(piper_init=False)
    return piper


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


def _check_firmware(piper: Any) -> bool:
    print("\n[preflight] Firmware version")
    piper.SearchPiperFirmwareVersion()
    time.sleep(0.08)
    fw = piper.GetPiperFirmwareVersion()
    if fw == _FIRMWARE_FAIL or (isinstance(fw, int) and fw < 0):
        piper.SearchPiperFirmwareVersion()
        time.sleep(0.08)
        fw = piper.GetPiperFirmwareVersion()
    ok = not (fw == _FIRMWARE_FAIL or (isinstance(fw, int) and fw < 0))
    return _status("GetPiperFirmwareVersion()", ok, repr(fw))


def _check_arm_state(piper: Any) -> bool:
    print("\n[preflight] Arm state (read-only feedback)")
    ok = True

    deadline = time.monotonic() + 2.0
    joint_msg = None
    best_hz = 0.0
    while time.monotonic() < deadline:
        joint_msg = piper.GetArmJointMsgs()
        hz = getattr(joint_msg, "Hz", 0.0) or 0.0
        best_hz = max(best_hz, hz)
        if hz > 1.0:
            break
        time.sleep(0.05)

    if joint_msg is not None and best_hz > 0:
        degs = [round(d, 1) for d in _joints_deg_from_feedback(joint_msg)]
        ok = _status("joint feedback", True, f"Hz={best_hz:.1f} deg={degs}") and ok
    else:
        ok = _status("joint feedback", False, "no joint stream") and ok

    status_msg = piper.GetArmStatus()
    arm_status = getattr(status_msg, "arm_status", None)
    if arm_status is not None:
        mode = getattr(arm_status, "ctrl_mode", None)
        mode_name = _CTRL_MODE_NAMES.get(mode, f"0x{mode:02x}" if mode is not None else "?")
        ok = _status("control mode", mode is not None, mode_name) and ok
    else:
        ok = _status("GetArmStatus()", False, "no status") and ok

    enabled = piper.GetArmEnableStatus()
    if enabled:
        on = sum(1 for e in enabled if e)
        ok = _status("motor enable flags", True, f"{on}/{len(enabled)} enabled") and ok
    else:
        ok = _status("GetArmEnableStatus()", False, "empty") and ok

    fps = piper.GetCanFps()
    if fps is not None and fps > 0:
        ok = _status("CAN FPS", True, f"{fps:.1f}") and ok
    else:
        print("  [SKIP] CAN FPS — not available yet")

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
        all_ok = _check_firmware(piper) and all_ok
        all_ok = _check_arm_state(piper) and all_ok
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
