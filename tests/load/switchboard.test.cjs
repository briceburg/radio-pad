const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

// Replace k6 imports with deterministic socket/timer adapters; execute the actual workload.
const workload = readFileSync(join(__dirname, "switchboard.js"), "utf8")
  .replace(/^import .*;\n/gm, "")
  .replace(/^export /gm, "");

function room() {
  const sockets = [];
  const timers = [];
  const intervals = new Set();
  class Socket {
    static OPEN = 1;
    readyState = Socket.OPEN;
    handlers = {};
    sent = [];
    constructor() {
      sockets.push(this);
    }
    addEventListener(event, callback) {
      this.handlers[event] = callback;
    }
    send(message) {
      this.sent.push(JSON.parse(message));
    }
    close() {
      this.readyState = 3;
      this.handlers.close();
    }
  }
  class Metric {
    add() {}
  }
  runInNewContext(`${workload}\nopenRoom(0, 0);`, {
    __ENV: {
      REGISTRY_URL: "http://localhost/api",
      SWITCHBOARD_URL: "ws://localhost/switchboard",
    },
    Counter: Metric,
    Rate: Metric,
    Trend: Metric,
    WebSocket: Socket,
    setTimeout: (callback) => timers.push(callback),
    setInterval: (callback) => {
      intervals.add(callback);
      return callback;
    },
    clearInterval: (callback) => intervals.delete(callback),
  });
  return {
    sockets,
    intervals,
    advance: () => timers.shift()(),
    open: () => {
      sockets[0].handlers.open();
      sockets[1].handlers.open();
    },
    authenticate: () =>
      sockets[1].handlers.message({
        data: JSON.stringify({ event: "authenticated", data: {} }),
      }),
  };
}

test("traffic starts after authentication and stops before draining", () => {
  const run = room();
  run.open();
  assert.equal(run.intervals.size, 0);
  run.authenticate();
  assert.equal(run.intervals.size, 1);
  assert.equal(run.sockets[0].sent[0].event, "playback_state");
  run.advance();
  assert.equal(run.intervals.size, 0);
  run.advance();
  assert.ok(run.sockets.every((socket) => socket.readyState === 3));
});

for (const afterClose of [false, true]) {
  test(`late authentication cannot start traffic ${afterClose ? "after close" : "during drain"}`, () => {
    const run = room();
    run.open();
    run.advance();
    if (afterClose) run.advance();
    run.authenticate();
    assert.equal(run.intervals.size, 0);
    assert.equal(run.sockets[0].sent.length, 0);
  });
}

test("a late player handshake cannot create controllers after shutdown", () => {
  const run = room();
  run.advance();
  run.advance();
  run.sockets[0].handlers.open();
  assert.equal(run.sockets.length, 1);
  assert.equal(run.intervals.size, 0);
});
