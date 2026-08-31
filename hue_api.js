var API = typeof Qt !== "undefined"
  ? Qt.resolvedUrl("hue_api.py").toString().replace("file://", "")
  : "hue_api.py"

function apiCmd(args) {
  var cmd = ["python3", API]
  for (var i = 0; i < args.length; i++) cmd.push(String(args[i]))
  return cmd
}

function isValidId(id) {
  return /^[a-zA-Z0-9_-]{1,40}$/.test(String(id))
}

// A malicious/compromised bridge shouldn't be able to force unbounded
// memory use or slow the panel to a crawl -- cap the raw text a bridge
// response can be before it's even handed to JSON.parse, and cap how many
// rooms/scenes/lights get parsed out of it below.
var MAX_JSON_TEXT_LENGTH = 262144
var MAX_PARSED_ITEMS = 500
var MAX_NAME_LENGTH = 200

// Room/scene names render through QML Text elements we don't all control
// directly -- some flow into shell-provided components (e.g. Toggle.label)
// whose internal Text has no textFormat override and defaults to
// Text.AutoText, which would interpret markup-like content as rich text.
// Stripping angle brackets at the source means it's inert wherever it's
// rendered, not just in the Text elements we happen to have hardened.
function sanitizeName(name) {
  return String(name).replace(/[<>]/g, "").slice(0, MAX_NAME_LENGTH)
}

function parseStatus(text) {
  var obj = parseJsonObject(text)
  if (!obj) return null
  var bridgeId = String(obj.bridgeId || "").trim().toLowerCase()
  if (bridgeId && !isValidId(bridgeId)) bridgeId = ""
  return { paired: !!obj.paired, bridgeId: bridgeId }
}

function parseJsonObject(text) {
  var raw = String(text || "").trim()
  if (!raw || raw.length > MAX_JSON_TEXT_LENGTH) return null
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
  var seen = 0
  for (var id in obj) {
    if (!Object.prototype.hasOwnProperty.call(obj, id)) continue
    if (seen >= MAX_PARSED_ITEMS) break
    seen++
    if (!isValidId(id)) continue
    var group = obj[id]
    var type = String(group.type || "")
    if (type !== "Room" && type !== "Zone") continue
    var action = group.action || {}
    var bri = typeof action.bri === "number" ? action.bri : 254
    var lightIds = Array.isArray(group.lights)
      ? group.lights.slice(0, MAX_PARSED_ITEMS).map(String).filter(isValidId)
      : []
    groups.push({
      id: String(id),
      name: sanitizeName(group.name || "Group " + id),
      type: type,
      class: String(group.class || "Other").slice(0, MAX_NAME_LENGTH),
      on: !!(group.state && group.state.any_on),
      allOn: !!(group.state && group.state.all_on),
      bri: Math.max(1, Math.min(254, bri)),
      lightIds: lightIds
    })
  }
  groups.sort(function(a, b) { return a.name.localeCompare(b.name) })
  return groups
}

function parseScenes(text) {
  var obj = parseJsonObject(text)
  if (!obj) return []
  var scenes = []
  var seen = 0
  for (var id in obj) {
    if (!Object.prototype.hasOwnProperty.call(obj, id)) continue
    if (seen >= MAX_PARSED_ITEMS) break
    seen++
    if (!isValidId(id)) continue
    var scene = obj[id]
    var group = scene.group !== undefined && scene.group !== null ? String(scene.group) : ""
    if (!group || !isValidId(group)) continue
    scenes.push({
      id: String(id),
      name: sanitizeName(scene.name || "Scene " + id),
      group: group
    })
  }
  scenes.sort(function(a, b) { return a.name.localeCompare(b.name) })
  return scenes
}

// Nerd Font glyphs verified against the installed font (a reduced "basic"
// build, not the full Material Design Icons set) by rendering each
// candidate codepoint and checking it visually -- most guessed codepoints
// turned out to be missing or wrong glyphs, so this only maps classes with
// a confirmed match. Everything else falls back to the plugin's own bulb
// icon, which every room already shows regardless.
var ROOM_CLASS_ICONS = {
  "Bedroom": "",
  "Kids bedroom": "",
  "Guest room": "",
  "Bathroom": "",
  "Toilet": "",
  "Office": "",
  "Computer": "",
  "Garden": "",
  "Balcony": "",
  "Terrace": "",
  "Porch": "",
  "Driveway": "",
  "Carport": "",
  "Garage": "",
  "TV": "",
  "Reading": "",
  "Storage": "",
  "Closet": "",
  "Home": "",
  "Barbecue": "",
  "Music": "",
  "Gym": "",
  "Nursery": ""
}
var ROOM_ICON_DEFAULT = "󰌵"

function roomIcon(className) {
  return ROOM_CLASS_ICONS[String(className || "")] || ROOM_ICON_DEFAULT
}

// Sorts `items` (each with an `id`) by position in `orderIds`, appending
// anything not listed at the end in its original order. `orderIds` is
// filtered down to ids actually present in `items` first, so stale ids
// (a room/scene since deleted on the bridge) don't inject phantom entries.
function applyOrder(items, orderIds) {
  var known = {}
  for (var i = 0; i < items.length; i++) known[items[i].id] = true
  var order = Array.isArray(orderIds) ? orderIds.filter(function(id) { return known[id] }) : []
  var rank = {}
  for (var j = 0; j < order.length; j++) rank[order[j]] = j
  var ranked = items.map(function(item, idx) {
    return { item: item, rank: Object.prototype.hasOwnProperty.call(rank, item.id) ? rank[item.id] : order.length + idx }
  })
  ranked.sort(function(a, b) { return a.rank - b.rank })
  return ranked.map(function(r) { return r.item })
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
    isValidId: isValidId,
    parseStatus: parseStatus,
    parseJsonObject: parseJsonObject,
    parseGroups: parseGroups,
    parseScenes: parseScenes,
    roomIcon: roomIcon,
    applyOrder: applyOrder,
    roomBrightness: roomBrightness
  }
}
