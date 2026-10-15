/*
    Apple Music-style synced lyrics.

    - Big, heavy text; long lines wrap onto two lines.
    - The current line is bright and sharp. The others get dimmer, smaller
      and more blurred the further away they are, which gives the depth.
    - When the line changes, every line glides to its new place with a soft
      spring, and lines further down start a little later, so the list moves
      like a wave instead of one block.
    - Long instrumental breaks show three breathing dots.
*/

import QtQuick
import QtQuick.Effects
import org.kde.kirigami as Kirigami

Item {
    id: root

    property string lyricsText: ""     // LRC text from MediaFiles
    property real positionMs: 0        // song position from NowPlaying
    property bool shown: true

    // Where the current line sits, as a fraction of the height
    readonly property real focusRatio: 0.33

    // [{ time: ms, text: "...", gap: bool }]
    readonly property var lines: parse(lyricsText)

    // Line being sung now (-1 before the first line). Switching 0.25 s early
    // feels in time, because the eye needs a moment to move.
    readonly property int current: {
        let index = -1;
        for (let i = 0; i < lines.length && lines[i].time <= positionMs + 250; i++) {
            index = i;
        }
        return index;
    }
    readonly property int focusIndex: Math.max(current, 0)

    function parse(text) {
        const timed = [];
        for (const line of text.split("\n")) {
            const match = line.match(/^\[(\d+):(\d+(?:\.\d+)?)\](.*)$/);
            if (match) {
                timed.push({
                    time: (parseInt(match[1]) * 60 + parseFloat(match[2])) * 1000,
                    text: match[3].trim(),
                });
            }
        }
        // Keep empty lines only as breaks of 4 s or more; drop the rest
        const result = [];
        for (let i = 0; i < timed.length; i++) {
            const next = i + 1 < timed.length ? timed[i + 1].time : Infinity;
            if (timed[i].text.length > 0) {
                result.push({ time: timed[i].time, text: timed[i].text, gap: false });
            } else if (next - timed[i].time >= 4000 && result.length > 0) {
                result.push({ time: timed[i].time, text: "", gap: true });
            }
        }
        return result;
    }

    opacity: shown && lines.length > 0 ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 500; easing.type: Easing.InOutQuad } }

    // ------------------------------------------------------------ scrolling

    // Bumped whenever the column re-lays out (lines wrap, fonts load ...)
    property int layoutTick: 0

    // How far the column must scroll so the current line sits at focusRatio
    readonly property real targetOffset: {
        layoutTick;
        const item = repeater.count > focusIndex ? repeater.itemAt(focusIndex) : null;
        return item ? item.y + item.height / 2 - height * focusRatio : 0;
    }
    property real lastOffset: 0
    property bool ready: false

    // The column jumps straight to its new place; each line is then pushed
    // back by the same amount and animated home, with its own delay.
    onTargetOffsetChanged: {
        const delta = targetOffset - lastOffset;
        lastOffset = targetOffset;
        if (!ready || Math.abs(delta) < 0.5) {
            return;
        }
        for (let i = 0; i < repeater.count; i++) {
            const item = repeater.itemAt(i);
            if (item) {
                item.glide(delta);
            }
        }
    }

    // New song: place everything without animating
    onLinesChanged: {
        ready = false;
        Qt.callLater(() => {
            lastOffset = targetOffset;
            ready = true;
        });
    }

    // ------------------------------------------------------------ drawing

    Item {
        id: content
        anchors.fill: parent

        // Soft fade at the top and bottom edges instead of a hard cut.
        // Applied in place: hiding this item and drawing a masked copy
        // would stop the per-line blur layers inside it from rendering.
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: fadeMask
        }

        Column {
            id: column
            width: parent.width
            y: -root.targetOffset
            spacing: Kirigami.Units.gridUnit * 1.3
            onPositioningComplete: root.layoutTick++

            Repeater {
                id: repeater
                model: root.lines

                delegate: Item {
                    id: lyricLine

                    required property var modelData
                    required property int index

                    readonly property bool active: index === root.current
                    readonly property int distance: index - root.focusIndex   // negative = already sung

                    width: column.width
                    height: modelData.gap ? dots.height : label.height

                    // Lines near the screen get the blur layer; far ones are
                    // off-screen anyway. (Not `visible`: Column skips hidden
                    // items, which would make the list jump.)
                    readonly property bool near: distance > -6 && distance < 9

                    function glide(delta) {
                        move.stop();
                        shift.y += delta;
                        // Lines above the current one move at once; lines
                        // below follow one after another, like a wave
                        pause.duration = Math.min(Math.max(distance + 1, 0) * 55, 450);
                        move.start();
                    }

                    transform: Translate { id: shift }

                    SequentialAnimation {
                        id: move
                        PauseAnimation { id: pause }
                        NumberAnimation {
                            target: shift
                            property: "y"
                            to: 0
                            duration: 800
                            easing.type: Easing.OutBack
                            easing.overshoot: 0.7      // a soft spring, barely past the target
                        }
                    }

                    opacity: active ? 1 : Math.max(0.14, 0.42 - Math.abs(distance) * 0.06)
                    scale: active ? 1 : 0.93
                    transformOrigin: Item.Left
                    Behavior on opacity { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }

                    layer.enabled: near
                    layer.effect: MultiEffect {
                        blurEnabled: true
                        blurMax: 32
                        blur: lyricLine.active ? 0 : Math.min(Math.abs(lyricLine.distance) * 0.16, 0.7)
                        Behavior on blur { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                    }

                    Text {
                        id: label
                        visible: !lyricLine.modelData.gap
                        width: parent.width
                        text: lyricLine.modelData.text
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        lineHeight: 1.05
                        color: "white"
                        font.family: "Red Hat Display"
                        font.weight: Font.ExtraBold
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 3.4
                    }

                    // Instrumental break: three dots that breathe while active
                    Row {
                        id: dots
                        visible: lyricLine.modelData.gap
                        spacing: Kirigami.Units.gridUnit * 0.6
                        topPadding: Kirigami.Units.gridUnit * 0.5
                        bottomPadding: topPadding

                        Repeater {
                            model: 3
                            Rectangle {
                                required property int index
                                width: Kirigami.Units.gridUnit * 0.9
                                height: width
                                radius: width / 2
                                color: "white"
                                SequentialAnimation on opacity {
                                    running: lyricLine.active && lyricLine.modelData.gap
                                    loops: Animation.Infinite
                                    PauseAnimation { duration: index * 250 }
                                    NumberAnimation { from: 0.35; to: 1; duration: 600; easing.type: Easing.InOutSine }
                                    NumberAnimation { from: 1; to: 0.35; duration: 600; easing.type: Easing.InOutSine }
                                    PauseAnimation { duration: (2 - index) * 250 }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Mask for the fade: opaque in the middle, transparent at the edges
    Item {
        id: fadeMask
        anchors.fill: parent
        visible: false
        layer.enabled: true

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.14; color: "white" }
                GradientStop { position: 0.80; color: "white" }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

}
