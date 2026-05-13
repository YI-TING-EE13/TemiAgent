import unittest

from hermes_temi_bridge.image_resolver import to_hermes_path


class PathTranslationTests(unittest.TestCase):
    def test_bridge_path_translates_to_hermes_path(self):
        self.assertEqual(
            to_hermes_path(
                "/var/lib/temi_shared/events/temi-01/evt_001/frame_t.jpg",
                "/var/lib/temi_shared",
                "/shared/temi",
            ),
            "/shared/temi/events/temi-01/evt_001/frame_t.jpg",
        )

    def test_path_outside_shared_root_fails(self):
        with self.assertRaises(ValueError):
            to_hermes_path("/tmp/frame_t.jpg", "/var/lib/temi_shared", "/shared/temi")


if __name__ == "__main__":
    unittest.main()
