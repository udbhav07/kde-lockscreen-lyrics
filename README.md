# kde-lockscreen-lyrics

Spotify controls and Apple Music-style synced lyrics on the KDE Plasma 6 lock screen. Live/video wallpapers keep working.

## What you get

- **Media controller** on the idle lock screen (the one right after <kbd>Meta</kbd>+<kbd>L</kbd>): album cover, title, artist, progress bar, ⏮ ⏯ ⏭
- **Synced lyrics** on the left: current line bright, others dimmed and blurred, sliding as the song plays
- **Lyrics toggle** button, shown only when the song has synced lyrics
- **Mouse-friendly idle screen**: moving the mouse or clicking the controller doesn't open the password prompt; a key press does
- **Instant lyrics** for the 25 songs before and after the current one, downloaded ahead of time
- **Local cache** of up to 500 songs (least recently used deleted first), so repeat songs need no internet

## How it works

```
Spotify ──MPRIS/D-Bus──► lockscreen-media-helper ──► ~/.cache/kde-lockscreen-lyrics/cover.jpg
   │                        (current song)               ~/.cache/kde-lockscreen-lyrics/lyrics.lrc
   │                                                           │
   └──Spotify Web API──► lockscreen-lyrics-prefetch ──► songs/<track-id>.jpg / .lrc  (cache)
                           (±25 songs)                         │
                                                               ▼
                                                 Lock screen QML reads the files
```

- **The lock screen can't use the internet**, so two background services (systemd user units) download everything into `~/.cache` and the lock screen only reads files.
- **`helper/lockscreen-media-helper`** (bash): follows Spotify with `playerctl`. On every song change it takes the cover and lyrics from `songs/` if saved, otherwise downloads the cover and asks [LRCLIB](https://lrclib.net) for synced lyrics, then swaps them into `cover.jpg` / `lyrics.lrc`. Each song runs as a background job, so a slow request never delays the next song.
- **`helper/lockscreen-lyrics-prefetch`** (Python): asks the Spotify Web API which playlist, album or Liked Songs list is playing and where, then fetches +1, −1, +2, −2 … up to ±25 into `songs/`. With shuffle, radio or mixes it uses Spotify's queue and recently played. Requests to LRCLIB are spaced out and back off on HTTP 429.
- **`lockscreen/MediaFiles.qml`**: every 0.5 s runs `stat` on the two files and re-reads them when they change (QML can't read local files directly on the lock screen, so it runs shell commands through Plasma's executable engine).
- **`lockscreen/NowPlaying.qml`**: the controller; talks to Spotify through KDE's MPRIS module and keeps the song position for the lyrics.
- **`lockscreen/LyricsView.qml`**: parses LRC (`[01:23.45] words`), picks the current line from the position, and animates the list.
- **`install.sh`**: copies `lockscreen/` into `/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/` (sudo) and installs/enables both services. `upstream/` holds KDE's untouched originals, for comparing after Plasma updates.

## Install

Requirements: KDE Plasma 6, Spotify desktop app, `playerctl`, `curl`, `jq`, `python3`.

```bash
./install.sh
/usr/libexec/kscreenlocker_greet --testing     # try it without really locking
```

Optional, for the ±25-song prefetch: create an app at [developer.spotify.com](https://developer.spotify.com/dashboard) with redirect URI `http://127.0.0.1:8888/callback` (Web API), then:

```bash
mkdir -p ~/.config/kde-lockscreen-lyrics
echo YOUR_CLIENT_ID > ~/.config/kde-lockscreen-lyrics/spotify-client-id
lockscreen-lyrics-prefetch --login
systemctl --user restart lockscreen-lyrics-prefetch
```

Re-run `./install.sh` after every `plasma-desktop` update, because updates overwrite the lock screen files.

## Undo

```bash
systemctl --user disable --now lockscreen-media-helper lockscreen-lyrics-prefetch
sudo dnf reinstall plasma-desktop      # restores KDE's original lock screen
```

## Credits

KDE Plasma (lock screen, GPL-2.0-or-later) · SilentSDDM (theme pieces, GPL-3.0) · [LRCLIB](https://lrclib.net) (lyrics). This project is GPL-3.0.
