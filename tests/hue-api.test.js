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

test("parseLights clamps bri/ct to Hue's valid ranges and flags capabilities", () => {
  const lights = HueApi.parseLights(JSON.stringify({
    "2": { name: "Lamp", state: { on: true, bri: 999, ct: 50, hue: 100, sat: 200 } },
    "1": { name: "Bulb", state: { on: false } }
  }))
  assert.equal(lights.length, 2)
  // sorted by name: Bulb before Lamp
  assert.equal(lights[0].name, "Bulb")
  assert.equal(lights[0].hasBri, false)
  assert.equal(lights[0].hasColor, false)
  assert.equal(lights[1].name, "Lamp")
  assert.equal(lights[1].bri, 254) // clamped from 999
  assert.equal(lights[1].ct, 153) // clamped from 50
  assert.equal(lights[1].hasColor, true)
})

test("parseGroups keeps only Room/Zone types and sorts by name", () => {
  const groups = HueApi.parseGroups(JSON.stringify({
    "1": { name: "Zeta Room", type: "Room", lights: ["1"] },
    "2": { name: "Not a room", type: "LightGroup", lights: ["2"] },
    "3": { name: "Alpha Zone", type: "Zone", lights: [] }
  }))
  assert.equal(groups.length, 2)
  assert.equal(groups[0].name, "Alpha Zone")
  assert.equal(groups[1].name, "Zeta Room")
})

test("roomLights looks up lights by id and skips ones not found", () => {
  const byId = { "1": { id: "1", name: "A" } }
  const room = { lightIds: ["1", "missing"] }
  const lights = HueApi.roomLights(room, byId)
  assert.deepEqual(lights, [{ id: "1", name: "A" }])
})
