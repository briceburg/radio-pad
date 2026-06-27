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
    global.WebSocket = vi.fn(function (url) {
      this.url = url;
      Object.assign(this, mockWebSocketInstance);
      return this;
    });
    Capacitor.isNativePlatform.mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("resolves switchboard URL override correctly in browser mode", () => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", "ws://localhost:8080");
    const rc = new RadioControl();

    rc.connect("ws://remote-server:9000/player/foo?token=123");

    expect(global.WebSocket).toHaveBeenCalledWith(
      "ws://localhost:8080/player/foo?token=123",
    );
  });

  it("resolves same-origin switchboard overrides correctly in browser mode", () => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", "/switchboard");
    const rc = new RadioControl();

    rc.connect("ws://remote-server:9000/switchboard/player/foo?token=123");

    expect(global.WebSocket).toHaveBeenCalledWith(
      "ws://localhost:3000/switchboard/player/foo?token=123",
    );
  });

  it("connect ignores override in native platform", () => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", "ws://localhost:8080");
    Capacitor.isNativePlatform.mockReturnValue(true);
    const rc = new RadioControl();

    rc.connect("ws://remote-server:9000/player/foo?token=123");

    expect(global.WebSocket).toHaveBeenCalledWith(
      "ws://remote-server:9000/player/foo?token=123",
    );
  });

  it.each([
    [
      "playback_start",
      (rc) => rc.startPlayback("WXXI"),
      { event: "playback_start", data: { station_name: "WXXI" } },
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
        detail:
          "WebSocket not connected. Cannot send playback_start command.",
      }),
    );
  });

  it("emits playback state and station catalog URL events", () => {
    const rc = new RadioControl();
    const playbackSpy = vi.fn();
    const catalogSpy = vi.fn();
    rc.addEventListener("playbackstate", playbackSpy);
    rc.addEventListener("stationcatalogurl", catalogSpy);
    rc.connect("ws://example.com/");

    receiveEvent(rc, "playback_state", { station_name: "WXXI" });
    receiveEvent(rc, "station_catalog_url", {
      url: "https://example.test/stations.json",
    });

    expect(playbackSpy).toHaveBeenCalledWith(
      expect.objectContaining({ detail: "WXXI" }),
    );
    expect(catalogSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        detail: "https://example.test/stations.json",
      }),
    );
  });
});
