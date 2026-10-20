import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("configure_iterm2", REPO / "scripts/configure_iterm2.py")
iterm2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iterm2)


class ITermProfileTests(unittest.TestCase):
    def preferences(self):
        return {
            "Default Bookmark Guid": "original-profile",
            "New Bookmarks": [{
                "Guid": "original-profile",
                "Name": "My Appearance",
                "Keyboard Map": {
                    "0x61-0x100000": {"Action": 11, "Text": "0x01"},
                    "0xd-0x20000": {"Action": 11, "Text": "0x0d"},
                },
            }],
        }

    def test_profile_keeps_parent_and_other_bindings(self):
        profile = iterm2.build_profile(self.preferences())
        self.assertEqual(profile["Dynamic Profile Parent GUID"], "original-profile")
        self.assertTrue(profile["Mouse Reporting"])
        self.assertEqual(profile["Keyboard Map"]["0xd-0x20000"]["Text"], "0x0a")
        self.assertEqual(profile["Keyboard Map"]["0x61-0x100000"]["Text"], "0x01")

    def test_repeat_install_does_not_inherit_from_itself(self):
        preferences = self.preferences()
        previous = iterm2.build_profile(preferences)
        previous["Normal Font"] = "My font"
        preferences["Default Bookmark Guid"] = previous["Guid"]
        profile = iterm2.build_profile(preferences, previous)
        self.assertEqual(profile["Dynamic Profile Parent GUID"], "original-profile")
        self.assertEqual(profile["Normal Font"], "My font")

    def test_replacement_backup_is_outside_watched_directory(self):
        with tempfile.TemporaryDirectory(prefix="iterm-profile-check-") as raw:
            root = Path(raw)
            path = root / "DynamicProfiles/editing.json"
            backups = root / "ProfileBackups"
            profile = iterm2.build_profile(self.preferences())
            iterm2.save_profile(path, profile, backups)
            initial = path.read_bytes()
            iterm2.save_profile(path, profile, backups)
            self.assertFalse(backups.exists())
            profile["Keyboard Map"]["0xd-0x20000"]["Text"] = "0x0b"
            iterm2.save_profile(path, profile, backups)
            saved = list(backups.iterdir())
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_bytes(), initial)
            self.assertEqual(list(path.parent.iterdir()), [path])
            self.assertEqual(json.loads(path.read_text())["Profiles"][0], profile)


if __name__ == "__main__":
    unittest.main()
