/*
    Big media controller for the idle lock screen: cover, title, artist,
    progress, previous / play-pause / next, and the lyrics on/off button.
*/

import QtQuick
import QtQuick.Layouts
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
    readonly property color accent: "#C3C6FB"

    // Song position in milliseconds. The player only reports it now and then,
    // so it is counted forward here and corrected every 2 seconds.
    property real positionMs: 0
    readonly property real lengthMs: player ? player.length / 1000 : 0

    function formatTime(ms) {
        const s = Math.max(0, Math.floor(ms / 1000));
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }

    implicitWidth: Kirigami.Units.gridUnit * 24
    implicitHeight: row.implicitHeight + Kirigami.Units.gridUnit * 2
    radius: Kirigami.Units.gridUnit
    color: Qt.rgba(0, 0, 0, 0.35)     // see-through, so the live wallpaper still shows

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

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: Kirigami.Units.gridUnit
        spacing: Kirigami.Units.gridUnit

        Item {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 6
            Layout.preferredHeight: Layout.preferredWidth

            Kirigami.ShadowedImage {
                id: cover
                anchors.fill: parent
                radius: Kirigami.Units.cornerRadius * 2
                color: Qt.rgba(1, 1, 1, 0.08)
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
                color: root.accent
                opacity: 0.6
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            PlasmaComponents3.Label {
                Layout.fillWidth: true
                text: root.player ? root.player.track : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                maximumLineCount: 1
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.4
                font.weight: Font.DemiBold
                color: "white"
            }

            PlasmaComponents3.Label {
                Layout.fillWidth: true
                text: root.player ? (root.player.artist || root.player.identity) : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                maximumLineCount: 1
                color: "white"
                opacity: 0.7
            }

            // Progress bar
            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                implicitHeight: 4
                radius: 2
                color: Qt.rgba(1, 1, 1, 0.2)

                Rectangle {
                    width: root.lengthMs > 0 ? parent.width * root.positionMs / root.lengthMs : 0
                    height: parent.height
                    radius: parent.radius
                    color: root.accent
                }
            }

            RowLayout {
                Layout.fillWidth: true

                PlasmaComponents3.Label {
                    text: root.formatTime(root.positionMs)
                    color: "white"
                    opacity: 0.6
                    font: Kirigami.Theme.smallFont
                }
                Item { Layout.fillWidth: true }
                PlasmaComponents3.Label {
                    text: root.formatTime(root.lengthMs)
                    color: "white"
                    opacity: 0.6
                    font: Kirigami.Theme.smallFont
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                PlasmaComponents3.ToolButton {
                    enabled: root.player !== null && root.player.canGoPrevious
                    icon.name: "media-skip-backward"
                    icon.color: root.accent
                    icon.width: Kirigami.Units.iconSizes.medium
                    icon.height: icon.width
                    focusPolicy: Qt.TabFocus
                    onClicked: root.player.Previous()
                    Accessible.name: "Previous track"
                }

                PlasmaComponents3.ToolButton {
                    icon.name: root.playing ? "media-playback-pause" : "media-playback-start"
                    icon.color: root.accent
                    icon.width: Kirigami.Units.iconSizes.large
                    icon.height: icon.width
                    focusPolicy: Qt.TabFocus
                    onClicked: root.player.PlayPause()
                    Accessible.name: "Play or pause"
                }

                PlasmaComponents3.ToolButton {
                    enabled: root.player !== null && root.player.canGoNext
                    icon.name: "media-skip-forward"
                    icon.color: root.accent
                    icon.width: Kirigami.Units.iconSizes.medium
                    icon.height: icon.width
                    focusPolicy: Qt.TabFocus
                    onClicked: root.player.Next()
                    Accessible.name: "Next track"
                }

                Item { Layout.fillWidth: true }

                // Only when the current song has synced lyrics
                PlasmaComponents3.ToolButton {
                    visible: root.files !== null && root.files.lyricsText.length > 0
                    checked: root.lyricsShown
                    icon.name: "view-media-lyrics-symbolic"
                    icon.color: root.accent
                    text: "Lyrics"
                    focusPolicy: Qt.TabFocus
                    onClicked: root.lyricsButtonClicked()
                    Accessible.name: root.lyricsShown ? "Hide lyrics" : "Show lyrics"
                }
            }
        }
    }
}
