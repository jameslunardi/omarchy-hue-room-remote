function isValidIp(ip) {
  return /^(\d{1,3}\.){3}\d{1,3}$/.test(ip)
}

function isValidId(id) {
  return /^[a-f0-9]{1,40}$/i.test(String(id))
}

function parseConfig(text) {
  var raw = String(text || "").trim()
  if (!raw) return null
  try {
    var parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object") return null
    var bridgeIp = String(parsed.bridgeIp || "").trim()
    var username = String(parsed.username || "").trim()
    if (!bridgeIp || !isValidIp(bridgeIp)) return null
    if (!username || !isValidId(username)) return null
    return { bridgeIp: bridgeIp, username: username }
  } catch (e) {
    return null
  }
}

function curlGet(url) {
  return ["curl", "-fsSk", "--max-time", "5", url]
}

function curlPutJson(url, body) {
  return ["curl", "-fsSk", "--max-time", "5", "-X", "PUT",
    "-H", "Content-Type: application/json",
    "-d", body, url]
}

function lightsUrl(config) {
  return "https://" + config.bridgeIp + "/api/" + config.username + "/lights"
}

function groupsUrl(config) {
  return "https://" + config.bridgeIp + "/api/" + config.username + "/groups"
}

function lightStateUrl(config, lightId) {
  return "https://" + config.bridgeIp + "/api/" + config.username
    + "/lights/" + encodeURIComponent(lightId) + "/state"
}

function groupActionUrl(config, groupId) {
  return "https://" + config.bridgeIp + "/api/" + config.username
    + "/groups/" + encodeURIComponent(groupId) + "/action"
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

function parseLights(text) {
  var obj = parseJsonObject(text)
  if (!obj) return []
  var lights = []
  for (var id in obj) {
    if (!Object.prototype.hasOwnProperty.call(obj, id)) continue
    var light = obj[id]
    var state = light.state || {}
    var hasBri = typeof state.bri === "number"
    var hasCt = typeof state.ct === "number"
    var hasColor = typeof state.hue === "number" && typeof state.sat === "number"
    lights.push({
      id: String(id),
      name: String(light.name || "Light " + id),
      on: !!state.on,
      bri: hasBri ? Math.max(1, Math.min(254, state.bri)) : 0,
      hasBri: hasBri,
      ct: hasCt ? Math.max(153, Math.min(500, state.ct)) : 0,
      hasCt: hasCt,
      hue: hasColor ? state.hue : 0,
      sat: hasColor ? state.sat : 0,
      hasColor: hasColor,
      pickerOpen: false
    })
  }
  lights.sort(function(a, b) { return a.name.localeCompare(b.name) })
  return lights
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
    groups.push({
      id: String(id),
      name: String(group.name || "Group " + id),
      type: type,
      on: !!(group.state && group.state.any_on),
      allOn: !!(group.state && group.state.all_on),
      lightIds: Array.isArray(group.lights) ? group.lights.map(String) : []
    })
  }
  groups.sort(function(a, b) { return a.name.localeCompare(b.name) })
  return groups
}

function roomLights(room, byId) {
  var result = []
  for (var i = 0; i < room.lightIds.length; i++) {
    var light = byId[room.lightIds[i]]
    if (light) result.push(light)
  }
  return result
}
