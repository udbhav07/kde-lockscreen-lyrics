/*
    Temporary test: can the lock screen read the helper's files in ~/.cache?
    Shows the cover image and tries two ways of reading lyrics.lrc.
    Delete this file (and its use in LockScreenUi.qml) once the test is done.
*/

import QtQuick
import QtCore
import org.kde.plasma.plasma5support as P5Support

Rectangle {
    id: root

    // file:///home/<you>/.cache/kde-lockscreen-lyrics
    readonly property string cacheUrl: StandardPaths.writableLocation(StandardPaths.GenericCacheLocation) + "/kde-lockscreen-lyrics"
    readonly property string cachePath: cacheUrl.replace("file://", "")

    property string xhrResult: "waiting..."
    property string execResult: "waiting..."

    width: 520
    height: content.height + 32
    radius: 12
    color: Qt.rgba(0, 0, 0, 0.45)   // see-through, so the live wallpaper still shows

    Column {
        id: content
        x: 16
        y: 16
        width: parent.width - 32
        spacing: 8

        Image {
            id: cover
            width: 120
            height: 120
            fillMode: Image.PreserveAspectCrop
            source: root.cacheUrl + "/cover.jpg"
        }

        Text {
            width: parent.width
            color: "white"
            wrapMode: Text.Wrap
            text: "1. Image: " + ["not set", "OK", "loading", "ERROR"][cover.status] + "\n"
                + "2. XMLHttpRequest: " + root.xhrResult + "\n"
                + "3. Run 'head': " + root.execResult + "\n"
                + "folder: " + root.cachePath
        }
    }

    // Way 2: JavaScript's XMLHttpRequest on a file:// URL
    Component.onCompleted: {
        try {
            const xhr = new XMLHttpRequest();
            xhr.onreadystatechange = () => {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    root.xhrResult = xhr.responseText.length > 0
                        ? "OK, first line: " + xhr.responseText.split("\n")[0]
                        : "ERROR (empty, status " + xhr.status + ")";
                }
            };
            xhr.open("GET", root.cacheUrl + "/lyrics.lrc");
            xhr.send();
        } catch (e) {
            root.xhrResult = "ERROR: " + e;
        }
    }

    // Way 3: run the 'head' command through Plasma's executable engine
    P5Support.DataSource {
        engine: "executable"
        onNewData: (source, data) => {
            root.execResult = data["exit code"] === 0
                ? "OK, first line: " + data.stdout.split("\n")[0]
                : "ERROR (exit " + data["exit code"] + "): " + data.stderr;
            disconnectSource(source);
        }
        Component.onCompleted: connectSource("head -n 1 '" + root.cachePath + "/lyrics.lrc'")
    }
}
