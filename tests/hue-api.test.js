const test = require("node:test")
const assert = require("node:assert/strict")
const HueApi = require("../HueApi.js")

test("isValidIp", () => {
  assert.equal(HueApi.isValidIp("192.168.1.1"), true)
  assert.equal(HueApi.isValidIp("0.0.0.0"), true)
  assert.equal(HueApi.isValidIp(""), false)
  assert.equal(HueApi.isValidIp("192.168.1"), false)
  assert.equal(HueApi.isValidIp("192.168.1.1.1"), false)
  assert.equal(HueApi.isValidIp("not.an.ip.addr"), false)
})

test("isValidId accepts hyphenated Hue usernames", () => {
  assert.equal(HueApi.isValidId("abc-123_XYZ"), true)
  assert.equal(HueApi.isValidId("a".repeat(40)), true)
})

test("isValidId rejects empty, oversized, or invalid-character ids", () => {
  assert.equal(HueApi.isValidId(""), false)
  assert.equal(HueApi.isValidId("a".repeat(41)), false)
  assert.equal(HueApi.isValidId("has space"), false)
  assert.equal(HueApi.isValidId("has/slash"), false)
})

test("parseConfig accepts a well-formed config", () => {
  const cfg = HueApi.parseConfig(JSON.stringify({
    bridgeIp: "192.168.1.50", username: "abc-123", bridgeId: "AABBCC"
  }))
  assert.deepEqual(cfg, { bridgeIp: "192.168.1.50", username: "abc-123", bridgeId: "aabbcc" })
})

test("parseConfig rejects missing or invalid fields", () => {
  assert.equal(HueApi.parseConfig(""), null)
  assert.equal(HueApi.parseConfig("not json"), null)
  assert.equal(HueApi.parseConfig(JSON.stringify({ bridgeIp: "bad", username: "abc" })), null)
  assert.equal(HueApi.parseConfig(JSON.stringify({ bridgeIp: "1.2.3.4", username: "" })), null)
})

test("parseConfig drops an invalid bridgeId but keeps the rest", () => {
  const cfg = HueApi.parseConfig(JSON.stringify({
    bridgeIp: "1.2.3.4", username: "abc", bridgeId: "has space"
  }))
  assert.deepEqual(cfg, { bridgeIp: "1.2.3.4", username: "abc", bridgeId: "" })
})

test("parseGroups keeps only Room/Zone types and sorts by name", () => {
  const groups = HueApi.parseGroups(JSON.stringify({
    "1": { name: "Zeta Room", type: "Room", lights: ["1"], action: { bri: 120 } },
    "2": { name: "Not a room", type: "LightGroup", lights: ["2"], action: { bri: 50 } },
    "3": { name: "Alpha Zone", type: "Zone", lights: [], action: { bri: 60 } }
  }))
  assert.equal(groups.length, 2)
  assert.equal(groups[0].name, "Alpha Zone")
  assert.equal(groups[1].name, "Zeta Room")
})

test("parseGroups exposes group brightness clamped to Hue's valid range", () => {
  const groups = HueApi.parseGroups(JSON.stringify({
    "1": { name: "Over", type: "Room", lights: ["1"], action: { bri: 999 } },
    "2": { name: "Under", type: "Room", lights: ["1"], action: { bri: 0 } },
    "3": { name: "Missing", type: "Room", lights: ["1"] }
  }))
  const byName = Object.fromEntries(groups.map(g => [g.name, g]))
  assert.equal(byName.Over.bri, 254)
  assert.equal(byName.Under.bri, 1)
  assert.equal(byName.Missing.bri, 254)
})

test("parseGroups reports on/off from state.any_on, not action.on", () => {
  const groups = HueApi.parseGroups(JSON.stringify({
    "1": { name: "Room", type: "Room", lights: ["1"], state: { any_on: true, all_on: false }, action: { on: false } }
  }))
  assert.equal(groups[0].on, true)
  assert.equal(groups[0].allOn, false)
})

test("parseGroups passes through the bridge's class field, defaulting to Other", () => {
  const groups = HueApi.parseGroups(JSON.stringify({
    "1": { name: "Office", type: "Room", lights: ["1"], class: "Office" },
    "2": { name: "Mystery", type: "Room", lights: ["1"] }
  }))
  const byName = Object.fromEntries(groups.map(g => [g.name, g]))
  assert.equal(byName.Office.class, "Office")
  assert.equal(byName.Mystery.class, "Other")
})

test("roomIcon returns a mapped glyph for a known class", () => {
  const bedroomIcon = HueApi.roomIcon("Bedroom")
  const defaultIcon = HueApi.roomIcon("Other")
  assert.notEqual(bedroomIcon, defaultIcon)
  assert.equal(typeof bedroomIcon, "string")
  assert.ok(bedroomIcon.length > 0)
})

test("roomIcon falls back to the default glyph for unknown or missing classes", () => {
  const defaultIcon = HueApi.roomIcon("Other")
  assert.equal(HueApi.roomIcon("Something Hue never sends"), defaultIcon)
  assert.equal(HueApi.roomIcon(undefined), defaultIcon)
  assert.equal(HueApi.roomIcon(""), defaultIcon)
})

test("parseScenes keeps only scenes tied to a group and sorts by name", () => {
  const scenes = HueApi.parseScenes(JSON.stringify({
    "s2": { name: "Zen", type: "GroupScene", group: "1" },
    "s1": { name: "Bright", type: "GroupScene", group: "1" },
    "s3": { name: "Ungrouped", type: "LightScene", lights: ["1", "2"] }
  }))
  assert.deepEqual(scenes, [
    { id: "s1", name: "Bright", group: "1" },
    { id: "s2", name: "Zen", group: "1" }
  ])
})

test("parseScenes returns an empty list for empty/malformed input", () => {
  assert.deepEqual(HueApi.parseScenes(""), [])
  assert.deepEqual(HueApi.parseScenes("not json"), [])
})

test("roomBrightness averages the actual state.bri of a room's lights", () => {
  const text = JSON.stringify({
    "1": { state: { bri: 100 } },
    "2": { state: { bri: 200 } },
    "3": { state: { bri: 50 } } // not in the room, should be ignored
  })
  assert.equal(HueApi.roomBrightness(text, ["1", "2"]), 150)
})

test("roomBrightness clamps to Hue's valid range and skips lights without bri", () => {
  const text = JSON.stringify({
    "1": { state: { bri: 999 } },
    "2": { state: { on: true } } // no bri (on/off-only light), ignored
  })
  assert.equal(HueApi.roomBrightness(text, ["1", "2"]), 254)
})

test("roomBrightness returns null when there's nothing usable", () => {
  assert.equal(HueApi.roomBrightness(JSON.stringify({}), ["1"]), null)
  assert.equal(HueApi.roomBrightness("", ["1"]), null)
  assert.equal(HueApi.roomBrightness(JSON.stringify({ "1": { state: { bri: 10 } } }), []), null)
})
