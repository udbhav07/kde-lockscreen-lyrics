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

    def test_spotify_instance_name(self):
        players = [player("brave.instance5"), player("spotify.instance9")]
        self.assertEqual(mh.pick(players, {})["name"], "spotify.instance9")

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

    def test_quoted_trackid(self):
        line = mh.SEP.join(["brave.instance1", "Paused", "'/com/brave/Track1'", "", "", "T", "1", "", ""])
        self.assertEqual(mh.parse_snapshot(line)[0]["trackid"], "/com/brave/Track1")

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


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.w = mh.Writer(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def now(self):
        return (self.dir / "now.txt").read_text().rstrip("\n").split("\t")

    def test_switch_clears_files_and_writes_now(self):
        (self.dir / "cover.jpg").write_text("old")
        (self.dir / "lyrics.lrc").write_text("old")
        self.w.switch(player("spotify", title="Dandelions", artist="Ruth B."))
        self.assertFalse((self.dir / "cover.jpg").exists())
        self.assertFalse((self.dir / "lyrics.lrc").exists())
        self.assertEqual(self.now(), ["spotify", "Dandelions", "", "", ""])

    def test_stale_worker_cannot_write(self):
        old = self.w.switch(player("spotify", title="A"))
        new = self.w.switch(player("vlc", title="B"))
        self.assertFalse(self.w.put(old, "lyrics.lrc", b"[00:01.00]A"))
        self.assertTrue(self.w.put(new, "lyrics.lrc", b"[00:01.00]B"))
        self.assertEqual((self.dir / "lyrics.lrc").read_text(), "[00:01.00]B")

    def test_worker_finishing_first_is_cleared_by_switch(self):
        gen = self.w.switch(player("spotify", title="A"))
        self.w.put(gen, "cover.jpg", b"A")
        self.w.switch(player("vlc", title="B"))
        self.assertFalse((self.dir / "cover.jpg").exists())

    def test_note_updates_fields_only_for_current_song(self):
        gen = self.w.switch(player("brave.instance1", title="Ed Sheeran - Shape of You (Lyrics)"))
        self.w.note(gen, artist="Ed Sheeran", source="lrclib", expected_ms=233000)
        self.w.note(gen - 1, artist="stale")
        self.assertEqual(self.now()[2:], ["Ed Sheeran", "lrclib", "233000"])

    def test_tabs_in_title_cannot_break_the_file(self):
        self.w.switch(player("vlc", title="a\tb\nc"))
        self.assertEqual(self.now(), ["vlc", "a b c", "", "", ""])

    def test_nothing_playing_removes_everything(self):
        gen = self.w.switch(player("spotify"))
        self.w.put(gen, "cover.jpg", b"x")
        self.w.switch(None)
        self.assertEqual(list(self.dir.iterdir()), [])


class Lrclib(unittest.TestCase):
    RESULTS = [
        {"duration": 260, "syncedLyrics": "[00:01.00]long"},
        {"duration": 234, "syncedLyrics": None},
        {"duration": 233.5, "syncedLyrics": "[00:01.00]match"},
    ]

    def test_prefers_duration_match(self):
        self.assertEqual(mh.choose_synced(self.RESULTS, 232), ("[00:01.00]match", 233.5))

    def test_falls_back_to_first_synced(self):
        self.assertEqual(mh.choose_synced(self.RESULTS, 100), ("[00:01.00]long", 260))

    def test_unknown_length(self):
        self.assertEqual(mh.choose_synced(self.RESULTS, None), ("[00:01.00]long", 260))

    def test_none_synced(self):
        self.assertEqual(mh.choose_synced([{"duration": 1, "syncedLyrics": ""}], 1), ("", None))

    def test_clean_title(self):
        self.assertEqual(mh.clean_title("Calm Down (feat. Selena Gomez)"), "Calm Down")
        self.assertEqual(mh.clean_title("Nee Kallalona (From \"Movie\") - Remix"), "Nee Kallalona")


class ArtFile(unittest.TestCase):
    def test_reads_small_regular_file_under_tmp(self):
        with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".png") as f:
            f.write(b"PNG")
            f.flush()
            self.assertEqual(mh.read_art_file("file://" + f.name), b"PNG")

    def test_refuses_other_places_and_oversize(self):
        self.assertIsNone(mh.read_art_file("file:///etc/passwd"))
        self.assertIsNone(mh.read_art_file("file:///tmp"))
        with tempfile.NamedTemporaryFile(dir="/tmp") as f:
            f.truncate(mh.MAX_ART + 1)
            self.assertIsNone(mh.read_art_file("file://" + f.name))

    def test_url_encoded_path(self):
        with tempfile.NamedTemporaryFile(dir="/tmp", prefix="a b") as f:
            f.write(b"x")
            f.flush()
            self.assertEqual(mh.read_art_file("file://" + f.name.replace(" ", "%20")), b"x")


if __name__ == "__main__":
    unittest.main()
