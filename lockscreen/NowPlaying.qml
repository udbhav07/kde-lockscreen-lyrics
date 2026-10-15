/*
    Big media controller for the idle lock screen, in one row:

    ┌──────────────────────────────────────────────────────────────┐
    │ ▣▣▣   ⏮ ( ⏸ ) ⏭          Title                         [≡]  │
    │ ▣▣▣                       Artist                             │
    │ ▣▣▣              1:23 ━━━━━━━━━━━━━━━━━━━━ -2:10             │
    └──────────────────────────────────────────────────────────────┘
*/

import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris

Rectangle {
    id: root

    property MediaFiles files
    property bool shown: true          // false fades the controller out
    property bool lyricsShown: true
    signal lyricsButtonClicked()

    readonly property var player: mpris.currentPlayer
    readonly property bool hasMedia: player !== null && player.track.length > 0
    readonly property bool playing: player !== null && player.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property bool hasLyrics: files !== null && files.lyricsText.length > 0
    readonly property color accent: "#C3C6FB"

    // Song position in milliseconds. The player only reports it now and then,
    // so it is counted forward here and corrected every 2 seconds.
    property real positionMs: 0
    readonly property real lengthMs: player ? player.length / 1000 : 0

    function formatTime(ms) {
        const s = Math.max(0, Math.floor(ms / 1000));
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }

    implicitWidth: Kirigami.Units.gridUnit * 36
    implicitHeight: content.implicitHeight + Kirigami.Units.gridUnit * 1.8
    radius: Kirigami.Units.gridUnit * 1.2
    color: Qt.rgba(0, 0, 0, 0.38)          // see-through, so the live wallpaper still shows
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.08)   // a faint glass edge

    opacity: shown && hasMedia ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 300 } }

    Mpris.Mpris2Model {
        id: mpris
    }

    onPlayerChanged: positionMs = player ? player.position / 1000 : 0

    Connections {
        target: root.player
        function onPositionChanged() {
            root.positionMs = root.player.position / 1000;
        }
        function onTrackChanged() {
            root.positionMs = 0;
            root.player.updatePosition();
        }
    }

    Timer {
        interval: 100
        repeat: true
        running: root.playing
        onTriggered: {
            const next = root.positionMs + interval * (root.player.rate || 1);
            root.positionMs = root.lengthMs > 0 ? Math.min(next, root.lengthMs) : next;
        }
    }

    Timer {
        interval: 2000
        repeat: true
        running: root.playing
        triggeredOnStart: true
        onTriggered: root.player.updatePosition()
    }

    // A round icon button that grows a little on hover and shrinks when pressed
    component RoundButton: Item {
        id: button

        property string iconName             // a theme icon, or ...
        property string glyph                // ... one drawn here: "play", "pause", "next", "previous"
        property real diameter: Kirigami.Units.gridUnit * 2.6
        property bool filled: false          // filled = the big play/pause button
        property string accessibleName
        signal clicked()

        implicitWidth: diameter
        implicitHeight: diameter
        opacity: enabled ? 1 : 0.35
        scale: mouse.pressed ? 0.9 : mouse.containsMouse ? 1.08 : 1
        Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: button.filled ? root.accent
                 : mouse.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent"
            Behavior on color { ColorAnimation { duration: 150 } }
        }

        Kirigami.Icon {
            anchors.centerIn: parent
            visible: button.glyph === ""
            width: button.diameter * 0.55
            height: width
            source: button.iconName
            isMask: true
            color: root.accent
        }

        // Bold, filled media symbols (theme icons are thin outlines)
        Item {
            id: glyphBox
            readonly property real s: button.diameter * (button.filled ? 0.38 : 0.42)
            readonly property color ink: button.filled ? "#15172b" : root.accent
            anchors.centerIn: parent
            width: s
            height: s
            visible: button.glyph !== ""
            // "previous" is "next" mirrored
            transform: Scale { origin.x: glyphBox.s / 2; xScale: button.glyph === "previous" ? -1 : 1 }

            // Triangle: play, and the arrow of next/previous
            Shape {
                anchors.fill: parent
                visible: button.glyph !== "pause"
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    id: triangle
                    strokeWidth: -1
                    fillColor: glyphBox.ink
                    joinStyle: ShapePath.RoundJoin
                    readonly property real s: glyphBox.s
                    readonly property bool play: button.glyph === "play"
                    // play is nudged right so it looks centred in the circle
                    startX: play ? s * 0.18 : s * 0.04; startY: s * 0.06
                    PathLine { x: triangle.play ? triangle.s * 0.98 : triangle.s * 0.66; y: triangle.s * 0.5 }
                    PathLine { x: triangle.play ? triangle.s * 0.18 : triangle.s * 0.04; y: triangle.s * 0.94 }
                    PathLine { x: triangle.play ? triangle.s * 0.18 : triangle.s * 0.04; y: triangle.s * 0.06 }
                }
            }
            // Bar of next/previous
            Rectangle {
                visible: button.glyph === "next" || button.glyph === "previous"
                x: glyphBox.s * 0.74; y: glyphBox.s * 0.08
                width: glyphBox.s * 0.16; height: glyphBox.s * 0.84
                radius: width / 2
                color: glyphBox.ink
            }
            // Two bars of pause
            Repeater {
                model: button.glyph === "pause" ? 2 : 0
                Rectangle {
                    required property int index
                    x: glyphBox.s * (index === 0 ? 0.1 : 0.6); y: glyphBox.s * 0.04
                    width: glyphBox.s * 0.3; height: glyphBox.s * 0.92
                    radius: glyphBox.s * 0.08
                    color: glyphBox.ink
                }
            }
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: button.clicked()
        }

        Accessible.role: Accessible.Button
        Accessible.name: accessibleName
        Accessible.onPressAction: clicked()
    }

    // One row: cover | prev play next | title, artist, progress | lyrics
    RowLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Kirigami.Units.gridUnit * 0.9
        spacing: Kirigami.Units.gridUnit

        Item {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 4.4
            Layout.preferredHeight: Layout.preferredWidth

            Kirigami.ShadowedImage {
                id: cover
                anchors.fill: parent
                radius: Kirigami.Units.gridUnit * 0.6
                color: Qt.rgba(1, 1, 1, 0.08)
                shadow.size: Kirigami.Units.gridUnit
                shadow.color: Qt.rgba(0, 0, 0, 0.5)
                shadow.yOffset: 2
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: width * Screen.devicePixelRatio
                sourceSize.height: height * Screen.devicePixelRatio
                source: root.files ? root.files.coverUrl : ""
            }

            Kirigami.Icon {
                anchors.centerIn: parent
                width: parent.width / 2
                height: width
                visible: cover.status !== Image.Ready
                source: "media-album-cover-manager-amarok-symbolic"
                isMask: true
                color: root.accent
                opacity: 0.6
            }
        }

        Row {
            Layout.alignment: Qt.AlignVCenter
            spacing: Kirigami.Units.gridUnit * 0.4

            RoundButton {
                anchors.verticalCenter: parent.verticalCenter
                diameter: Kirigami.Units.gridUnit * 2.2
                glyph: "previous"
                enabled: root.player !== null && root.player.canGoPrevious
                accessibleName: "Previous track"
                onClicked: root.player.Previous()
            }

            RoundButton {
                anchors.verticalCenter: parent.verticalCenter
                diameter: Kirigami.Units.gridUnit * 3
                filled: true
                glyph: root.playing ? "pause" : "play"
                accessibleName: "Play or pause"
                onClicked: root.player.PlayPause()
            }

            RoundButton {
                anchors.verticalCenter: parent.verticalCenter
                diameter: Kirigami.Units.gridUnit * 2.2
                glyph: "next"
                enabled: root.player !== null && root.player.canGoNext
                accessibleName: "Next track"
                onClicked: root.player.Next()
            }
        }

        // Title and artist centred, progress underneath
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: Kirigami.Units.smallSpacing

            PlasmaComponents3.Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                text: root.player ? root.player.track : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                maximumLineCount: 1
                font.family: "Red Hat Display"
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.4
                font.weight: Font.Bold
                color: "white"
            }

            PlasmaComponents3.Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                text: root.player ? (root.player.artist || root.player.identity) : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                maximumLineCount: 1
                font.family: "Red Hat Display"
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.05
                font.weight: Font.Medium
                color: "white"
                opacity: 0.65
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing * 2

                PlasmaComponents3.Label {
                    text: root.formatTime(root.positionMs)
                    color: "white"
                    opacity: 0.55
                    font.family: "Red Hat Display"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    font.features: { "tnum": 1 }      // digits of equal width, so the time doesn't wobble
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 4
                    radius: height / 2
                    color: Qt.rgba(1, 1, 1, 0.18)

                    Rectangle {
                        width: root.lengthMs > 0 ? parent.width * Math.min(root.positionMs / root.lengthMs, 1) : 0
                        height: parent.height
                        radius: parent.radius
                        color: root.accent
                    }
                }

                PlasmaComponents3.Label {
                    text: "-" + root.formatTime(root.lengthMs - root.positionMs)
                    color: "white"
                    opacity: 0.55
                    font.family: "Red Hat Display"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    font.features: { "tnum": 1 }
                }
            }
        }

        // Only when the current song has synced lyrics; highlighted while they show
        RoundButton {
            Layout.alignment: Qt.AlignVCenter
            diameter: Kirigami.Units.gridUnit * 2.2
            visible: root.hasLyrics
            iconName: "view-media-lyrics-symbolic"
            accessibleName: root.lyricsShown ? "Hide lyrics" : "Show lyrics"
            onClicked: root.lyricsButtonClicked()

            Rectangle {
                z: -1
                anchors.fill: parent
                radius: width / 2
                color: root.lyricsShown ? Qt.rgba(195 / 255, 198 / 255, 251 / 255, 0.22) : "transparent"
                Behavior on color { ColorAnimation { duration: 200 } }
            }
        }
    }
}
