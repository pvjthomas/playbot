"""Platform CAN profile tests."""

import unittest
from unittest import mock

import config
from can_platform import resolve_can_profile


class TestCanPlatform(unittest.TestCase):
    def tearDown(self):
        config.CAN_BUSTYPE = "auto"
        config.CAN_CHANNEL = "auto"

    def test_auto_linux_socketcan(self):
        config.CAN_BUSTYPE = "auto"
        with mock.patch("can_platform.is_linux", return_value=True), mock.patch(
            "can_platform.is_darwin", return_value=False
        ):
            p = resolve_can_profile()
        self.assertEqual(p.bustype, "socketcan")
        self.assertEqual(p.channel, config.CAN_INTERFACE)
        self.assertFalse(p.use_create_can_bus)

    def test_auto_mac_gs_usb(self):
        config.CAN_BUSTYPE = "auto"
        with mock.patch("can_platform.is_linux", return_value=False), mock.patch(
            "can_platform.is_darwin", return_value=True
        ):
            p = resolve_can_profile()
        self.assertEqual(p.bustype, "gs_usb")
        self.assertEqual(p.channel, "0")
        self.assertTrue(p.use_create_can_bus)
        self.assertFalse(p.judge_flag)

    def test_force_gs_usb_channel(self):
        config.CAN_BUSTYPE = "gs_usb"
        config.CAN_CHANNEL = "1"
        p = resolve_can_profile()
        self.assertEqual(p.channel, "1")
        self.assertEqual(p.bustype, "gs_usb")
