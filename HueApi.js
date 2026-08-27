var API = typeof Qt !== "undefined"
  ? Qt.resolvedUrl("hue-api.py").toString().replace("file://", "")
  : "hue-api.py"

function apiCmd(args) {
  var cmd = ["python3", API]
  for (var i = 0; i < args.length; i++) cmd.push(String(args[i]))
  return cmd
}

function isValidIp(ip) {
  return /^(\d{1,3}\.){3}\d{1,3}$/.test(ip)
}

function isValidId(id) {
  return /^[a-zA-Z0-9_-]{1,40}$/.test(String(id))
}

function parseConfig(text) {
  var raw = String(text || "").trim()
  if (!raw) return null
  try {
    var parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object") return null
    var bridgeIp = String(parsed.bridgeIp || "").trim()
    var username = String(parsed.username || "").trim()
    var bridgeId = String(parsed.bridgeId || "").trim().toLowerCase()
    if (!bridgeIp || !isValidIp(bridgeIp)) return null
    if (!username || !isValidId(username)) return null
    if (bridgeId && !isValidId(bridgeId)) bridgeId = ""
    return { bridgeIp: bridgeIp, username: username, bridgeId: bridgeId }
  } catch (e) {
    return null
  }
}

function parseJsonObject(text) {
  var raw = String(text || "").trim()
  if (!raw) return null
  try {
    var parsed = JSON.parse(raw)
    return parsed && typeof parsed === "object" ? parsed : null
  } catch (e) {
    return null
  }
}

function parseGroups(text) {
  var obj = parseJsonObject(text)
  if (!obj) return []
  var groups = []
  for (var id in obj) {
    if (!Object.prototype.hasOwnProperty.call(obj, id)) continue
    var group = obj[id]
    var type = String(group.type || "")
    if (type !== "Room" && type !== "Zone") continue
    var action = group.action || {}
    var bri = typeof action.bri === "number" ? action.bri : 254
    groups.push({
      id: String(id),
      name: String(group.name || "Group " + id),
      type: type,
      on: !!(group.state && group.state.any_on),
      allOn: !!(group.state && group.state.all_on),
      bri: Math.max(1, Math.min(254, bri)),
      lightIds: Array.isArray(group.lights) ? group.lights.map(String) : []
    })
  }
  groups.sort(function(a, b) { return a.name.localeCompare(b.name) })
  return groups
}

function parseScenes(text) {
  var obj = parseJsonObject(text)
  if (!obj) return []
  var scenes = []
  for (var id in obj) {
    if (!Object.prototype.hasOwnProperty.call(obj, id)) continue
    var scene = obj[id]
    var group = scene.group !== undefined && scene.group !== null ? String(scene.group) : ""
    if (!group) continue
    scenes.push({
      id: String(id),
      name: String(scene.name || "Scene " + id),
      group: group
    })
  }
  scenes.sort(function(a, b) { return a.name.localeCompare(b.name) })
  return scenes
}

function roomBrightness(text, lightIds) {
  var obj = parseJsonObject(text)
  if (!obj || !lightIds || lightIds.length === 0) return null
  var total = 0
  var count = 0
  for (var i = 0; i < lightIds.length; i++) {
    var light = obj[lightIds[i]]
    if (light && light.state && typeof light.state.bri === "number") {
      total += light.state.bri
      count++
    }
  }
  if (count === 0) return null
  return Math.max(1, Math.min(254, Math.round(total / count)))
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    apiCmd: apiCmd,
    isValidIp: isValidIp,
    isValidId: isValidId,
    parseConfig: parseConfig,
    parseJsonObject: parseJsonObject,
    parseGroups: parseGroups,
    parseScenes: parseScenes,
    roomBrightness: roomBrightness
  }
}
