import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { RadioControl } from "../../src/js/services/radio-control.js";
import { Capacitor } from "@capacitor/core";

vi.mock("@capacitor/core", () => ({
  Capacitor: {
    isNativePlatform: vi.fn(),
  },
}));

describe("RadioControl", () => {
  let mockWebSocketInstance;

  function connectOpenControl(url = "ws://example.com/") {
    const rc = new RadioControl();
    rc.connect(url);
    rc.ws.readyState = WebSocket.OPEN;
    return rc;
  }

  function receiveEvent(rc, event, data) {
    rc.ws.onmessage({
      data: JSON.stringify({ event, data }),
    });
  }

  function expectSentEvent(expected) {
    expect(mockWebSocketInstance.send).toHaveBeenCalledWith(
      JSON.stringify(expected),
    );
  }

  beforeEach(() => {
    vi.useFakeTimers();
    mockWebSocketInstance = {
      readyState: WebSocket.CONNECTING,
      close: vi.fn(),
      send: vi.fn(),
    };
    vi.stubGlobal(
      "WebSocket",
      vi.fn(function (url) {
        this.url = url;
        Object.assign(this, mockWebSocketInstance);
        return this;
      }),
    );
    Capacitor.isNativePlatform.mockReturnValue(false);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it.each([
    [
      "uses an absolute browser override",
      "ws://localhost:8080",
      false,
      "ws://remote-server:9000/player/foo?token=123",
      "ws://localhost:8080/player/foo?token=123",
    ],
    [
      "resolves a same-origin browser override",
      "/switchboard",
      false,
      "ws://remote-server:9000/switchboard/player/foo?token=123",
      "ws://localhost:3000/switchboard/player/foo?token=123",
    ],
    [
      "ignores browser overrides on native platforms",
      "ws://localhost:8080",
      true,
      "ws://remote-server:9000/player/foo?token=123",
      "ws://remote-server:9000/player/foo?token=123",
    ],
  ])("%s", (_case, override, isNative, input, expected) => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", override);
    Capacitor.isNativePlatform.mockReturnValue(isNative);
    const rc = new RadioControl();

    rc.connect(input);

    expect(global.WebSocket).toHaveBeenCalledWith(expected);
  });

  it.each([
    [
      "playback_start",
      (rc) => rc.startPlayback("WXXI"),
      { event: "playback_start", data: { call_sign: "WXXI" } },
    ],
    [
      "playback_stop",
      (rc) => rc.stopPlayback(),
      { event: "playback_stop", data: null },
    ],
  ])("sends %s when connected", (_event, sendCommand, expected) => {
    const rc = connectOpenControl();

    sendCommand(rc);

    expectSentEvent(expected);
  });

  it("sends error event if sending request while disconnected", () => {
    const rc = new RadioControl();
    const errorSpy = vi.fn();
    rc.addEventListener("error", errorSpy);

    rc.startPlayback("WXXI");

    expect(errorSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        detail: "WebSocket not connected. Cannot send playback_start command.",
      }),
    );
  });

  it.each([
    [
      "playback_state",
      {
        call_sign: "WXXI",
        requested_call_sign: "KEXP",
        failed_call_sign: "LOFI",
      },
      "playbackstate",
      {
        callSign: "WXXI",
        requestedCallSign: "KEXP",
        failedCallSign: "LOFI",
      },
    ],
    [
      "radio_dial_url",
      "https://example.test/radio-dial.json",
      "radiodialurl",
      "https://example.test/radio-dial.json",
    ],
    [
      "player_presence",
      { player_id: "living-room", connected: true },
      "playerpresence",
      { player_id: "living-room", connected: true },
    ],
    [
      "player_status",
      { scope: "playback", level: "ok" },
      "playerstatus",
      { scope: "playback", level: "ok" },
    ],
  ])("maps %s messages to UI events", (message, data, event, expected) => {
    const rc = new RadioControl();
    const listener = vi.fn();
    rc.addEventListener(event, listener);
    rc.connect("ws://example.com/");

    receiveEvent(rc, message, data);

    expect(listener).toHaveBeenCalledWith(
      expect.objectContaining({ detail: expected }),
    );
  });

  it("reports malformed socket messages", () => {
    const rc = new RadioControl();
    const listener = vi.fn();
    rc.addEventListener("error", listener);
    rc.connect("ws://example.com/");

    rc.ws.onmessage({ data: "not-json" });

    expect(listener).toHaveBeenCalledWith(
      expect.objectContaining({ detail: "Error parsing WebSocket message." }),
    );
  });
});
