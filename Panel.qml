import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "HueApi.js" as HueApi

Panel {
  id: root
  moduleName: "omarchy-philips-hue"
  ipcTarget: "omarchy-philips-hue"

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  property var config: null
  property string currentThemeName: ""
  property var lightsById: ({})
  property var rooms: []
  property var roomsWithLights: []
  property var orphanLights: []
  property int pendingFetches: 0
  property bool loading: false
  property bool lastFetchFailed: false
  property var pendingAction: null

  readonly property int roomCount: root.roomsWithLights.length
  readonly property int lightTotal: root.lightsTotal()
  readonly property int lightedRoomCount: root.lightedRooms().length
  readonly property bool allLightsOn: root.lightedRoomCount > 0 && root.lightedRooms().every(function(room) { return room.on })

  readonly property string statusText: {
    if (root.config === null) return "Not paired"
    if (root.lastFetchFailed) return "Bridge unreachable"
    if (root.loading) return "Loading…"
    var roomLabel = root.roomCount + " room" + (root.roomCount === 1 ? "" : "s")
    return roomLabel + " · " + root.lightTotal + " light" + (root.lightTotal === 1 ? "" : "s")
  }

  function lightedRooms() {
    var result = []
    for (var i = 0; i < root.roomsWithLights.length; i++) {
      if (root.roomsWithLights[i].lightCount > 0) result.push(root.roomsWithLights[i])
    }
    return result
  }

  function lightsTotal() {
    var total = 0
    for (var i = 0; i < root.roomsWithLights.length; i++) {
      total += root.roomsWithLights[i].lightCount
    }
    return total + root.orphanLights.length
  }

  function open() {
    root.controller.show()
    root.refresh()
  }

  function openFromHotkey() {
    root.controller.show()
    root.refresh()
  }

  function close() {
    root.controller.hide()
  }

  function refresh() {
    if (!root.config) {
      configFile.reload()
      return
    }
    root.lastFetchFailed = false
    if (root.roomsWithLights.length === 0 && root.orphanLights.length === 0) root.loading = true
    lightsProc.running = false
    groupsProc.running = false
    Qt.callLater(startFetches)
  }

  function startFetches() {
    if (!root.config) return
    root.pendingFetches = 2
    lightsProc.command = HueApi.curlGet(HueApi.lightsUrl(root.config))
    groupsProc.command = HueApi.curlGet(HueApi.groupsUrl(root.config))
    lightsProc.running = true
    groupsProc.running = true
  }

  function finishFetch(success) {
    root.pendingFetches--
    if (success === false) root.lastFetchFailed = true
    if (root.pendingFetches <= 0) {
      root.loading = false
      root.assembleRooms()
    }
  }

  function assembleRooms() {
    var used = {}
    var result = []
    for (var i = 0; i < root.rooms.length; i++) {
      var room = root.rooms[i]
      var lights = HueApi.roomLights(room, root.lightsById)
      for (var j = 0; j < room.lightIds.length; j++) used[room.lightIds[j]] = true
      result.push({ id: room.id, name: room.name, on: room.on, lightCount: lights.length, lights: lights })
    }
    var orphans = []
    for (var id in root.lightsById) {
      if (!used[id]) orphans.push(root.lightsById[id])
    }
    root.roomsWithLights = result
    root.orphanLights = orphans
  }

  function lightClone(light, changes) {
    return {
      id: light.id,
      name: light.name,
      on: changes.on !== undefined ? changes.on : light.on,
      bri: changes.bri !== undefined ? changes.bri : light.bri,
      hasBri: light.hasBri,
      ct: changes.ct !== undefined ? changes.ct : light.ct,
      hasCt: light.hasCt,
      hue: changes.hue !== undefined ? changes.hue : light.hue,
      sat: changes.sat !== undefined ? changes.sat : light.sat,
      hasColor: light.hasColor,
      pickerOpen: changes.pickerOpen !== undefined ? changes.pickerOpen : light.pickerOpen
    }
  }

  function lightCopy(light, on) {
    return root.lightClone(light, { on: on })
  }

  function setRoomOn(roomId, on) {
    var newRooms = []
    for (var i = 0; i < root.roomsWithLights.length; i++) {
      var room = root.roomsWithLights[i]
      newRooms.push({
        id: room.id,
        name: room.name,
        on: room.id === roomId ? on : room.on,
        lightCount: room.lightCount,
        lights: room.id === roomId
          ? room.lights.map(function(light) { return root.lightCopy(light, on) })
          : room.lights
      })
    }
    root.roomsWithLights = newRooms
  }

  function setLightOn(lightId, on) {
    var newRooms = []
    for (var i = 0; i < root.roomsWithLights.length; i++) {
      var room = root.roomsWithLights[i]
      newRooms.push({
        id: room.id,
        name: room.name,
        on: room.on,
        lightCount: room.lightCount,
        lights: room.lights.map(function(light) {
          return light.id === lightId ? root.lightCopy(light, on) : light
        })
      })
    }
    root.roomsWithLights = newRooms
    root.orphanLights = root.orphanLights.map(function(light) {
      return light.id === lightId ? root.lightCopy(light, on) : light
    })
  }

  function patchLights(lightId, changes) {
    var newRooms = []
    for (var i = 0; i < root.roomsWithLights.length; i++) {
      var room = root.roomsWithLights[i]
      newRooms.push({
        id: room.id,
        name: room.name,
        on: room.on,
        lightCount: room.lightCount,
        lights: room.lights.map(function(light) {
          return light.id === lightId ? root.lightClone(light, changes) : light
        })
      })
    }
    root.roomsWithLights = newRooms
    root.orphanLights = root.orphanLights.map(function(light) {
      return light.id === lightId ? root.lightClone(light, changes) : light
    })
  }

  function setLightBri(lightId, bri) {
    root.patchLights(lightId, { bri: bri })
  }

  function setLightCt(lightId, ct) {
    root.patchLights(lightId, { ct: ct })
  }

  function patchLightColor(lightId, hue, sat) {
    root.patchLights(lightId, { hue: hue, sat: sat })
  }

  function lightById(lightId) {
    for (var i = 0; i < root.roomsWithLights.length; i++) {
      var room = root.roomsWithLights[i]
      for (var j = 0; j < room.lights.length; j++) {
        if (room.lights[j].id === lightId) return room.lights[j]
      }
    }
    for (var k = 0; k < root.orphanLights.length; k++) {
      if (root.orphanLights[k].id === lightId) return root.orphanLights[k]
    }
    return null
  }

  function toggleColorPicker(lightId) {
    var light = root.lightById(lightId)
    if (light) root.patchLights(lightId, { pickerOpen: !light.pickerOpen })
  }

  function toggleRoom(roomId, on) {
    if (!root.config) return
    root.setRoomOn(roomId, on)
    root.runAction(HueApi.curlPutJson(HueApi.groupActionUrl(root.config, roomId), JSON.stringify({ on: on })))
    root.scheduleRefresh()
  }

  function toggleLight(lightId, on) {
    if (!root.config) return
    root.setLightOn(lightId, on)
    root.runAction(HueApi.curlPutJson(HueApi.lightStateUrl(root.config, lightId), JSON.stringify({ on: on })))
    root.scheduleRefresh()
  }

  function setBrightness(lightId, bri) {
    if (!root.config) return
    var clamped = Math.max(1, Math.min(254, Math.round(bri)))
    root.setLightBri(lightId, clamped)
    root.runAction(HueApi.curlPutJson(HueApi.lightStateUrl(root.config, lightId), JSON.stringify({ bri: clamped })))
    root.scheduleRefresh()
  }

  function setColorTemperature(lightId, ct) {
    if (!root.config) return
    var clamped = Math.max(153, Math.min(500, Math.round(ct)))
    root.setLightCt(lightId, clamped)
    root.runAction(HueApi.curlPutJson(HueApi.lightStateUrl(root.config, lightId), JSON.stringify({ ct: clamped })))
    root.scheduleRefresh()
  }

  function setLightColor(lightId, hue, sat) {
    if (!root.config) return
    root.patchLightColor(lightId, hue, sat)
    root.runAction(HueApi.curlPutJson(HueApi.lightStateUrl(root.config, lightId), JSON.stringify({ hue: hue, sat: sat })))
    root.scheduleRefresh()
  }

  function toggleAll(on) {
    if (!root.config || root.lightedRoomCount === 0) return
    var rooms = root.lightedRooms()
    var body = JSON.stringify({ on: on })
    for (var i = 0; i < rooms.length; i++) {
      root.runAction(HueApi.curlPutJson(HueApi.groupActionUrl(root.config, rooms[i].id), body))
    }
    root.setAllOn(on)
    root.scheduleRefresh()
  }

  function setAllOn(on) {
    root.roomsWithLights = root.roomsWithLights.map(function(room) {
      if (room.lightCount === 0) return room
      return {
        id: room.id,
        name: room.name,
        on: on,
        lightCount: room.lightCount,
        lights: room.lights.map(function(light) { return root.lightCopy(light, on) })
      }
    })
  }

  function runAction(command) {
    if (actionProc.running) {
      root.pendingAction = command
      return
    }
    actionProc.command = command
    actionProc.running = true
  }

  function scheduleRefresh() {
    resyncTimer.restart()
  }

  property FileView configFile: FileView {
    path: Quickshell.env("HOME") + "/.local/state/omarchy/settings/hue.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      root.config = HueApi.parseConfig(text())
      if (root.config) root.refresh()
    }
    onLoadFailed: root.config = null
  }

  property FileView themeNameFile: FileView {
    path: Quickshell.env("HOME") + "/.local/state/omarchy/current/theme.name"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      root.currentThemeName = String(text()).trim()
      root.syncThemeColor()
    }
  }

  property FileView colorsFile: FileView {
    path: Quickshell.env("HOME") + "/.local/state/omarchy/current/theme/colors.toml"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.syncThemeColor()
  }

  property FileView hueConfigFile: FileView {
    path: Quickshell.env("HOME") + "/.config/omarchy/settings/hue-theme.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
  }

  property string lastSyncedColor: ""

  function parseTomlAccent(text) {
    var lines = String(text || "").split("\n")
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim()
      if (line.indexOf("accent") === 0 && line.indexOf("=") !== -1) {
        var value = line.split("=")[1].trim()
        if (value.charAt(0) === '"' && value.charAt(value.length - 1) === '"')
          value = value.slice(1, -1)
        if (value.charAt(0) === "#" && value.length === 7)
          return value.slice(1)
      }
    }
    return ""
  }

  function parseHueConfig(text) {
    var raw = String(text || "").trim()
    if (!raw) return null
    try {
      return JSON.parse(raw)
    } catch (e) {
      return null
    }
  }

  function hexToHsv(hex) {
    var r = parseInt(hex.slice(0, 2), 16) / 255
    var g = parseInt(hex.slice(2, 4), 16) / 255
    var b = parseInt(hex.slice(4, 6), 16) / 255
    var mx = Math.max(r, g, b)
    var mn = Math.min(r, g, b)
    var d = mx - mn
    var hue01 = 0
    if (d !== 0) {
      if (mx === r) hue01 = ((g - b) / d) % 6
      else if (mx === g) hue01 = (b - r) / d + 2
      else hue01 = (r - g) / d + 4
    }
    hue01 = ((hue01 / 6) % 1 + 1) % 1
    var sat = mx === 0 ? 0 : d / mx
    return {
      hue: Math.round(hue01 * 65535) % 65536,
      sat: Math.round(sat * 254)
    }
  }

  function syncThemeColor() {
    if (!root.config) return

    var accentHex = root.parseTomlAccent(colorsFile.text())
    if (!accentHex) return
    if (accentHex === root.lastSyncedColor) return
    root.lastSyncedColor = accentHex

    var hueConfig = root.parseHueConfig(hueConfigFile.text())
    if (hueConfig && hueConfig.enabled === false) return

    var themeSlug = root.currentThemeName
    var color = accentHex
    if (hueConfig && hueConfig.themes && hueConfig.themes[themeSlug])
      color = String(hueConfig.themes[themeSlug]).replace(/^#/, "")

    if (color.length !== 6) return

    var hsv = root.hexToHsv(color)
    var transition = (hueConfig && hueConfig.transition) ? hueConfig.transition : 20
    var body = { hue: hsv.hue, sat: hsv.sat, transitiontime: transition }

    if (hueConfig && typeof hueConfig.bri === "number")
      body.bri = Math.max(1, Math.min(254, hueConfig.bri))
    if (hueConfig && hueConfig.turnOn)
      body.on = true

    hueSyncGroupsProc.command = HueApi.curlGet(HueApi.groupsUrl(root.config))
    hueSyncGroupsProc.pendingBody = JSON.stringify(body)
    hueSyncGroupsProc.running = true
  }

  Process {
    id: hueSyncGroupsProc

    property string pendingBody: ""

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var obj = null
        try { obj = JSON.parse(text) } catch (e) {}
        if (!obj) return

        var hueConfig = root.parseHueConfig(hueConfigFile.text())
        var targets = []
        for (var id in obj) {
          if (!Object.prototype.hasOwnProperty.call(obj, id)) continue
          var g = obj[id]
          var type = String(g.type || "")
          if (type !== "Room" && type !== "Zone") continue

          var configured = hueConfig ? hueConfig.groups : null
          if (configured && configured.indexOf("all") === -1) {
            var name = String(g.name || "").toLowerCase()
            var found = false
            for (var i = 0; i < configured.length; i++) {
              if (name.indexOf(String(configured[i]).toLowerCase()) !== -1) {
                found = true
                break
              }
            }
            if (!found) continue
          }
          targets.push(id)
        }

        for (var j = 0; j < targets.length; j++) {
          hueSyncActionProc.command = HueApi.curlPutJson(
            HueApi.groupActionUrl(root.config, targets[j]),
            hueSyncGroupsProc.pendingBody
          )
          hueSyncActionProc.running = true
        }
      }
    }
  }

  Process {
    id: hueSyncActionProc
  }

  Timer {
    interval: 1500
    running: true
    onTriggered: configFile.reload()
  }

  Timer {
    interval: 5000
    repeat: true
    running: root.config === null
    onTriggered: configFile.reload()
  }

  Timer {
    id: resyncTimer
    interval: 700
    onTriggered: root.refresh()
  }

  Timer {
    id: pollTimer
    interval: 15000
    repeat: true
    running: root.config !== null
    onTriggered: root.refresh()
  }

  Process {
    id: lightsProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var lights = HueApi.parseLights(text)
        var byId = {}
        for (var i = 0; i < lights.length; i++) byId[lights[i].id] = lights[i]
        root.lightsById = byId
        root.finishFetch(true)
      }
    }
  }

  Process {
    id: groupsProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.rooms = HueApi.parseGroups(text)
        root.finishFetch(true)
      }
    }
  }

  Process {
    id: actionProc
    onExited: function(exitCode) {
      if (root.pendingAction) {
        var command = root.pendingAction
        root.pendingAction = null
        root.runAction(command)
      }
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
          id: column
          width: scroll.width
          spacing: Style.space(12)

          Row {
            width: parent.width
            spacing: Style.space(10)

            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: "󰌵"
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.title
            }

            Column {
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(2)

              Text {
                text: "Hue Lights" + (root.currentThemeName ? " (" + root.currentThemeName + ")" : "")
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.title
                font.bold: true
              }

              Text {
                text: root.statusText
                color: Qt.darker(root.bar.foreground, 1.4)
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.caption
              }
            }

          }

          Rectangle {
            width: parent.width
            height: Style.spacing.hairline
            color: root.bar.foreground
            opacity: 0.12
          }

          Column {
            visible: root.config === null
            width: parent.width
            spacing: Style.space(8)

            Text {
              width: parent.width
              text: "No bridge configured yet."
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.body
              wrapMode: Text.WordWrap
            }

            Text {
              width: parent.width
              text: "Press the link button on your Hue bridge, then click below."
              color: Qt.darker(root.bar.foreground, 1.4)
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }

            Rectangle {
              width: parent.width
              height: pairButton.implicitHeight + Style.space(16)
              radius: Style.space(8)
              color: pairButtonMouse.containsMouse ? Qt.lighter(Color.accent, 1.2) : Color.accent

              Text {
                id: pairButton
                anchors.centerIn: parent
                text: "Pair with bridge"
                color: "#ffffff"
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.body
                font.bold: true
              }

              MouseArea {
                id: pairButtonMouse
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                hoverEnabled: true
                onClicked: {
                  var pairPath = Qt.resolvedUrl("pair.sh").toString().replace("file://", "")
                  Quickshell.execDetached(["omarchy-launch-terminal", "bash", pairPath])
                }
              }
            }
          }

          Row {
            visible: root.config !== null && root.loading && root.roomCount === 0 && root.orphanLights.length === 0
            spacing: Style.space(8)

            Text {
              text: "󰦖"
              color: Qt.darker(root.bar.foreground, 1.4)
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.body

              RotationAnimator on rotation {
                running: root.loading
                from: 0
                to: 360
                duration: 800
                loops: Animation.Infinite
              }
            }

            Text {
              text: "Loading…"
              color: Qt.darker(root.bar.foreground, 1.4)
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.body
            }
          }

          Text {
            visible: root.config !== null && root.lastFetchFailed && !root.loading
            width: parent.width
            text: "Couldn't reach the bridge. Check the bridge is on and the IP is still valid, then re-run pair.sh."
            color: Color.urgent
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Toggle {
            visible: root.config !== null && root.lightedRoomCount > 0
            width: parent.width
            label: "All lights"
            checked: root.allLightsOn
            foreground: root.bar.foreground
            accent: Color.accent
            fontFamily: root.bar.fontFamily
            onClicked: root.toggleAll(!root.allLightsOn)
          }

          Column {
            visible: root.config !== null && root.roomCount > 0
            width: parent.width
            spacing: Style.space(4)

            Repeater {
              model: root.roomsWithLights

              Column {
                required property var modelData
                width: parent.width
                spacing: Style.space(4)

                Toggle {
                  width: parent.width
                  label: modelData.name
                  description: modelData.lightCount + " light" + (modelData.lightCount === 1 ? "" : "s")
                  checked: modelData.on
                  foreground: root.bar.foreground
                  accent: Color.accent
                  fontFamily: root.bar.fontFamily
                  onClicked: root.toggleRoom(modelData.id, !modelData.on)
                }

                Repeater {
                  model: modelData.lights

                  Column {
                    id: lightRow
                    required property var modelData
                    width: parent.width
                    spacing: Style.space(2)

                    Toggle {
                      width: parent.width
                      label: modelData.name
                      titleSize: Style.font.body
                      checked: modelData.on
                      foreground: Qt.darker(root.bar.foreground, 1.2)
                      accent: Color.accent
                      fontFamily: root.bar.fontFamily
                      onClicked: root.toggleLight(modelData.id, !modelData.on)
                    }

                    Row {
                      visible: modelData.on && modelData.hasColor
                      width: parent.width - Style.space(24)
                      anchors.horizontalCenter: parent.horizontalCenter
                      spacing: Style.space(8)

                      PanelSlider {
                        width: parent.width - Style.space(30)
                        bar: root.bar
                        minimum: 1
                        maximum: 254
                        integer: true
                        step: 10
                        value: modelData.bri
                        onReleased: function(v) { root.setBrightness(modelData.id, v) }
                      }

                      Item {
                        width: Style.space(22)
                        height: Style.space(22)

                        Image {
                          anchors.fill: parent
                          source: Qt.resolvedUrl("hsv_wheel.png")
                          fillMode: Image.Stretch
                          smooth: true
                        }

                        Rectangle {
                          anchors.fill: parent
                          radius: Style.space(11)
                          border.width: modelData.pickerOpen ? 2 : 1
                          border.color: modelData.pickerOpen ? Color.accent : Qt.darker(root.bar.foreground, 1.6)
                          color: "transparent"
                        }

                        MouseArea {
                          anchors.fill: parent
                          cursorShape: Qt.PointingHandCursor
                          onClicked: root.toggleColorPicker(modelData.id)
                        }
                      }
                    }

                    Item {
                      id: colorPicker
                      visible: modelData.on && modelData.hasColor && modelData.pickerOpen
                      width: Style.space(180)
                      height: Style.space(180)
                      anchors.horizontalCenter: parent.horizontalCenter
                      property real dragHue: modelData.hue
                      property real dragSat: modelData.sat
                      property bool picking: false

                      Image {
                        anchors.fill: parent
                        source: Qt.resolvedUrl("hsv_wheel.png")
                        fillMode: Image.Stretch
                        smooth: true
                      }

                      Rectangle {
                        width: 12
                        height: 12
                        radius: 6
                        border.color: "#ffffff"
                        border.width: 2
                        color: "transparent"
                        x: colorPicker.width / 2
                           + Math.cos(-Math.PI / 2 + (colorPicker.dragHue / 65535) * 2 * Math.PI)
                             * (colorPicker.dragSat / 254) * (colorPicker.width / 2) - width / 2
                        y: colorPicker.height / 2
                           + Math.sin(-Math.PI / 2 + (colorPicker.dragHue / 65535) * 2 * Math.PI)
                             * (colorPicker.dragSat / 254) * (colorPicker.height / 2) - height / 2
                      }

                      MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor

                        function apply(x, y) {
                          var c = colorPicker.width / 2
                          var dx = x - c
                          var dy = y - c
                          var dist = Math.sqrt(dx * dx + dy * dy)
                          if (dist > c) return
                          var hue01 = (((Math.atan2(dy, dx) + Math.PI / 2) / (2 * Math.PI)) % 1 + 1) % 1
                          colorPicker.dragHue = Math.round(hue01 * 65535)
                          colorPicker.dragSat = Math.round((dist / c) * 254)
                        }

                        onPressed: function(mouse) {
                          colorPicker.picking = true
                          apply(mouse.x, mouse.y)
                        }
                        onPositionChanged: function(mouse) {
                          if (colorPicker.picking) apply(mouse.x, mouse.y)
                        }
                        onReleased: function(mouse) {
                          colorPicker.picking = false
                          root.setLightColor(modelData.id, colorPicker.dragHue, colorPicker.dragSat)
                        }
                      }
                    }

                    PanelSlider {
                      visible: modelData.on && modelData.hasCt
                      width: parent.width - Style.space(24)
                      anchors.horizontalCenter: parent.horizontalCenter
                      bar: root.bar
                      minimum: 153
                      maximum: 500
                      integer: true
                      step: 10
                      value: modelData.ct
                      onReleased: function(v) { root.setColorTemperature(modelData.id, v) }
                    }
                  }
                }
              }
            }
          }

          Column {
            visible: root.config !== null && root.orphanLights.length > 0
            width: parent.width
            spacing: Style.space(4)

            Text {
              text: "Other lights"
              color: Qt.darker(root.bar.foreground, 1.4)
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.caption
              font.letterSpacing: 1
              font.bold: true
            }

            Repeater {
              model: root.orphanLights

              Column {
                id: lightRow
                required property var modelData
                width: parent.width
                spacing: Style.space(2)

                Toggle {
                  width: parent.width
                  label: modelData.name
                  titleSize: Style.font.body
                  checked: modelData.on
                  foreground: Qt.darker(root.bar.foreground, 1.2)
                  accent: Color.accent
                  fontFamily: root.bar.fontFamily
                  onClicked: root.toggleLight(modelData.id, !modelData.on)
                }

                PanelSlider {
                  visible: modelData.on && modelData.hasBri
                  width: parent.width - Style.space(24)
                  anchors.horizontalCenter: parent.horizontalCenter
                  bar: root.bar
                  minimum: 1
                  maximum: 254
                  integer: true
                  step: 10
                  value: modelData.bri
                  onReleased: function(v) { root.setBrightness(modelData.id, v) }
                }

                Row {
                  visible: modelData.on && modelData.hasColor
                  width: parent.width - Style.space(24)
                  anchors.horizontalCenter: parent.horizontalCenter
                  spacing: Style.space(8)

                  PanelSlider {
                    width: parent.width - Style.space(30)
                    bar: root.bar
                    minimum: 1
                    maximum: 254
                    integer: true
                    step: 10
                    value: modelData.bri
                    onReleased: function(v) { root.setBrightness(modelData.id, v) }
                  }

                  Item {
                    width: Style.space(22)
                    height: Style.space(22)

                    Image {
                      anchors.fill: parent
                      source: Qt.resolvedUrl("hsv_wheel.png")
                      fillMode: Image.Stretch
                      smooth: true
                    }

                    Rectangle {
                      anchors.fill: parent
                      radius: Style.space(11)
                      border.width: modelData.pickerOpen ? 2 : 1
                      border.color: modelData.pickerOpen ? Color.accent : Qt.darker(root.bar.foreground, 1.6)
                      color: "transparent"
                    }

                    MouseArea {
                      anchors.fill: parent
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.toggleColorPicker(modelData.id)
                    }
                  }
                }

                Item {
                  id: colorPicker
                  visible: modelData.on && modelData.hasColor && modelData.pickerOpen
                  width: Style.space(180)
                  height: Style.space(180)
                  anchors.horizontalCenter: parent.horizontalCenter
                  property real dragHue: modelData.hue
                  property real dragSat: modelData.sat
                  property bool picking: false

                  Image {
                    anchors.fill: parent
                    source: Qt.resolvedUrl("hsv_wheel.png")
                    fillMode: Image.Stretch
                    smooth: true
                  }

                  Rectangle {
                    width: 12
                    height: 12
                    radius: 6
                    border.color: "#ffffff"
                    border.width: 2
                    color: "transparent"
                    x: colorPicker.width / 2
                       + Math.cos(-Math.PI / 2 + (colorPicker.dragHue / 65535) * 2 * Math.PI)
                         * (colorPicker.dragSat / 254) * (colorPicker.width / 2) - width / 2
                    y: colorPicker.height / 2
                       + Math.sin(-Math.PI / 2 + (colorPicker.dragHue / 65535) * 2 * Math.PI)
                         * (colorPicker.dragSat / 254) * (colorPicker.height / 2) - height / 2
                  }

                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor

                    function apply(x, y) {
                      var c = colorPicker.width / 2
                      var dx = x - c
                      var dy = y - c
                      var dist = Math.sqrt(dx * dx + dy * dy)
                      if (dist > c) return
                      var hue01 = (((Math.atan2(dy, dx) + Math.PI / 2) / (2 * Math.PI)) % 1 + 1) % 1
                      colorPicker.dragHue = Math.round(hue01 * 65535)
                      colorPicker.dragSat = Math.round((dist / c) * 254)
                    }

                    onPressed: function(mouse) {
                      colorPicker.picking = true
                      apply(mouse.x, mouse.y)
                    }
                    onPositionChanged: function(mouse) {
                      if (colorPicker.picking) apply(mouse.x, mouse.y)
                    }
                    onReleased: function(mouse) {
                      colorPicker.picking = false
                      root.setLightColor(modelData.id, colorPicker.dragHue, colorPicker.dragSat)
                    }
                  }
                }

                PanelSlider {
                  visible: modelData.on && modelData.hasCt
                  width: parent.width - Style.space(24)
                  anchors.horizontalCenter: parent.horizontalCenter
                  bar: root.bar
                  minimum: 153
                  maximum: 500
                  integer: true
                  step: 10
                  value: modelData.ct
                  onReleased: function(v) { root.setColorTemperature(modelData.id, v) }
                }
              }
            }
          }

          Text {
            visible: root.config !== null && !root.loading && !root.lastFetchFailed && root.roomCount === 0 && root.orphanLights.length === 0
            text: "No lights found on this bridge."
            color: Qt.darker(root.bar.foreground, 1.4)
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }
    }
  }
}
