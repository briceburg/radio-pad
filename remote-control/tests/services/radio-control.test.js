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

  beforeEach(() => {
    vi.useFakeTimers();
    mockWebSocketInstance = {
      close: vi.fn(),
      send: vi.fn(),
    };
    const MockWebSocket = vi.fn(function (url) {
      this.url = url;
      Object.assign(this, mockWebSocketInstance);
      return this;
    });
    MockWebSocket.CONNECTING = 0;
    MockWebSocket.OPEN = 1;
    MockWebSocket.CLOSING = 2;
    MockWebSocket.CLOSED = 3;
    mockWebSocketInstance.readyState = MockWebSocket.CONNECTING;
    global.WebSocket = MockWebSocket;
    Capacitor.isNativePlatform.mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("resolves switchboard URL override correctly in browser mode", async () => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", "ws://localhost:8080");
    const rc = new RadioControl();

    rc.connect("ws://remote-server:9000/player/foo?token=123");

    expect(global.WebSocket).toHaveBeenCalledWith(
      "ws://localhost:8080/player/foo?token=123",
    );
  });

  it("resolves same-origin switchboard overrides correctly in browser mode", async () => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", "/switchboard");
    const rc = new RadioControl();

    rc.connect("ws://remote-server:9000/switchboard/player/foo?token=123");

    expect(global.WebSocket).toHaveBeenCalledWith(
      "ws://localhost:3000/switchboard/player/foo?token=123",
    );
  });

  it("connect ignores override in native platform", async () => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", "ws://localhost:8080");
    Capacitor.isNativePlatform.mockReturnValue(true);
    const rc = new RadioControl();

    rc.connect("ws://remote-server:9000/player/foo?token=123");

    expect(global.WebSocket).toHaveBeenCalledWith(
      "ws://remote-server:9000/player/foo?token=123",
    );
  });

  it("sending station request works when connected", async () => {
    const rc = new RadioControl();
    rc.connect("ws://example.com/");

    // simulate open
    rc.ws.readyState = WebSocket.OPEN;

    rc.sendStationRequest("WXXI");

    expect(mockWebSocketInstance.send).toHaveBeenCalledWith(
      JSON.stringify({
        event: "station_request",
        data: "WXXI",
      }),
    );
  });

  it("rewrites player stations_url messages through the local api proxy", async () => {
    const rc = new RadioControl();
    const stationsSpy = vi.fn();
    rc.addEventListener("stationsurl", stationsSpy);

    rc.connect("ws://example.com/");

    rc.ws.onmessage({
      data: JSON.stringify({
        event: "stations_url",
        data: "http://registry:1980/api/presets/briceburg",
      }),
    });

    expect(stationsSpy).toHaveBeenCalledTimes(1);
    expect(stationsSpy.mock.calls[0][0].detail).toBe(
      "http://localhost:3000/api/presets/briceburg",
    );
  });

  it("sends error event if sending request while disconnected", async () => {
    const rc = new RadioControl();
    const errorSpy = vi.fn();
    rc.addEventListener("error", errorSpy);

    // we never call connect() or don't set readyState
    rc.sendStationRequest("WXXI");

    expect(errorSpy).toHaveBeenCalled();
  });

  it("retries control websocket reconnects promptly after disconnect", async () => {
    const rc = new RadioControl();

    rc.connect("ws://example.com/");
    expect(global.WebSocket).toHaveBeenCalledTimes(1);

    rc.ws.readyState = WebSocket.CLOSED;
    rc.ws.onclose();

    await vi.advanceTimersByTimeAsync(499);
    expect(global.WebSocket).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1);
    expect(global.WebSocket).toHaveBeenCalledTimes(2);
  });

  it("closes stalled websocket connection attempts after the control timeout", async () => {
    const rc = new RadioControl();

    rc.connect("ws://example.com/");

    await vi.advanceTimersByTimeAsync(3999);
    expect(mockWebSocketInstance.close).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(mockWebSocketInstance.close).toHaveBeenCalledTimes(1);
  });
});
