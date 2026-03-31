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
  });

  it("resolves switchboard URL override correctly in browser mode", async () => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", "ws://localhost:8080");
    const rc = new RadioControl();
    
    rc.connect("ws://remote-server:9000/player/foo?token=123");
    
    expect(global.WebSocket).toHaveBeenCalledWith("ws://localhost:8080/player/foo?token=123");
  });

  it("connect ignores override in native platform", async () => {
    vi.stubEnv("VITE_SWITCHBOARD_URL", "ws://localhost:8080");
    Capacitor.isNativePlatform.mockReturnValue(true);
    const rc = new RadioControl();
    
    rc.connect("ws://remote-server:9000/player/foo?token=123");
    
    expect(global.WebSocket).toHaveBeenCalledWith("ws://remote-server:9000/player/foo?token=123");
  });
  
  it("sending station request works when connected", async () => {
    const rc = new RadioControl();
    rc.connect("ws://example.com/");
    
    // simulate open
    mockWebSocketInstance.readyState = WebSocket.OPEN;
    
    rc.sendStationRequest("WXXI");
    
    expect(mockWebSocketInstance.send).toHaveBeenCalledWith(JSON.stringify({
      event: "station_request",
      data: "WXXI"
    }));
  });

  it("sends error event if sending request while disconnected", async () => {
    const rc = new RadioControl();
    const errorSpy = vi.fn();
    rc.addEventListener("error", errorSpy);
    
    // we never call connect() or don't set readyState
    rc.sendStationRequest("WXXI");
    
    expect(errorSpy).toHaveBeenCalled();
  });

  it("connect with falsy URL does not create a WebSocket", () => {
    const rc = new RadioControl();

    rc.connect(null);
    expect(global.WebSocket).not.toHaveBeenCalled();

    rc.connect("");
    expect(global.WebSocket).not.toHaveBeenCalled();

    rc.connect(undefined);
    expect(global.WebSocket).not.toHaveBeenCalled();
  });

  it("reconnect delay grows with jitter and is capped at 30 s", () => {
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    const rc = new RadioControl();
    rc.connect("ws://example.com/");

    // Simulate successive close → reconnect cycles
    const delays = [];
    for (let i = 0; i < 15; i++) {
      // Trigger onclose to schedule a reconnect
      rc.ws.onclose();
      // Capture the delay used for the next setTimeout
      const lastCall = vi.getTimerCount();
      const delay = rc.reconnectDelay;
      delays.push(delay);

      // Advance timers to fire the reconnect
      vi.advanceTimersByTime(delay);
    }

    // Delays should increase monotonically (with jitter) up to the 30 s cap
    for (let i = 1; i < delays.length; i++) {
      expect(delays[i]).toBeGreaterThanOrEqual(delays[i - 1]);
    }
    // The cap is 30 000 ms
    expect(delays[delays.length - 1]).toBeLessThanOrEqual(30000);
  });
});
