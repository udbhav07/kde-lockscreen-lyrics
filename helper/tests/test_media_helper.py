"""Tests for helper/lockscreen-media-helper. Run: python3 -m unittest discover helper/tests"""

import importlib.machinery
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

HELPER = Path(__file__).resolve().parents[1] / "lockscreen-media-helper"
loader = importlib.machinery.SourceFileLoader("media_helper", str(HELPER))
spec = importlib.util.spec_from_loader("media_helper", loader)
mh = importlib.util.module_from_spec(spec)
loader.exec_module(mh)


def player(name, status="Playing", title="Song", artist="Artist", length=200_000_000, url="", pid=""):
    return {"name": name, "status": status, "trackid": "", "art": "", "artist": artist,
            "title": title, "length": length, "url": url, "kde_pid": pid}


class PickPlayer(unittest.TestCase):
    def test_playing_beats_paused_spotify(self):
        players = [player("spotify", "Paused"), player("brave.instance5", "Playing")]
        self.assertEqual(mh.pick(players, {})["name"], "brave.instance5")

    def test_spotify_wins_tie(self):
        players = [player("brave.instance5"), player("spotify")]
        self.assertEqual(mh.pick(players, {})["name"], "spotify")

    def test_most_recent_wins_remaining_tie(self):
        players = [player("vlc", "Paused"), player("elisa", "Paused")]
        self.assertEqual(mh.pick(players, {"vlc": 1, "elisa": 2})["name"], "elisa")

    def test_no_title_is_ignored(self):
        self.assertIsNone(mh.pick([player("chromium.instance1", title="")], {}))

    def test_nothing(self):
        self.assertIsNone(mh.pick([], {}))


class Dedupe(unittest.TestCase):
    def test_native_player_hidden_by_plasma_integration(self):
        players = [player("brave.instance42"), player("plasma-browser-integration", pid="42"),
                   player("chromium.instance7")]
        names = [p["name"] for p in mh.dedupe(players)]
        self.assertEqual(names, ["plasma-browser-integration", "chromium.instance7"])

    def test_firefox_instance_names(self):
        players = [player("firefox.instance_1_23"), player("plasma-browser-integration", pid="23")]
        self.assertEqual([p["name"] for p in mh.dedupe(players)], ["plasma-browser-integration"])


class ParseSnapshot(unittest.TestCase):
    def test_fields_and_bad_lines(self):
        sep = mh.SEP
        line = sep.join(["spotify", "Playing", "/com/spotify/track/abc", "https://i/x.jpg",
                         "Ruth B.", "Dandelions", "233000000", "", ""])
        players = mh.parse_snapshot(line + "\nNo player could handle this command\n")
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]["title"], "Dandelions")
        self.assertEqual(players[0]["length"], 233_000_000)

    def test_missing_length(self):
        line = mh.SEP.join(["vlc", "Playing", "", "", "", "Talk", "", "", ""])
        self.assertEqual(mh.parse_snapshot(line)[0]["length"], 0)


class Evict(unittest.TestCase):
    def test_count_and_age(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            now = time.time()
            for i, age_days in enumerate([0, 1, 2, 10]):
                for ext in (".lrc", ".jpg"):
                    f = d / f"s{i}{ext}"
                    f.write_text("x")
                    os.utime(f, (now - age_days * 86400,) * 2)
            mh.evict(d, max_items=2, max_age_days=7)
            self.assertEqual(sorted(f.name for f in d.iterdir()),
                             ["s0.jpg", "s0.lrc", "s1.jpg", "s1.lrc"])

    def test_keep(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            old = d / "old.lrc"
            old.write_text("x")
            os.utime(old, (1, 1))
            (d / "new.lrc").write_text("x")
            mh.evict(d, max_items=1, keep={"old"})
            self.assertEqual(sorted(f.name for f in d.iterdir()), ["old.lrc"])


if __name__ == "__main__":
    unittest.main()
