import QtQuick 2.0
import QtQuick.Layouts 1.3
import QtQuick.Controls 2.1
import QtQuick.Window 2.1
import QtQuick.Controls.Material 2.1

import dai.gui 1.0

ListView {
    id: cameraPreview

    Rectangle {
        id: cameraPreviewRect
        color: "black"
        width: parent.width
        height: parent.height

        ImageWriter {
            id: imageWriter
            objectName: "writer"
            anchors.fill: parent
            anchors.margins: 10
        }

        RowLayout {
            anchors.top: parent.top
            anchors.topMargin: 10
            anchors.horizontalCenter: parent.horizontalCenter
            height: 50
            spacing: 10

            ComboBox {
                id: comboBoxImage
                Layout.preferredWidth: 150
                Layout.fillHeight: true
                model: previewChoices
                onActivated: function(index) {
                    previewBridge.changeSelected(model[index])
                }
            }

            ComboBox {
                id: comboBoxDevices
                Layout.preferredWidth: 200
                Layout.fillHeight: true
                model: deviceChoices
                onActivated: function(index) {
                    appBridge.selectDevice(model[index])
                }
            }

            Button {
                Layout.preferredWidth: 100
                Layout.fillHeight: true
                text: "Reload"
                onClicked: appBridge.reloadDevices()
            }

            Button {
                id: recordButton
                Layout.preferredWidth: 100
                Layout.fillHeight: true
                text: recording ? "Stop" : "Record"
                onClicked: appBridge.toggleRecording()
            }

            Button {
                id: uploadButton
                Layout.preferredWidth: 100
                Layout.fillHeight: true
                text: "Upload"
                onClicked: appBridge.uploadFiles()
            }
        }
    }
}
/*##^##
Designer {
    D{i:0;autoSize:true;height:480;width:640}
}
##^##*/
