"""Vision team tests — run: python -m unittest discover -s tests -p 'test_vision.py'"""

import time
import unittest

import config
from vision import AttackVision, _FAKE_SEQUENCE


class TestVision(unittest.TestCase):
    def test_fake_attack_cycles_valid_directions(self):
        old_fake = config.USE_FAKE_ATTACKS
        old_sec = config.FAKE_ATTACK_CYCLE_SEC
        config.USE_FAKE_ATTACKS = True
        config.FAKE_ATTACK_CYCLE_SEC = 0.01
        try:
            v = AttackVision()
            seen: set[str] = set()
            for _ in range(30):
                seen.add(v.detect_attack(None))
                time.sleep(0.02)
            v.close()
            self.assertIn("left", seen)
            self.assertIn("right", seen)
            self.assertIn("high", seen)
            self.assertIn("none", seen)
        finally:
            config.USE_FAKE_ATTACKS = old_fake
            config.FAKE_ATTACK_CYCLE_SEC = old_sec

    def test_none_frame_returns_none(self):
        old = config.USE_FAKE_ATTACKS
        config.USE_FAKE_ATTACKS = False
        try:
            v = AttackVision()
            self.assertEqual(v.detect_attack(None), "none")
            v.close()
        finally:
            config.USE_FAKE_ATTACKS = old


if __name__ == "__main__":
    unittest.main()
