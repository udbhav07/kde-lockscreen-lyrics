/*
    Apple Music-style synced lyrics: the current line is bright and in focus,
    the others are dimmed and blurred, and the list slides up as the song plays.
*/

import QtQuick
import QtQuick.Effects
import org.kde.kirigami as Kirigami

Item {
    id: root

    property string lyricsText: ""     // LRC text from MediaFiles
    property real positionMs: 0        // song position from NowPlaying
    property bool shown: true

    // [{ time: ms, text: "..." }], from lines like "[01:23.45] words"
    readonly property var lines: parse(lyricsText)

    // Index of the line being sung now (-1 before the first line).
    // Switching 0.3 s early feels in time, because the eye needs a moment.
    readonly property int current: {
        let index = -1;
        for (let i = 0; i < lines.length && lines[i].time <= positionMs + 300; i++) {
            index = i;
        }
        return index;
    }

    function parse(text) {
        const result = [];
        for (const line of text.split("\n")) {
            const match = line.match(/^\[(\d+):(\d+(?:\.\d+)?)\](.*)$/);
            if (match && match[3].trim().length > 0) {
                result.push({
                    time: (parseInt(match[1]) * 60 + parseFloat(match[2])) * 1000,
                    text: match[3].trim(),
                });
            }
        }
        return result;
    }

    opacity: shown && lines.length > 0 ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 400 } }

    ListView {
        id: view
        anchors.fill: parent
        clip: true
        interactive: false
        model: root.lines
        currentIndex: Math.max(root.current, 0)

        // Keep the current line about a third of the way down, sliding smoothly
        highlightRangeMode: ListView.StrictlyEnforceRange
        preferredHighlightBegin: height * 0.3
        preferredHighlightEnd: preferredHighlightBegin
        highlightMoveDuration: 600
        highlightMoveVelocity: -1

        delegate: Text {
            id: lyricLine

            required property var modelData
            required property int index
            readonly property bool active: index === root.current
            readonly property int distance: Math.abs(index - Math.max(root.current, 0))

            width: ListView.view.width
            topPadding: Kirigami.Units.gridUnit * 0.4
            bottomPadding: Kirigami.Units.gridUnit * 0.4
            text: modelData.text
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: "white"
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 2.2
            font.weight: Font.Bold

            opacity: active ? 1 : Math.max(0.15, 0.5 - distance * 0.08)
            scale: active ? 1 : 0.95
            transformOrigin: Item.Left
            Behavior on opacity { NumberAnimation { duration: 400 } }
            Behavior on scale { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

            // Blur grows with distance from the current line
            layer.enabled: !active
            layer.effect: MultiEffect {
                blurEnabled: true
                blurMax: 24
                blur: Math.min(lyricLine.distance * 0.15, 0.6)
            }
        }
    }
}
