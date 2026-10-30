import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_HOLD_MINUTES,
  installMicKeeper,
  parseHoldMinutes,
} from "../dist/mic-keeper.js";

// A track whose clones share one source, like a real capture: the source ends
// when its last track is stopped.
class FakeSource {
  tracks = new Set();
  get live() {
    return this.tracks.size > 0;
  }
}

class FakeTrack extends EventTarget {
  constructor(source) {
    super();
    this.source = source;
    this.readyState = "live";
    this.muted = false;
    this.enabled = true;
    source.tracks.add(this);
  }
  clone() {
    return new FakeTrack(this.source);
  }
  stop() {
    this.readyState = "ended";
    this.source.tracks.delete(this);
  }
}

globalThis.MediaStream ??= class {
  constructor(tracks) {
    this.tracks = tracks;
  }
  getAudioTracks() {
    return this.tracks;
  }
  getTracks() {
    return this.tracks;
  }
};
globalThis.DOMException ??= class extends Error {};

function setup(minutes = 30) {
  const sources = [];
  const calls = [];
  const mediaDevices = {
    getUserMedia(constraints) {
      calls.push(constraints);
      const source = new FakeSource();
      sources.push(source);
      return Promise.resolve(new MediaStream([new FakeTrack(source)]));
    },
  };
  const pageEvents = new EventTarget();
  let holdMinutes = minutes;
  const keeper = installMicKeeper(mediaDevices, () => holdMinutes, pageEvents);
  return {
    mediaDevices,
    calls,
    sources,
    pageEvents,
    keeper,
    setHold: (value) => {
      holdMinutes = value;
    },
  };
}

const stopAll = (stream) => stream.getTracks().forEach((track) => track.stop());

test("a second dictation reuses the capture and does not call getUserMedia again", async () => {
  const t = setup();
  const first = await t.mediaDevices.getUserMedia({ audio: { echoCancellation: true } });
  stopAll(first);
  assert.equal(t.calls.length, 1);
  assert.equal(t.sources[0].live, true, "the capture stays open after the caller stops its track");
  const second = await t.mediaDevices.getUserMedia({ audio: { echoCancellation: true } });
  assert.equal(t.calls.length, 1);
  assert.equal(second.getAudioTracks()[0].readyState, "live");
  assert.equal(second.getAudioTracks()[0].enabled, true);
  stopAll(second);
  t.keeper.dispose();
  assert.equal(t.sources[0].live, false);
});

test("different audio constraints make a new capture, and the old one is released", async () => {
  const t = setup();
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  stopAll(await t.mediaDevices.getUserMedia({ audio: { deviceId: { exact: "mic-2" } } }));
  assert.equal(t.calls.length, 2);
  assert.equal(t.sources[0].live, false);
  assert.equal(t.sources[1].live, true);
  t.keeper.dispose();
});

test("concurrent requests share one getUserMedia call", async () => {
  const t = setup();
  const [a, b] = await Promise.all([
    t.mediaDevices.getUserMedia({ audio: true }),
    t.mediaDevices.getUserMedia({ audio: true }),
  ]);
  assert.equal(t.calls.length, 1);
  assert.notEqual(a.getAudioTracks()[0], b.getAudioTracks()[0]);
  stopAll(a);
  assert.equal(t.sources[0].live, true);
  t.keeper.dispose();
});

test("video requests and empty requests pass through untouched", async () => {
  const t = setup();
  stopAll(await t.mediaDevices.getUserMedia({ video: true }));
  stopAll(await t.mediaDevices.getUserMedia({ audio: true, video: true }));
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  stopAll(await t.mediaDevices.getUserMedia({ video: true }));
  assert.equal(t.calls.length, 4);
  assert.equal(t.sources[0].live, false);
  assert.equal(t.sources[1].live, false);
  t.keeper.dispose();
});

test("an ended or muted capture is replaced by a new getUserMedia call", async () => {
  const t = setup();
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  [...t.sources[0].tracks][0].muted = true;
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  assert.equal(t.calls.length, 2);
  [...t.sources[1].tracks][0].stop();
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  assert.equal(t.calls.length, 3);
  t.keeper.dispose();
});

test("the capture is released after the hold time without a caller", async (context) => {
  context.mock.timers.enable({ apis: ["setTimeout"] });
  const t = setup(10);
  const stream = await t.mediaDevices.getUserMedia({ audio: true });
  context.mock.timers.tick(60 * 60_000);
  assert.equal(t.sources[0].live, true, "kept while a caller still holds a track");
  stopAll(stream);
  context.mock.timers.tick(9 * 60_000);
  assert.equal(t.sources[0].live, true);
  context.mock.timers.tick(60_000);
  assert.equal(t.sources[0].live, false);
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  assert.equal(t.calls.length, 2);
  t.keeper.dispose();
});

test("a new request cancels the idle release", async (context) => {
  context.mock.timers.enable({ apis: ["setTimeout"] });
  const t = setup(10);
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  context.mock.timers.tick(9 * 60_000);
  const again = await t.mediaDevices.getUserMedia({ audio: true });
  context.mock.timers.tick(60 * 60_000);
  assert.equal(t.sources[0].live, true);
  stopAll(again);
  t.keeper.dispose();
});

test("a hold time of 0 turns the keeper off; the setting is read on every call", async () => {
  const t = setup(0);
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  assert.equal(t.sources[0].live, false);
  t.setHold(5);
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  assert.equal(t.sources[1].live, true);
  t.keeper.dispose();
});

test("a failed getUserMedia is passed on and nothing is kept", async () => {
  let calls = 0;
  const mediaDevices = {
    getUserMedia() {
      calls += 1;
      return Promise.reject(new Error("NotAllowedError"));
    },
  };
  const keeper = installMicKeeper(mediaDevices, () => 30, new EventTarget());
  await assert.rejects(mediaDevices.getUserMedia({ audio: true }), /NotAllowedError/u);
  await assert.rejects(mediaDevices.getUserMedia({ audio: true }), /NotAllowedError/u);
  assert.equal(calls, 2);
  keeper.dispose();
});

test("pagehide releases the capture unless the page goes to the back/forward cache", async () => {
  const t = setup();
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  t.pageEvents.dispatchEvent(Object.assign(new Event("pagehide"), { persisted: true }));
  assert.equal(t.sources[0].live, true);
  t.pageEvents.dispatchEvent(Object.assign(new Event("pagehide"), { persisted: false }));
  assert.equal(t.sources[0].live, false);
  t.keeper.dispose();
});

test("dispose puts the original getUserMedia back", async () => {
  const t = setup();
  const patched = t.mediaDevices.getUserMedia;
  t.keeper.dispose();
  assert.notEqual(t.mediaDevices.getUserMedia, patched);
  stopAll(await t.mediaDevices.getUserMedia({ audio: true }));
  assert.equal(t.sources[0].live, false);
});

test("parseHoldMinutes", () => {
  assert.equal(parseHoldMinutes(null), DEFAULT_HOLD_MINUTES);
  assert.equal(parseHoldMinutes(""), DEFAULT_HOLD_MINUTES);
  assert.equal(parseHoldMinutes("abc"), DEFAULT_HOLD_MINUTES);
  assert.equal(parseHoldMinutes("0"), 0);
  assert.equal(parseHoldMinutes("120"), 120);
  assert.equal(parseHoldMinutes("-1"), -1);
});
