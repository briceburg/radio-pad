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

function createMockListen() {
  return { setStationCatalog: vi.fn(), play: vi.fn(), stop: vi.fn() };
}

const PLAYER = {
  id: "living-room",
  name: "Living Room",
  stations_url: "https://example.test/stations.json",
  switchboard_url: "wss://example.test/switchboard/briceburg/living-room",
};

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
      stationCatalog: null,
      currentStation: null,
      loading: false,
      connectionState: "idle",
      playerConnected: null,
      playerStatuses: {},
      resourceStatuses: {},
    });
    listenStore.set({
      stationCatalog: null,
      currentStation: null,
      loading: false,
    });
  });

  it("selects a player, connects, and loads its station catalog", async () => {
    const control = createMockControl();
    const listen = createMockListen();
    const stationCatalog = {
      name: "Casa Briceburg",
      stations: [{ name: "KEXP" }],
    };
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => stationCatalog,
    });

    const actions = createControlActions({ control, listen });

    await actions.selectPlayer(PLAYER);

    expect(control.connect).toHaveBeenCalledWith(PLAYER.switchboard_url, null);
    expect(global.fetch).toHaveBeenCalledWith(
      PLAYER.stations_url,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(controlStore.get()).toMatchObject({
      player: PLAYER,
      stationCatalog,
      loading: false,
    });
  });

  it("retains a degraded station state when station catalog loading fails", async () => {
    const control = createMockControl();
    const actions = createControlActions({
      control,
      listen: createMockListen(),
    });
    global.fetch.mockRejectedValue(new Error("Failed to fetch"));

    await actions.selectPlayer(PLAYER);

    expect(controlStore.get()).toMatchObject({
      player: PLAYER,
      stationCatalog: null,
      loading: false,
      resourceStatuses: {
        station_catalog: {
          level: "warning",
          summary: "Station catalog unavailable.",
        },
      },
    });
  });

  it("reuses an in-flight station catalog load for a retained URL", async () => {
    const control = createMockControl();
    const actions = createControlActions({
      control,
      listen: createMockListen(),
    });
    let resolveFetch;
    global.fetch.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const selection = actions.selectPlayer(PLAYER);
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledOnce());
    control.dispatchEvent(
      new CustomEvent("stationcatalogurl", { detail: PLAYER.stations_url }),
    );

    expect(global.fetch).toHaveBeenCalledOnce();
    resolveFetch({ ok: true, json: async () => ({ stations: [] }) });
    await selection;
  });

  it("dispatches explicit playback commands for control stations", async () => {
    const control = createMockControl();
    const listen = createMockListen();
    const actions = createControlActions({ control, listen });

    await actions.clickStation("control", "KEXP");
    await actions.stopStation("control");

    expect(control.startPlayback).toHaveBeenCalledWith("KEXP");
    expect(control.stopPlayback).toHaveBeenCalled();
  });
});
