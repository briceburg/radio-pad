import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../src/js/notifications.js", () => ({
  toastWarning: vi.fn(),
}));

import { createControlActions } from "../../src/js/actions/control-actions.js";
import { authStore, controlStore, listenStore } from "../../src/js/store.js";

function createMockControl() {
  return {
    listeners: new Map(),
    addEventListener(type, handler) {
      this.listeners.set(type, handler);
    },
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn(),
    sendStationRequest: vi.fn(),
  };
}

describe("control-actions", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    authStore.set({
      enabled: false,
      reason: "not_configured",
      signedIn: false,
      name: null,
      email: null,
      subject: null,
      registryBearerToken: null,
    });
    controlStore.set({
      player: {
        id: null,
        name: null,
        stations_url: null,
        switchboard_url: null,
      },
      stationsData: null,
      currentStation: null,
      loading: false,
      connectionState: "idle",
      statusText: "",
    });
    listenStore.set({
      stationsData: null,
      currentStation: null,
      loading: false,
      titleName: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads control stations directly from the selected player metadata", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        name: "Casa Briceburg",
        stations: [{ name: "kunm" }],
      }),
    });
    const control = createMockControl();
    const listen = { setStations: vi.fn(), play: vi.fn(), stop: vi.fn() };
    const actions = createControlActions({ control, listen });
    const player = {
      id: "living-room",
      name: "Living Room",
      stations_url: "http://localhost:3000/api/presets/briceburg",
      switchboard_url: "ws://localhost:3000/switchboard/briceburg/living-room",
    };

    await actions.selectPlayer(player);

    expect(control.connect).toHaveBeenCalledWith(player.switchboard_url, null);
    expect(global.fetch).toHaveBeenCalledWith(
      player.stations_url,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(controlStore.get()).toMatchObject({
      player,
      stationsData: {
        name: "Casa Briceburg",
        stations: [{ name: "kunm" }],
      },
      loading: false,
      connectionState: "connected",
    });
  });

  it("preserves existing control stations during reconnect-only recovery", async () => {
    const control = createMockControl();
    const listen = { setStations: vi.fn(), play: vi.fn(), stop: vi.fn() };
    const actions = createControlActions({ control, listen });
    const stationsData = {
      name: "Casa Briceburg",
      stations: [{ name: "kunm" }],
    };
    const player = {
      id: "living-room",
      name: "Living Room",
      stations_url: "http://localhost:3000/api/presets/briceburg",
      switchboard_url: "ws://localhost:3000/switchboard/briceburg/living-room",
    };

    controlStore.set({
      ...controlStore.get(),
      player,
      stationsData,
      currentStation: "kunm",
      connectionState: "disconnected",
      loading: false,
    });

    await actions.selectPlayer(player, { reconnectOnly: true });

    expect(global.fetch).not.toHaveBeenCalled();
    expect(control.connect).toHaveBeenCalledWith(player.switchboard_url, null);
    expect(controlStore.get()).toMatchObject({
      player,
      stationsData,
      currentStation: "kunm",
      loading: false,
      connectionState: "connecting",
    });
  });
});
