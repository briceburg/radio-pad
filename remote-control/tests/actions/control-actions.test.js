import { beforeEach, describe, expect, it, vi } from "vitest";
import { createControlActions } from "../../src/js/actions/control-actions.js";
import { authStore, controlStore, listenStore } from "../../src/js/store.js";

function createMockControl() {
  const control = new EventTarget();
  control.connect = vi.fn(async () => {});
  control.disconnect = vi.fn();
  control.startPlayback = vi.fn();
  control.stopPlayback = vi.fn();
  return control;
}

describe("control-actions", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    authStore.set({ registryBearerToken: null });
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
      playerConnected: null,
      playerStatuses: {},
      statusText: "",
    });
    listenStore.set({
      stationsData: null,
      currentStation: null,
      loading: false,
    });
  });

  it("selects a player, connects, and loads its station catalog", async () => {
    const control = createMockControl();
    const listen = { setStations: vi.fn(), play: vi.fn(), stop: vi.fn() };
    const stationCatalog = {
      name: "Casa Briceburg",
      stations: [{ name: "KEXP" }],
    };
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => stationCatalog,
    });

    const actions = createControlActions({ control, listen });
    const player = {
      id: "living-room",
      name: "Living Room",
      stations_url: "https://example.test/stations.json",
      switchboard_url: "wss://example.test/switchboard/briceburg/living-room",
    };

    await actions.selectPlayer(player);

    expect(control.connect).toHaveBeenCalledWith(player.switchboard_url, null);
    expect(global.fetch).toHaveBeenCalledWith(
      player.stations_url,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(controlStore.get()).toMatchObject({
      player,
      stationsData: stationCatalog,
      loading: false,
    });
  });

  it("dispatches explicit playback commands for control stations", async () => {
    const control = createMockControl();
    const listen = { setStations: vi.fn(), play: vi.fn(), stop: vi.fn() };
    const actions = createControlActions({ control, listen });

    await actions.clickStation("control", "KEXP");
    await actions.stopStation("control");

    expect(control.startPlayback).toHaveBeenCalledWith("KEXP");
    expect(control.stopPlayback).toHaveBeenCalled();
  });
});
