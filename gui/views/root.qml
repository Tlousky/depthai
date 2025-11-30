/****************************************************************************
**
** Copyright (C) 2021 The Qt Company Ltd.
** Contact: https://www.qt.io/licensing/
**
** This file is part of the examples of Qt for Python.
**
** $QT_BEGIN_LICENSE:BSD$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see https://www.qt.io/terms-conditions. For further
** information use the contact form at https://www.qt.io/contact-us.
**
** BSD License Usage
** Alternatively, you may use this file under the terms of the BSD license
** as follows:
**
** "Redistribution and use in source and binary forms, with or without
** modification, are permitted provided that the following conditions are
** met:
**   * Redistributions of source code must retain the above copyright
**     notice, this list of conditions and the following disclaimer.
**   * Redistributions in binary form must reproduce the above copyright
**     notice, this list of conditions and the following disclaimer in
**     the documentation and/or other materials provided with the
**     distribution.
**   * Neither the name of The Qt Company Ltd nor the names of its
**     contributors may be used to endorse or promote products derived
**     from this software without specific prior written permission.
**
**
** THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
** "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
** LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
** A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
** OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
** SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
** LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
** DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
** THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
** (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
** OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
**
** $QT_END_LICENSE$
**
****************************************************************************/

import QtQuick 2.0
import QtQuick.Layouts 1.3
import QtQuick.Controls 2.1
import QtQuick.Window 2.1
import QtQuick.Controls.Material 2.1

import dai.gui 1.0

ApplicationWindow {
    width: 1700
    height: 640
    Material.theme: Material.Dark
    Material.accent: Material.Red
    visible: true

    property var previewChoices: []
    property var modelChoices: []
    property var modelSourceChoices: []
    property var ovVersions: []
    property var countLabels: []
    property var medianChoices: []
    property var colorResolutionChoices: []
    property var monoResolutionChoices: []
    property var restartRequired
    property var deviceChoices: []
    property var irEnabled: false
    property var irDotBrightness: 0
    property var irFloodBrightness: 0
    property var depthEnabled: true
    property var statisticsAccepted: true
    property var runningApp
    property bool recording: false

    property bool lrc: false

    // AI Properties
    property bool nnEnabled: true
    property string cnnModel: "mobilenet-ssd"
    property int shaves: 6
    property string modelSource: "color"
    property bool fullFov: true
    property bool sbb: false
    property real sbbFactor: 0.3
    property string ovVersion: "2021.4"
    property string countLabel: "person"

    // Depth Properties
    property bool disparityEnabled: false
    property bool subpixel: false
    property bool extendedDisparity: false
    property int disparityConfidenceThreshold: 240
    property int lrcThreshold: 10
    property int bilateralSigma: 0
    property real depthRangeFrom: 0
    property real depthRangeTo: 10
    property string medianFilter: "KERNEL_7x7"
    property int irLaserDotProjector: 0
    property int irFloodIlluminator: 0

    // Camera Properties
    property bool sync: true
    property bool rgbDepthAlignment: true
    property int colorIso: 0
    property int colorExposure: 0
    property int colorContrast: 0
    property int colorBrightness: 0
    property int colorSaturation: 0
    property int colorSharpness: 0
    property int colorFps: 30
    property string colorResolution: "THE_1080_P"
    property int monoIso: 0
    property int monoExposure: 0
    property int monoContrast: 0
    property int monoBrightness: 0
    property int monoSaturation: 0
    property int monoSharpness: 0
    property int monoFps: 30
    property string monoResolution: "THE_400_P"

    // Misc Properties
    property string reportPath: ""
    property string encodeOutput: ""
    property int encodeColorFps: 30
    property int encodeLeftFps: 30
    property int encodeRightFps: 30
    property int encodeDepthFps: 30
    property int encodeIrFps: 30
    property bool encodeColor: true
    property bool encodeLeft: false
    property bool encodeRight: false
    property bool encodeDepth: true
    property bool encodeIr: false
    property bool encodePointCloud: false
    property bool reportTemp: false
    property bool reportCpu: false
    property bool reportMem: false


    AppBridge {
        id: appBridge
    }

    DepthBridge {
        id: depthBridge
    }
    ColorCamBridge {
        id: colorCamBridge
    }
    MonoCamBridge {
        id: monoCamBridge
    }
    PreviewBridge {
        id: previewBridge
    }
    AIBridge {
        id: aiBridge
    }

    Rectangle {
        id: root
        x: 0
        y: 0
        width: parent.width
        height: parent.height
        color: "#000000"
        enabled: true

        CameraPreview {
          x: 0
          y: 0
          width: parent.width - 630
          height: parent.height
        }

        TabBar {
            id: bar
            x: parent.width - 630
            y: 0
            height: 50
            width: 590

            TabButton {
                text: "AI"
            }

            TabButton {
                enabled: depthEnabled
                text: "Depth"
            }
            TabButton {
               text: "Camera"
            }
            TabButton {
               text: "Misc"
            }
        }

        StackLayout {
          x: parent.width - 630
          y: 70
          width: 630
          currentIndex: bar.currentIndex
          Item {
                AIProperties {}
          }
          Item {
                DepthProperties {}
          }
          Item {
               CameraProperties {}
          }
          Item {
               MiscProperties {}
          }
        }

        Button {
            x: parent.width - 600
            y: 540
            enabled: restartRequired || false
            height: 60
            width: 563
            text: "Apply and Restart"
            onClicked: appBridge.applyAndRestart()
        }
    }
}
