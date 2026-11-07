"""Tests for helper/lockscreen-media-helper. Run: python3 -m unittest discover helper/tests"""

import importlib.machinery
import importlib.util
import json
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

    def test_last_used_wins_when_all_paused(self):
        players = [player("spotify", "Paused"), player("brave.instance5", "Paused")]
        self.assertEqual(mh.pick(players, {"spotify": 1, "brave.instance5": 2})["name"], "brave.instance5")

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


class YoutubeTitles(unittest.TestCase):
    CASES = [
        ("Ed Sheeran - Shape of You (Lyrics)", "7clouds", ("Ed Sheeran", "Shape of You")),
        ("Ed Sheeran - Shape of You [Official Video]", "Ed Sheeran", ("Ed Sheeran", "Shape of You")),
        ("Shape of You", "Ed Sheeran - Topic", ("Ed Sheeran", "Shape of You")),
        ("Calm Down", "RemaVEVO", ("Rema", "Calm Down")),
        ("Rema, Selena Gomez - Calm Down (Official Music Video)", "Rema", ("Rema, Selena Gomez", "Calm Down")),
        ("DJ Snake - Taki Taki ft. Selena Gomez, Ozuna, Cardi B (Official Video)", "DJ Snake",
         ("DJ Snake", "Taki Taki")),
        ("Shawn Mendes – Señorita (Official Audio) #shorts", "x", ("Shawn Mendes", "Señorita")),
        ("Dandelions | Ruth B. | Lyric Video", "Ruth B.", ("Ruth B.", "Dandelions")),
        ("Ruth B. - Dandelions (Visualizer) HD", "Ruth B.", ("Ruth B.", "Dandelions")),
    ]

    def test_cases(self):
        for title, channel, expected in self.CASES:
            with self.subTest(title=title):
                self.assertEqual(mh.youtube_song(title, channel), expected)


class VideoId(unittest.TestCase):
    def test_urls(self):
        good = ["https://www.youtube.com/watch?v=JGwWNGJdvx8",
                "https://www.youtube.com/watch?list=PL1&v=JGwWNGJdvx8&t=3",
                "https://youtu.be/JGwWNGJdvx8?si=x",
                "https://m.youtube.com/shorts/JGwWNGJdvx8",
                "https://music.youtube.com/watch?v=JGwWNGJdvx8"]
        for url in good:
            with self.subTest(url=url):
                self.assertEqual(mh.video_id(url), "JGwWNGJdvx8")

    def test_not_youtube(self):
        for url in ["", "https://vimeo.com/123", "https://www.youtube.com/watch?v=short",
                    "https://evil.example/youtube.com/watch?v=JGwWNGJdvx8"]:
            with self.subTest(url=url):
                self.assertIsNone(mh.video_id(url))


class Captions(unittest.TestCase):
    def ev(self, start, dur, text, **extra):
        return {"tStartMs": start, "dDurationMs": dur, "segs": [{"utf8": text}], **extra}

    def test_lines_dedupe_and_noise(self):
        data = {"events": [
            {"tStartMs": 0, "dDurationMs": 100},                       # no segs
            self.ev(1000, 2000, "♪ Maybe it's the way ♪"),
            self.ev(3000, 10, "\n", aAppend=1),                        # ASR line break
            self.ev(3000, 1500, "Maybe it's the way"),                 # rolling duplicate
            self.ev(4500, 1000, "[Music]"),
            self.ev(5500, 1000, "you say\nmy name"),
        ]}
        self.assertEqual(mh.json3_to_lrc(data),
                         "[00:01.00]Maybe it's the way\n[00:05.50]you say my name")

    def test_long_break_gets_empty_line(self):
        data = {"events": [self.ev(1000, 2000, "one"), self.ev(9000, 1000, "two"),
                           self.ev(10500, 500, "three")]}
        self.assertEqual(mh.json3_to_lrc(data),
                         "[00:01.00]one\n[00:03.00]\n[00:09.00]two\n[00:10.50]three")

    def test_minutes(self):
        self.assertEqual(mh.json3_to_lrc({"events": [self.ev(125_250, 1, "x")]}), "[02:05.25]x")

    def test_empty(self):
        self.assertEqual(mh.json3_to_lrc({"events": []}), "")
        self.assertEqual(mh.json3_to_lrc({}), "")


class Offset(unittest.TestCase):
    def test_shift(self):
        self.assertEqual(mh.shift_lrc("[00:01.50]a\n[01:59.00]b\nnot a line", 2.5),
                         "[00:04.00]a\n[02:01.50]b\nnot a line")

    def test_guard(self):
        for video, track, expected in [(200, 198, 0), (200, 197, 3), (230, 200, 30),
                                       (231, 200, 0), (190, 200, 0), (200, None, 0)]:
            with self.subTest(video=video, track=track):
                self.assertEqual(mh.intro_offset(video, track), expected)


class AdGuard(unittest.TestCase):
    def test_ad_playing(self):
        self.assertTrue(mh.ad_playing(15_000_000, 232_000))
        self.assertFalse(mh.ad_playing(233_500_000, 232_000))
        self.assertFalse(mh.ad_playing(15_000_000, 0))       # unknown -> not an ad


class Search(unittest.TestCase):
    ENTRIES = [
        {"id": "AAAAAAAAAAA", "title": "Ed Sheeran - Shape of You (Lyrics)", "channel": "7clouds Pop", "duration": 265},
        {"id": "BBBBBBBBBBB", "title": "Ed Sheeran -  Shape of You (Lyrics)", "channel": "7clouds", "duration": 233},
        {"id": "CCCCCCCCCCC", "title": "Ed Sheeran - Shape of You (Lyrics)", "channel": "7clouds", "duration": 300},
    ]

    def test_channel_title_and_duration_must_match(self):
        self.assertEqual(mh.match_search(self.ENTRIES, "Ed Sheeran - Shape of You (Lyrics)", "7clouds", 231.4),
                         ("BBBBBBBBBBB", 233000))

    def test_no_match(self):
        self.assertIsNone(mh.match_search(self.ENTRIES, "Ed Sheeran - Shape of You (Lyrics)", "7clouds", 15))
        self.assertIsNone(mh.match_search([{"id": None}], "x", "y", 1))


class CaptionTrack(unittest.TestCase):
    INFO = {
        "subtitles": {"live_chat": [{"ext": "json", "url": "chat"}],
                      "hi": [{"ext": "vtt", "url": "hi.vtt"}, {"ext": "json3", "url": "hi.json3"}],
                      "en-US": [{"ext": "json3", "url": "en.json3"}]},
        "automatic_captions": {"fr": [{"ext": "json3", "url": "fr"}],
                               "en-orig": [{"ext": "json3", "url": "asr.json3"}]},
    }

    def test_manual_prefers_english(self):
        self.assertEqual(mh.caption_url(self.INFO, "manual"), "en.json3")

    def test_auto_uses_original_language(self):
        self.assertEqual(mh.caption_url(self.INFO, "auto"), "asr.json3")

    def test_none(self):
        self.assertIsNone(mh.caption_url({"subtitles": {"live_chat": []}}, "manual"))
        self.assertIsNone(mh.caption_url({}, "auto"))


class Remember(unittest.TestCase):
    def test_round_trip_and_expiry(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "ids.tsv"
            f.write_text("old\tXXXXXXXXXXX\t1000\t1\n")
            mh.remember(f, "k", "JGwWNGJdvx8", 233000)
            self.assertEqual(mh.recall(f, "k"), ("JGwWNGJdvx8", 233000))
            self.assertIsNone(mh.recall(f, "old"))
            self.assertNotIn("old", f.read_text())


class BrowserSong(unittest.TestCase):
    """The YouTube handler with network and yt-dlp replaced by fakes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = {k: getattr(mh, k) for k in ("CACHE", "MUSIC", "YT", "THUMBS", "CAPTIONS", "IDS",
                                                  "http", "ytdlp", "lrclib")}
        mh.CACHE, mh.MUSIC, mh.YT = root, root / "youtube-music", root / "youtube"
        mh.THUMBS, mh.CAPTIONS, mh.IDS = mh.YT / "thumbs", mh.YT / "captions", mh.YT / "ids.tsv"
        for folder in (mh.MUSIC, mh.THUMBS, mh.CAPTIONS):
            folder.mkdir(parents=True)
        self.calls = []
        self.info = {"duration": 233, "subtitles": {}, "automatic_captions": {}}
        self.lrclib_answer = ("[00:01.00]from lrclib", 233)
        mh.ytdlp = self.fake_ytdlp
        mh.http = self.fake_http
        mh.lrclib = lambda artist, track, length_s, wait: (self.calls.append(("lrclib", artist, track))
                                                           or self.lrclib_answer)
        self.w = mh.Writer(root)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(mh, k, v)
        self.tmp.cleanup()

    def fake_ytdlp(self, args, alive):
        self.calls.append(("ytdlp", args[-1]))
        return json.dumps(self.info)

    def fake_http(self, url):
        self.calls.append(("http", url))
        if url.endswith("maxresdefault.jpg"):
            raise mh.HttpError(404)
        if url.endswith(".json3"):
            return json.dumps({"events": [{"tStartMs": 1000, "dDurationMs": 1, "segs": [{"utf8": "caption"}]}]}).encode()
        return b"JPEG"

    def play(self, length=233_000_000, url="https://www.youtube.com/watch?v=JGwWNGJdvx8"):
        p = player("plasma-browser-integration", title="Ed Sheeran - Shape of You (Official Video)",
                   artist="Ed Sheeran", length=length, url=url)
        gen = self.w.switch(p)
        mh.browser_song(self.w, p, gen, lambda s: True)
        return (self.w.folder / "now.txt").read_text().rstrip("\n").split("\t")

    def lyrics(self):
        f = self.w.folder / "lyrics.lrc"
        return f.read_text() if f.exists() else ""

    def test_manual_captions_win(self):
        self.info["subtitles"] = {"en": [{"ext": "json3", "url": "https://c/en.json3"}]}
        now = self.play()
        self.assertEqual(self.lyrics(), "[00:01.00]caption")
        self.assertEqual(now[2:], ["Ed Sheeran", "captions", "233000"])
        self.assertEqual((self.w.folder / "cover.jpg").read_bytes(), b"JPEG")
        self.assertIn(("http", "https://i.ytimg.com/vi/JGwWNGJdvx8/mqdefault.jpg"), self.calls)

    def test_lrclib_before_auto_captions(self):
        self.info["automatic_captions"] = {"en-orig": [{"ext": "json3", "url": "https://c/a.json3"}]}
        now = self.play()
        self.assertEqual(self.lyrics(), "[00:01.00]from lrclib")
        self.assertEqual(now[3], "lrclib")
        self.assertIn(("lrclib", "Ed Sheeran", "Shape of You"), self.calls)

    def test_auto_captions_last(self):
        self.info["automatic_captions"] = {"en-orig": [{"ext": "json3", "url": "https://c/a.json3"}]}
        self.lrclib_answer = ("", None)
        self.assertEqual(self.play()[3], "auto-captions")

    def test_intro_offset_applied_to_lrclib(self):
        self.lrclib_answer = ("[00:01.00]from lrclib", 220)
        self.play()
        self.assertEqual(self.lyrics(), "[00:14.00]from lrclib")

    def test_second_play_needs_no_network(self):
        self.play()
        self.calls.clear()
        self.play()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.lyrics(), "[00:01.00]from lrclib")

    def test_ad_hides_lyrics_and_caches_nothing(self):
        self.play()                         # learn the real length
        now = self.play(length=15_000_000)  # same title, ad length
        self.assertEqual(self.lyrics(), "")
        self.assertEqual(now[4], "233000")

    def test_first_play_starting_with_ad(self):
        now = self.play(length=15_000_000, url="")
        self.assertEqual(self.lyrics(), "")
        self.assertEqual(list(mh.MUSIC.iterdir()), [])
        self.assertEqual(now[3:], ["", ""])

    def test_caption_download_failure_falls_through_to_lrclib(self):
        self.info["subtitles"] = {"en": [{"ext": "json3", "url": "https://c/blocked"}]}
        real = self.fake_http
        def blocked(url):
            if url.endswith("blocked"):
                raise mh.HttpError(403)
            return real(url)
        mh.http = blocked
        self.assertEqual(self.play()[3], "lrclib")
        self.assertFalse((mh.CAPTIONS / "JGwWNGJdvx8.lrc").exists())    # retried next time

    def test_two_videos_of_one_song_both_show_lyrics(self):
        self.play(length=250_000_000, url="")       # no video id: official video
        self.assertEqual(self.lyrics(), "[00:01.00]from lrclib")
        self.play(length=210_000_000, url="")       # lyric video, same song, other length
        self.assertEqual(self.lyrics(), "[00:01.00]from lrclib")

    def test_long_ad_first_does_not_hide_the_video_later(self):
        self.play(length=70_000_000, url="")        # 70 s ad, taken as the video
        self.play(length=233_000_000, url="")
        self.assertEqual(self.lyrics(), "[00:01.00]from lrclib")

    def test_without_url_searches_by_title_and_channel(self):
        self.info = {"entries": [{"id": "JGwWNGJdvx8", "title": "Ed Sheeran - Shape of You (Official Video)",
                                  "channel": "Ed Sheeran", "duration": 233}]}
        now = self.play(url="")
        self.assertEqual(self.calls[0], ("ytdlp", "ytsearch5:Ed Sheeran - Shape of You (Official Video) Ed Sheeran"))
        self.assertEqual(now[4], "233000")


if __name__ == "__main__":
    unittest.main()
