/*
    Reads the files lockscreen-media-helper writes into
    ~/.cache/kde-lockscreen-lyrics. The lock screen blocks JavaScript file
    reads, so this runs small shell commands through Plasma's executable engine.
*/

import QtQuick
import QtCore
import org.kde.plasma.plasma5support as P5Support

Item {
    id: root

    readonly property string cacheUrl: StandardPaths.writableLocation(StandardPaths.GenericCacheLocation) + "/kde-lockscreen-lyrics"
    readonly property string cachePath: cacheUrl.replace("file://", "")

    // "" when there is no cover / no synced lyrics for the current song
    property string coverUrl: ""
    property string lyricsText: ""

    // The helper replaces files with mv, so their inode number changes on
    // every update. "name inode size mtime" per file tells us when to reload.
    property string coverStamp: ""
    property string lyricsStamp: ""
    readonly property string statCommand: "cd '" + cachePath + "' 2>/dev/null && stat -c '%n %i %s %Y' cover.jpg lyrics.lrc 2>/dev/null; true"
    readonly property string catCommand: "cat '" + cachePath + "/lyrics.lrc'"

    P5Support.DataSource {
        engine: "executable"
        interval: 500
        connectedSources: [root.statCommand]
        onNewData: (source, data) => {
            let cover = "";
            let lyrics = "";
            for (const line of data.stdout.trim().split("\n")) {
                const name = line.split(" ")[0];
                if (name === "cover.jpg") {
                    cover = line;
                } else if (name === "lyrics.lrc") {
                    lyrics = line;
                }
            }
            if (cover !== root.coverStamp) {
                root.coverStamp = cover;
                // The changing ?v= makes Image load the new file instead of a cached one
                root.coverUrl = cover ? root.cacheUrl + "/cover.jpg?v=" + encodeURIComponent(cover.split(" ")[1]) : "";
            }
            if (lyrics !== root.lyricsStamp) {
                root.lyricsStamp = lyrics;
                if (lyrics) {
                    reader.connectSource(root.catCommand);
                } else {
                    root.lyricsText = "";
                }
            }
        }
    }

    P5Support.DataSource {
        id: reader
        engine: "executable"
        onNewData: (source, data) => {
            root.lyricsText = data["exit code"] === 0 ? data.stdout.trim() : "";
            disconnectSource(source);
        }
    }
}
